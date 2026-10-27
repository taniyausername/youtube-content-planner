# YouTube Signal-to-Content-Plan System

A runnable research application that turns public YouTube metadata into ranked topic opportunities and editable content plans.

**Project:** Taniya · Roll no. 2320205  
**Programme:** B.Tech, Computer Science & Engineering · CGC College of Engineering, Landran  
**Guides:** Mr. Jagbir Singh Gill and Dr. Pardeep Singh Tiwana

The implementation contains ten modules corresponding to the synopsis. It uses FastAPI, SQLite, scikit-learn and a responsive HTML/CSS/JavaScript interface. It can run entirely offline after dependencies are installed. An optional language model drafts creative wording in live mode; numerical analysis and evidence checks remain deterministic.

## Quick local launch

With Python 3.12 installed, run `python3 start.py` from this folder (Windows: `py -3.12 start.py`). This sets up dependencies and opens the local app automatically. See [START_HERE.md](START_HERE.md).

## Start locally

Install Python 3.12. Extract this folder, open a terminal **inside `youtube-content-planner`**, then:

### Windows (Command Prompt)

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
copy .env.example .env
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### macOS / Linux

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**. Keep the terminal running. Click **Build content plan** with Demo selected. Stop the server with Ctrl+C.

No Node.js build step, database server, YouTube key or language-model subscription is needed for the demo. The first dependency installation needs an internet connection. Always run commands from the project folder.

## What you can do

- Enter a niche, audience, format, publication window and video limit.
- Run a clearly labelled synthetic demo, or retrieve live public metadata.
- Inspect ranked topics, scores, individual signal contributions and critic findings.
- Review source videos, public statistics and sampled channel activity.
- Generate content angles, title directions, hooks and an outline.
- Reopen saved research and export complete JSON, a CSV ranking or a Markdown content plan.
- Delete all saved research and observations from the interface.

The app does not publish videos or access anyone's private channel analytics.

## Enable live YouTube collection

1. Create/select a Google Cloud project and enable **YouTube Data API v3**.
2. Create an API key restricted to that API. If your host has a fixed outbound IP, apply an appropriate server IP restriction.
3. Put the key in the local `.env` file as `YOUTUBE_API_KEY=your-key`.
4. Restart the application. Select **Live · YouTube API** in the interface.

Only the server receives the API key. It never appears in the page, exports or database. The implementation requests at most two search pages and two video-detail batches for a run of up to 100 videos. Retries can increase request count. Consult the current Google Cloud quota screen and official API documentation rather than assuming a fixed available quota.

A run may return fewer videos than requested. The retrieved results are a search sample, not a census. Missing likes/comments/views are retained as unknown. Live API execution requires your own enabled key and internet access.

Repeat live research after at least one hour to start gathering comparable view observations for videos that appear again. One observation cannot establish growth. The system does not infer acceleration from a single snapshot.

## Optional language-model drafting

Set these server environment variables and restart:

```dotenv
LLM_API_KEY=your-provider-key
LLM_MODEL=your-provider-model-id
LLM_BASE_URL=https://api.openai.com/v1
```

The endpoint must support OpenAI-compatible Chat Completions, JSON-object responses and `max_tokens`. Some models require different parameters; adapt `app/drafting.py` for those providers. A malformed response, timeout or provider failure leaves the working template draft in place. Provider calls may incur charges.

Only the top three live opportunities are sent for drafting. Their topic terms, selected audience and format are included; API keys, the database and full collected descriptions are not included. Demo mode never calls a model, even when credentials are configured. Model wording is labelled as a draft and requires editorial review.

## How the ten modules map to the code

| Synopsis module | Implementation | Important boundary |
| --- | --- | --- |
| 1. Data collection | `app/collector.py` | Public search and video metadata; no private analytics or related-video crawling |
| 2. Cleaning/normalisation | `clean()` and `Video` validation | Deduplication, timestamp validation, whitespace cleanup, unknown-statistic preservation |
| 3. Trend detection | `TrendAgent` | Lifetime view pace and observed view gains; no claim of causal demand or acceleration |
| 4. Topic clustering | `TopicClusteringAgent` | TF-IDF and cosine-distance agglomerative clustering; lexical, not semantic embeddings |
| 5. Competitor intelligence | `CompetitorAgent` | Channel participation and upload counts within the retrieved sample; not a full channel audit |
| 6. Opportunity detection | `OpportunityAgent` | Synthesises the specialist outputs into evidence-linked candidates |
| 7. Ranking/scoring | `RankingEngine` | Seven transparent, provisional heuristic weights; no trained outcome prediction |
| 8. Verification/debate | `CriticAgent` and research orchestration | Explicit rule-based challenge and evidence-status assignment; not autonomous LLM-to-LLM debate |
| 9. Strategy generation | `StrategyGenerator`, `drafting.py` | Templates plus optional validated creative drafts |
| 10. Final content plan | Web interface and export routes | Ranked plans with rationale, audience, angle, format, titles, hook, subtopics, priority and evidence strength |

