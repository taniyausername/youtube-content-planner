"""Small specialist agents with auditable, deterministic assessments.

They exchange structured evidence through the orchestrator. No language model
is used to calculate statistics or to assert that a trend is real.
"""
from collections import Counter
from datetime import datetime
from math import log1p
from statistics import median
import re
import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics.pairwise import cosine_distances
from sklearn.feature_extraction.text import TfidfVectorizer
from .models import ResearchRequest, Video

WEIGHTS = {'demand': .22, 'momentum': .15, 'competition': .12,
           'engagement': .14, 'freshness': .12, 'relevance': .15, 'content_gap': .10}


def mean(values):
    return sum(values) / len(values) if values else None


class TopicClusteringAgent:
    def run(self, videos: list[Video], request: ResearchRequest) -> list[dict]:
        documents = [v.title + ' ' + v.description for v in videos]
        try:
            vectorizer = TfidfVectorizer(stop_words='english', ngram_range=(1, 2),
                                         max_features=4000, sublinear_tf=True)
            matrix = vectorizer.fit_transform(documents)
        except ValueError:
            return [{'topic': request.niche, 'videos': videos, 'terms': [request.niche], 'relevance': 0.0}]
        if len(videos) == 1:
            labels = [0]
        else:
            # Distance threshold preserves the possibility of one coherent cluster.
            labels = AgglomerativeClustering(n_clusters=None, distance_threshold=.78,
                                             metric='precomputed', linkage='average').fit_predict(cosine_distances(matrix))
        query = vectorizer.transform([request.niche])
        similarities = (matrix @ query.T).toarray().ravel()
        features = vectorizer.get_feature_names_out()
        groups = []
        for label in sorted(set(labels)):
            indices = [i for i, value in enumerate(labels) if value == label]
            center = np.asarray(matrix[indices].mean(axis=0)).ravel()
            terms = [str(features[i]) for i in center.argsort()[::-1][:5] if center[i] > 0]
            groups.append({'topic': ' / '.join(terms[:2]) or request.niche,
                           'videos': [videos[i] for i in indices], 'terms': terms,
                           'relevance': float(np.mean(similarities[indices]))})
        return groups


class TrendAgent:
    def run(self, videos: list[Video], previous: dict, request: ResearchRequest):
        ages = [max((v.observed_at - v.published_at).total_seconds() / 86400, 1) for v in videos]
        pace = [v.views / age for v, age in zip(videos, ages) if v.views is not None]
        growth = []
        for v in videos:
            old = previous.get(v.id)
            if old and v.views is not None and v.views >= old['views']:
                days = (v.observed_at - datetime.fromisoformat(old['observed_at'])).total_seconds() / 86400
                if days >= 1 / 24:
                    growth.append((v.views - old['views']) / days)
        return {'demand': median(pace) if pace else None,
                'momentum': median(growth) if growth else None,
                'momentum_samples': len(growth),
                'freshness': mean([max(0.0, 1 - age / request.days) for age in ages]),
                'note': 'Demand is median lifetime views/day, not search volume. Momentum is observed view gain/day, not acceleration.'}


class CompetitorAgent:
    def run(self, videos: list[Video], request: ResearchRequest):
        counts = Counter(v.channel_id for v in videos)
        coverage = sum(bool(re.search(r'\b(example|demo|case study|walkthrough|hands.on)\b',
                                     v.title + ' ' + v.description, re.I)) for v in videos) / len(videos)
        return {'competition': len(counts), 'content_gap': 1 - coverage,
                'channels': [{'id': channel, 'name': next(v.channel_title for v in videos if v.channel_id == channel),
                              'sample_uploads': count, 'sample_uploads_per_day': round(count / request.days, 3)}
                             for channel, count in counts.most_common()],
                'largest_channel_share': max(counts.values()) / len(videos),
                'note': 'Competition counts channels in the retrieved sample. The gap heuristic only checks explicit practical-example wording.'}


class EngagementAgent:
    def run(self, videos: list[Video]):
        ratios = [(v.likes + v.comments) / v.views for v in videos
                  if v.views and v.likes is not None and v.comments is not None]
        return {'engagement': median(ratios) if ratios else None, 'samples': len(ratios),
                'note': 'Median (likes + comments) / views; missing statistics remain unknown.'}


