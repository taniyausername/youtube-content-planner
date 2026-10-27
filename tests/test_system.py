import asyncio
from datetime import datetime, timedelta, timezone
import json
import httpx
import pytest
from fastapi.testclient import TestClient
from app.agents import (TopicClusteringAgent, TrendAgent, CompetitorAgent,
                        EngagementAgent, CriticAgent, RankingEngine)
from app.collector import collect_youtube, clean, demo_videos, CollectionError
from app.main import create_app, safe_cell
from app.models import ResearchRequest, Video
from app.store import Store


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv('APP_ACCESS_TOKEN', raising=False)
    monkeypatch.delenv('YOUTUBE_API_KEY', raising=False)
    return TestClient(create_app(str(tmp_path / 'test.sqlite3')))


def video(**kwargs):
    now = datetime.now(timezone.utc)
    defaults = dict(id='abcdefghijk', title='Python coding tutorial', channel_id='channel-1',
                    channel_title='Creator', published_at=now - timedelta(days=10), observed_at=now,
                    views=1000, likes=20, comments=5)
    return Video(**{**defaults, **kwargs})


def test_demo_full_workflow(client):
    response = client.post('/api/research', json={'niche': 'AI coding tools'})
    assert response.status_code == 200
    run = response.json()
    assert run['video_count'] == 30
    assert len(run['opportunities']) > 1
    assert all(v['synthetic'] for v in run['videos'])
    assert all('momentum' in o['omitted_signals'] for o in run['opportunities'])
    assert run['opportunities'] == sorted(run['opportunities'], key=lambda o: -o['score'])
    for o in run['opportunities']:
        assert 0 <= o['score'] <= 100
        assert sum(o['effective_weights'].values()) == pytest.approx(1)
        assert sum(o['contributions'].values()) == pytest.approx(o['score'], abs=.006)
        assert set(o['evidence_ids']) <= {v['id'] for v in run['videos']}
    assert client.get('/api/runs').json()[0]['id'] == run['id']
    assert client.get('/api/runs/' + run['id']).json() == run
    for kind in ['json', 'csv', 'md']:
        export = client.get(f"/api/runs/{run['id']}/export/{kind}")
        assert export.status_code == 200
        assert 'attachment' in export.headers['content-disposition']
        assert len(export.content) > 100
    assert client.delete('/api/runs').status_code == 200
    assert client.get('/api/runs').json() == []
    assert client.get('/api/runs/' + run['id']).status_code == 404


@pytest.mark.parametrize('payload', [{'niche': ' '}, {'niche': 'x'}, {'niche': 'AI', 'days': 0},
                                     {'niche': 'AI', 'max_videos': 1000}, {'niche': 'AI', 'mode': 'fake'}])
def test_invalid_input(client, payload):
    assert client.post('/api/research', json=payload).status_code == 422


def test_live_missing_key_is_clear(client):
    response = client.post('/api/research', json={'niche': 'AI tools', 'mode': 'live'})
    assert response.status_code == 502
    assert 'YOUTUBE_API_KEY' in response.json()['detail']
    assert client.get('/api/runs').json() == []
    assert client.post('/api/research', json={'niche': 'AI tools'}).status_code == 200


def test_auth_covers_data_routes(client, monkeypatch):
    monkeypatch.setenv('APP_ACCESS_TOKEN', 'test-secret')
    assert client.get('/health').status_code == 200
    assert client.get('/api/config').json()['auth_required']
    assert client.get('/api/runs').status_code == 401
    assert client.delete('/api/runs').status_code == 401
    assert client.post('/api/research', json={'niche': 'tools'}).status_code == 401
    assert client.get('/api/runs/anything/export/json').status_code == 401
    assert client.get('/api/runs', headers={'Authorization': 'Bearer test-secret'}).status_code == 200


def test_security_headers_and_assets(client):
    assert client.get('/').status_code == 200
    assert client.get('/static/app.js').status_code == 200
    assert "script-src 'self'" in client.get('/').headers['content-security-policy']
    assert client.get('/api/runs').headers['cache-control'] == 'no-store'
    assert client.get('/api/runs/not-a-run').status_code == 404


@pytest.mark.parametrize('text', ['=HYPERLINK("bad")', '+cmd', '-2+3', '@SUM(A1)', '  =1'])
def test_csv_formula_injection(text):
    assert safe_cell(text).startswith("'")


def test_cleaning_deduplicates_rejects_future_and_bad_ids():
    v = video(title=' Python  tools ')
    result = clean([v, v, video(id='bad'), video(id='12345678901', published_at=v.observed_at + timedelta(days=1))], v.observed_at)
    assert len(result) == 1
    assert result[0].title == 'Python tools'


def test_missing_engagement_is_not_zero():
    assert EngagementAgent().run([video(likes=None)])['engagement'] is None
    assert EngagementAgent().run([video(likes=0, comments=0)])['engagement'] == 0


def test_momentum_requires_history_and_ignores_counter_decrease():
    v = video()
    req = ResearchRequest(niche='python')
    assert TrendAgent().run([v], {}, req)['momentum'] is None
    old = {v.id: {'observed_at': (v.observed_at - timedelta(days=2)).isoformat(), 'views': 600}}
    assert TrendAgent().run([v], old, req)['momentum'] == 200
    old[v.id]['views'] = 2000
    assert TrendAgent().run([v], old, req)['momentum'] is None


def test_critic_flags_single_viral_video():
    req = ResearchRequest(niche='python')
    videos = [video(views=100000), video(id='12345678901', channel_id='other', views=100)]
    result = CriticAgent().run(videos, TrendAgent().run(videos, {}, req),
                              CompetitorAgent().run(videos, req), EngagementAgent().run(videos))
    assert result['status'] == 'review'
    assert any('60%' in w for w in result['warnings'])


@pytest.mark.parametrize('titles', [['the and or'], ['the and or', 'coding python'], ['Python', 'Python']])
def test_clustering_sparse_and_identical_documents(titles):
    videos = [video(id=str(i), title=t) for i, t in enumerate(titles)]
    groups = TopicClusteringAgent().run(videos, ResearchRequest(niche='python'))
    assert sum(len(g['videos']) for g in groups) == len(titles)


def test_cohort_omits_missing_features_consistently():
    base = {'demand': 10, 'momentum': 2, 'competition': 4, 'engagement': .02,
            'freshness': .5, 'relevance': .2, 'content_gap': .4}
    items = [{'topic': str(i), 'raw_signals': {**base, 'momentum': None if i == 0 else 2},
              'agents': {'critic': {'status': 'supported_in_sample'}}} for i in range(2)]
    ranked = RankingEngine().run(items)
    assert all('momentum' not in o['effective_weights'] for o in ranked)
    assert ranked[0]['score'] == ranked[1]['score']


def test_store_observation_age_and_retention(tmp_path):
    store = Store(str(tmp_path / 'store.db'))
    v = video()
    older = v.model_copy(update={'observed_at': v.observed_at - timedelta(hours=2), 'views': 500})
    run = {'id': 'one', 'created_at': older.observed_at.isoformat(), 'request': {}, 'video_count': 1}
    store.save(run, [older])
    assert store.previous([v])[v.id]['views'] == 500
    assert store.previous([v.model_copy(update={'synthetic': True})]) == {}
    with store.connect() as connection:
        connection.execute('UPDATE runs SET created_at = ?', ((v.observed_at - timedelta(days=31)).isoformat(),))
    assert store.get('one') is None


def test_youtube_pagination_missing_statistics_and_dedup():
    calls = []
    def handler(request):
        calls.append(request)
        if request.url.path.endswith('/search'):
            return httpx.Response(200, json={'items': [{'id': {'videoId': 'abcdefghijk'}}, {'id': {'videoId': 'abcdefghijk'}}]})
        return httpx.Response(200, json={'items': [{'id': 'abcdefghijk', 'snippet': {
            'title': 'Coding', 'channelId': 'channel', 'publishedAt': '2026-01-01T00:00:00Z'}, 'statistics': {'viewCount': '15'}}]})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            return await collect_youtube(ResearchRequest(niche='coding'), 'secret', c)
    videos = asyncio.run(run())
    assert len(videos) == 1 and videos[0].views == 15 and videos[0].likes is None
    assert len(calls) == 2
    assert calls[0].url.params['type'] == 'video'