Candidates flagged by the critic remain visible with **Review first**. Their presence is not verification of a trend. The app reports categorical evidence strength instead of an unsupported numerical probability of success.

## Where to publish and share

Use **GitHub for the source code** and a **Python/Docker host for the running application**. They are two different links.

### Source-code link

1. Sign in to GitHub and create an empty repository named `youtube-content-planner`.
2. Make it public for unrestricted evaluator access, or private and invite the evaluator.
3. Upload the contents of this folder, including `app`, `tests`, `docs`, the dependency files and README. Do not upload `.env`, `.venv`, `data` or provider credentials.
4. Alternatively, with Git installed, run:

```sh
git init
git add .
git commit -m "Implement YouTube content research and planning application"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/youtube-content-planner.git
git push -u origin main
```

Replace `YOUR-USERNAME` with your actual GitHub username. The resulting URL is the source link to submit. Project source repository: https://github.com/taniyausername/youtube-content-planner. The commands above also explain how to publish your own copy.

The included GitHub Actions workflow runs the Python tests on pushes and pull requests. Configure repository visibility and collaborator access to match your college's submission requirements. No open-source licence is granted by this package; choose a licence deliberately if you want to permit reuse beyond viewing.

### Working application link

Deploy the included Dockerfile on a host that supports persistent storage, or run the Python start command on a Python application host. GitHub Pages alone cannot run this FastAPI backend.

Configuration:

- Build: `python -m pip install -r requirements.txt`
- Start: `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1`
- If the host requires a dynamic port, use its configured port in that command.
- Health-check path: `/health`
- Persistent writable disk: point `DATABASE_PATH` to a file on the mounted disk, for example `/data/planner.sqlite3`.
- Set a long random `APP_ACCESS_TOKEN` before exposing the app to other people. Give it only to intended reviewers. Use HTTPS through the host's reverse proxy.
- Add `YOUTUBE_API_KEY` and optional model settings through the host's secret/environment settings, never through Git.
- Keep **one worker and one instance** for this version. Its concurrency gate and daily live-run guard are in memory and reset on restart. Configure provider-side quota limits as well.

The host supplies the actual application URL after deployment. This package has not been deployed to an external account.

### Docker on your computer

Create `.env` first, then:

```sh
docker compose up --build
```

Open http://127.0.0.1:8000. Compose binds only to localhost and uses a named volume for saved research. The Docker recipe is supplied but was not executed in the delivery environment.

## Tests

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Tests use a temporary SQLite database and simulated HTTP responses. They do not consume YouTube or model quota. See `docs/VALIDATION.md` for the checks actually performed on this release.

## Project structure

```text
app/
  models.py       Input and video validation
  collector.py    Public YouTube requests and synthetic fixtures
  agents.py       Clustering, specialist agents, critic, scoring, plans
  drafting.py     Optional model drafting with validated fallback
  store.py        SQLite runs and historical observations
  main.py         REST endpoints, orchestration, authentication, exports
  static/         Responsive interface, no frontend build required
tests/            Automated workflow and component tests
docs/             Architecture, scoring and verification notes
```

## Data and operational boundaries

This is a single-owner research application, not a multi-tenant service. The optional access token protects all research/history/export routes. Everyone with that token shares the same history and deletion rights. The token stays in the current page's memory and is not stored by the app in local storage. API/provider keys stay on the server.

SQLite files and exports are unencrypted on disk; protect the host account and backups. Records older than 30 days are deleted when saving, listing or retrieving research. An idle server does not run a cleanup scheduler: clear history before discontinuing use or schedule periodic cleanup if deploying continuously. Exported files are separate copies and must be deleted/updated separately. Review current YouTube API policies before a public production launch.

The live-run cap is a convenience guard, not distributed rate limiting. Requests are bounded to 100 videos; one research run is processed at a time. Browser disconnection does not cancel an already-started run. Errors are presented without exposing provider URLs or keys. Full production deployment would also need user accounts, distributed jobs/quotas, monitoring, backups and deployment-specific security review.

## References

- YouTube search: https://developers.google.com/youtube/v3/docs/search/list
- Video statistics: https://developers.google.com/youtube/v3/docs/videos/list
- FastAPI deployment: https://fastapi.tiangolo.com/deployment/docker/
- scikit-learn TF-IDF: https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html
- GitHub repository creation: https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository
