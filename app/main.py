import asyncio
import csv
from datetime import datetime, timezone
from io import StringIO
import json
import os
from pathlib import Path
import secrets
import threading
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .agents import TopicClusteringAgent, OpportunityAgent, RankingEngine, StrategyGenerator, WEIGHTS
from .collector import CollectionError, collect_youtube, demo_videos
from .drafting import enhance
from .models import ResearchRequest
from .store import Store

load_dotenv()
STATIC = Path(__file__).parent / 'static'


def markdown(result):
    lines = ['# YouTube content plan', '', f"Research: {result['request']['niche']}",
             f"Mode: {result['request']['mode']} | Created: {result['created_at']}", '',
             'Scores compare this sample only; they do not predict success.', '']
    for item in result['opportunities']:
        plan = item['plan']
        lines += [f"## {item['rank']}. {item['topic']}", '',
                  f"Score: {item['score']} | Priority: {item['priority']} | Evidence: {item['agents']['critic']['evidence_strength']}",
                  f"Audience: {plan['audience']} | Format: {plan['format']}", '', plan['rationale'], '', plan['angle'], '',
                  'Title directions:', *['- ' + x for x in plan['title_directions']], '',
                  'Hook: ' + plan['hook'], '', 'Outline:', *['- ' + x for x in plan['outline']], '',
                  'Critic findings:', *['- ' + x for x in item['agents']['critic']['warnings']], '',
                  'Evidence IDs: ' + ', '.join(item['evidence_ids']), '']
    lines += ['## Evidence', '']
    for v in result['videos']:
        lines.append(f"- {v['id']}: {v['title']} | {v['channel_title']} | views={v['views']} | observed={v['observed_at']}")
    return '\n'.join(lines)


def safe_cell(value):
    text = str(value)
    return "'" + text if text.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')) else text


def create_app(db_path: str | None = None):
    application = FastAPI(title='YouTube Signal-to-Content-Plan System', version='1.0.0',
                          docs_url=None, redoc_url=None, openapi_url=None)
    store = Store(db_path or os.getenv('DATABASE_PATH', 'data/planner.sqlite3'))
    application.state.store = store
    gate = threading.BoundedSemaphore(1)
    budget_lock = threading.Lock()
    live_budget = {'day': '', 'used': 0}

    def authenticate(authorization: str | None = Header(default=None)):
        token = os.getenv('APP_ACCESS_TOKEN', '')
        if token and not secrets.compare_digest((authorization or '').encode(), ('Bearer ' + token).encode()):
            raise HTTPException(401, 'Enter the app access token supplied by the owner.')

    @application.middleware('http')
    async def headers(request, call_next):
        try:
            content_length = int(request.headers.get('content-length', '0'))
        except ValueError:
            return Response('Invalid content length', status_code=400)
        if content_length > 16384:
            return Response('Request too large', status_code=413)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        if request.url.path.startswith('/api'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @application.get('/')
    def index():
        return FileResponse(STATIC / 'index.html')

    @application.get('/health')
    def health():
        return {'status': 'ok'}

    @application.get('/api/config')
    def config():
        return {'auth_required': bool(os.getenv('APP_ACCESS_TOKEN')),
                'live_available': bool(os.getenv('YOUTUBE_API_KEY')),
                'llm_available': bool(os.getenv('LLM_API_KEY') and os.getenv('LLM_MODEL'))}

    @application.get('/api/runs', dependencies=[Depends(authenticate)])
    def history():
        return store.history()

    @application.delete('/api/runs', dependencies=[Depends(authenticate)])
    def clear():
        if not gate.acquire(blocking=False):
            raise HTTPException(409, 'Wait for the current research run before clearing history.')
        try:
            store.clear()
            return {'deleted': True}
        finally:
            gate.release()

    @application.post('/api/research', dependencies=[Depends(authenticate)])
    def research(request: ResearchRequest):
        if not gate.acquire(blocking=False):
            raise HTTPException(429, 'A research run is already active. Try again when it finishes.')
        try:
            if request.mode == 'live':
                with budget_lock:
                    today = datetime.now(timezone.utc).date().isoformat()
                    if live_budget['day'] != today:
                        live_budget.update(day=today, used=0)
                    if live_budget['used'] >= int(os.getenv('MAX_LIVE_RUNS_PER_DAY', '20')):
                        raise HTTPException(429, 'The server daily live-research limit has been reached.')
                    live_budget['used'] += 1
                videos = asyncio.run(collect_youtube(request, os.getenv('YOUTUBE_API_KEY', '')))
            else:
                videos = demo_videos(request)
            if not videos:
                raise HTTPException(422, 'No usable videos were returned. Try a broader niche or longer date window.')
            clusters = TopicClusteringAgent().run(videos, request)
            previous = store.previous(videos)
            candidates = [OpportunityAgent().run(group, request, previous) for group in clusters]
            ranked = RankingEngine().run(candidates)
            for item in ranked:
                item['plan'] = StrategyGenerator().run(item, request)
            # Demo remains offline even if the server has provider credentials.
            drafting = asyncio.run(enhance(ranked, request)) if request.mode == 'live' else 'Offline template drafting in demo mode.'
            result = {'id': str(uuid4()), 'created_at': datetime.now(timezone.utc).isoformat(),
                      'request': request.model_dump(), 'video_count': len(videos),
                      'videos': [v.model_dump(mode='json') for v in videos],
                      'opportunities': ranked, 'base_weights': WEIGHTS, 'drafting': drafting,
                      'limitations': [
                          'DEMO: all video records are synthetic.' if request.mode == 'demo' else 'Live public metadata from a bounded YouTube search sample.',
                          'Retrieval is not a representative sample of all YouTube videos or audience demand.',
                          'Scores and weights are provisional heuristics, not a trained performance predictor.',
                          'Lexical TF-IDF clustering may miss synonyms; content gaps require manual review.',
                          'Specialist agents and critic use explicit rules, not autonomous LLM debate.',
                          'View gain measures observed growth, not acceleration or causal demand.',
                          'Downloaded exports must be managed separately from server retention.']}
            store.save(result, videos)
            return result
        except CollectionError as exc:
            raise HTTPException(502, str(exc)) from None
        finally:
            gate.release()

    @application.get('/api/runs/{run_id}', dependencies=[Depends(authenticate)])
    def get(run_id: str):
        result = store.get(run_id)
        if result is None:
            raise HTTPException(404, 'Research run not found or expired.')
        return result

    @application.get('/api/runs/{run_id}/export/{kind}', dependencies=[Depends(authenticate)])
    def export(run_id: str, kind: str):
        result = get(run_id)
        if kind == 'json':
            content, media = json.dumps(result, indent=2, ensure_ascii=False), 'application/json'
        elif kind == 'md':
            content, media = markdown(result), 'text/markdown'
        elif kind == 'csv':
            out = StringIO()
            writer = csv.writer(out)
            writer.writerow(['rank', 'topic', 'score', 'priority', 'evidence_strength', 'angle', 'evidence_ids'])
            for item in result['opportunities']:
                writer.writerow([safe_cell(x) for x in [item['rank'], item['topic'], item['score'], item['priority'],
                                 item['agents']['critic']['evidence_strength'], item['plan']['angle'], ','.join(item['evidence_ids'])]])
            content, media = out.getvalue(), 'text/csv'
        else:
            raise HTTPException(404, 'Supported formats: json, csv, md.')
        return Response(content, media_type=media,
                        headers={'Content-Disposition': f'attachment; filename="content-plan.{kind}"'})

    application.mount('/static', StaticFiles(directory=STATIC), name='static')
    return application


app = create_app()