def test_provider_errors_do_not_leak_keys():
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(403, text='secret-key'))) as c:
            await collect_youtube(ResearchRequest(niche='coding'), 'secret-key', c)
    with pytest.raises(CollectionError) as error:
        asyncio.run(run())
    assert 'secret-key' not in str(error.value)


def test_demo_does_not_call_network(client, monkeypatch):
    async def fail(*args, **kwargs):
        raise AssertionError('Demo must not call the network')
    monkeypatch.setattr(httpx.AsyncClient, 'get', fail)
    monkeypatch.setattr(httpx.AsyncClient, 'post', fail)
    monkeypatch.setenv('LLM_API_KEY', 'configured-but-unused')
    monkeypatch.setenv('LLM_MODEL', 'configured-but-unused')
    assert client.post('/api/research', json={'niche': 'coding'}).status_code == 200


def test_live_pagination_uses_token_and_batches_fifty():
    calls = []
    ids = [f'{i:011d}' for i in range(70)]
    def handler(request):
        calls.append(request)
        if request.url.path.endswith('/search'):
            if 'pageToken' not in request.url.params:
                return httpx.Response(200, json={'items': [{'id': {'videoId': i}} for i in ids[:50]], 'nextPageToken': 'page-two'})
            assert request.url.params['pageToken'] == 'page-two'
            return httpx.Response(200, json={'items': [{'id': {'videoId': i}} for i in ids[50:]]})
        selected = request.url.params['id'].split(',')
        assert len(selected) <= 50
        return httpx.Response(200, json={'items': [{'id': i, 'snippet': {'title': 'Example', 'channelId': 'channel',
            'publishedAt': (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()}, 'statistics': {}} for i in selected]})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            return await collect_youtube(ResearchRequest(niche='coding', max_videos=70), 'secret', c)
    assert len(asyncio.run(run())) == 70
    assert len(calls) == 4


def test_llm_validates_and_keeps_evidence_untouched(monkeypatch):
    from app.drafting import enhance
    monkeypatch.setenv('LLM_API_KEY', 'key')
    monkeypatch.setenv('LLM_MODEL', 'test-model')
    async def post(self, url, **kwargs):
        content = {'angle': 'Build a concrete example', 'hook': 'Start with the result',
                   'title_directions': ['A practical guide', 'Tested workflow'], 'outline': ['Problem', 'Example', 'Limitations']}
        return httpx.Response(200, request=httpx.Request('POST', url), json={'choices': [{'message': {'content': json.dumps(content)}}]})
    monkeypatch.setattr(httpx.AsyncClient, 'post', post)
    item = {'topic': 'python', 'terms': ['python'], 'score': 52, 'evidence_ids': ['one'], 'plan': {'source': 'template'}}
    asyncio.run(enhance([item], ResearchRequest(niche='python')))
    assert item['plan']['source'] == 'language_model_draft'
    assert item['score'] == 52 and item['evidence_ids'] == ['one']


def test_llm_failure_falls_back(monkeypatch):
    from app.drafting import enhance
    monkeypatch.setenv('LLM_API_KEY', 'key')
    monkeypatch.setenv('LLM_MODEL', 'test-model')
    async def post(self, url, **kwargs):
        return httpx.Response(200, request=httpx.Request('POST', url), json={'choices': [{'message': {'content': '{"score":100}'}}]})
    monkeypatch.setattr(httpx.AsyncClient, 'post', post)
    item = {'topic': 'python', 'terms': ['python'], 'plan': {'source': 'template'}}
    result = asyncio.run(enhance([item], ResearchRequest(niche='python')))
    assert item['plan'] == {'source': 'template'}
    assert '1 used the template fallback' in result


def test_request_body_limit(client):
    assert client.post('/api/research', content='x' * 17000).status_code == 413