class CriticAgent:
    def run(self, videos: list[Video], trend: dict, competitor: dict, engagement: dict):
        warnings = []
        total = sum(v.views or 0 for v in videos)
        outlier_share = max((v.views or 0 for v in videos), default=0) / total if total else 0
        if len(videos) < 3:
            warnings.append('Fewer than three videos support this topic.')
        if len(competitor['channels']) < 3:
            warnings.append('Fewer than three independent channels support this topic.')
        if outlier_share > .6:
            warnings.append('One video accounts for over 60% of sampled views.')
        if competitor['largest_channel_share'] > .6:
            warnings.append('One channel supplies over 60% of the videos.')
        if trend['momentum_samples'] < 3:
            warnings.append('Insufficient historical observations to establish a broad growth pattern.')
        if engagement['samples'] < len(videos):
            warnings.append('Some engagement statistics are unavailable; missing values are not zero.')
        status = 'review' if len(videos) < 3 or len(competitor['channels']) < 2 or outlier_share > .6 else 'supported_in_sample'
        return {'status': status, 'warnings': warnings, 'outlier_view_share': round(outlier_share, 4),
                'evidence_strength': 'limited' if status == 'review' else 'moderate',
                'confidence_note': 'Evidence strength describes sample support, not the probability of video success.'}


class OpportunityAgent:
    def run(self, cluster: dict, request: ResearchRequest, previous: dict):
        videos = cluster['videos']
        trend = TrendAgent().run(videos, previous, request)
        competition = CompetitorAgent().run(videos, request)
        engagement = EngagementAgent().run(videos)
        critic = CriticAgent().run(videos, trend, competition, engagement)
        signals = {'demand': trend['demand'], 'momentum': trend['momentum'],
                   'competition': competition['competition'], 'engagement': engagement['engagement'],
                   'freshness': trend['freshness'], 'relevance': cluster['relevance'],
                   'content_gap': competition['content_gap']}
        return {'topic': cluster['topic'], 'terms': cluster['terms'], 'raw_signals': signals,
                'agents': {'trend': trend, 'competition': competition, 'engagement': engagement, 'critic': critic},
                'evidence_ids': [v.id for v in videos], 'sample_size': len(videos)}


class RankingEngine:
    def run(self, opportunities: list[dict]) -> list[dict]:
        # Cohort-wide omission keeps every candidate on the same scoring basis.
        active = [key for key in WEIGHTS if all(o['raw_signals'][key] is not None for o in opportunities)]
        denominator = sum(WEIGHTS[key] for key in active)
        weights = {key: WEIGHTS[key] / denominator for key in active}
        normalized = [{} for _ in opportunities]
        for key in active:
            values = [o['raw_signals'][key] for o in opportunities]
            if key in ('demand', 'momentum', 'competition', 'engagement'):
                values = [log1p(max(0, x)) for x in values]
                low, high = min(values), max(values)
                values = [(x - low) / (high - low) if high > low else .5 for x in values]
                if key == 'competition':
                    values = [1 - x for x in values]
            for target, value in zip(normalized, values):
                target[key] = max(0.0, min(1.0, value))
        for opportunity, signals in zip(opportunities, normalized):
            contributions = {key: signals[key] * weight * 100 for key, weight in weights.items()}
            opportunity.update(normalized_signals=signals, effective_weights=weights,
                               contributions=contributions, omitted_signals=[k for k in WEIGHTS if k not in active],
                               score=round(sum(contributions.values()), 2))
        opportunities.sort(key=lambda item: (-item['score'], item['topic']))
        for index, item in enumerate(opportunities, 1):
            item['rank'] = index
            item['id'] = f'opportunity-{index}'
            item['priority'] = 'Review first' if item['agents']['critic']['status'] == 'review' else ('High' if index <= 3 else 'Normal')
        return opportunities


class StrategyGenerator:
    def run(self, opportunity: dict, request: ResearchRequest):
        topic = opportunity['topic']
        return {'source': 'template', 'audience': request.audience, 'format': request.format,
                'angle': f'Test {topic} with a practical example tailored to {request.audience.lower()}.',
                'rationale': f"Ranked using {opportunity['sample_size']} sampled videos. Inspect score contributions and critic findings before choosing this topic.",
                'title_directions': [f'{topic}: a practical starting point', f'{topic}: what worked in a hands-on test'],
                'hook': 'Show the result first, then explain the steps, trade-offs and limitations.',
                'subtopics': opportunity['terms'][:4],
                'outline': ['State the audience problem', 'Demonstrate one concrete example',
                            'Compare trade-offs and common mistakes', 'Summarise the next action'],
                'next_action': 'Review the evidence and check the proposed angle against existing videos before scripting.'}
