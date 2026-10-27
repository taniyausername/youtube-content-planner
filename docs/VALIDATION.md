# Release validation

Date: 26 October 2026. Environment: Linux, Python 3.12.

## Checks completed

| Check | Result |
| --- | --- |
| Install requirements in a new isolated Python virtual environment | Passed |
| `pip check` in that environment | Passed: no broken requirements |
| `python -m pytest -q` in that environment | **30 passed**, one dependency deprecation warning |
| Python module compilation | Passed |
| Frontend JavaScript syntax check | Passed |
| Real Uvicorn server startup and HTTP health request | Passed during interface-logic smoke test |
| Interface research form to backend to rendered DOM | Passed |
| Four distinct demo topic groups, score table and content plan fields | Passed |
| Demo label and absence of fabricated live evidence links | Passed |
| Saved history, reopening and deleting research | Passed |
| HTML-like query is displayed as text, not inserted as markup | Passed |

The DOM test executes the actual frontend JavaScript against a running Uvicorn server using jsdom. It checks interface behaviour without a browser rendering engine. It does **not** establish visual correctness, responsive layout or accessibility conformance.

## Automated Python coverage

The 30 cases cover the complete demo API workflow, ranked score bounds/contributions, consistent missing-signal handling, evidence references, all three export formats, request validation, missing-key errors, access control, HTTP security headers, CSV formula escaping, duplicate/future/invalid records, absent versus zero engagement, historical view gains, declining counters, viral-outlier flags, empty/sparse/identical clustering inputs, SQLite retention, synthetic-history isolation, API pagination/batching, provider error redaction, offline demo behaviour, valid/invalid model drafts and request-size rejection.

YouTube and model responses in these integration tests are simulated. A successful mocked test is not a successful request to the live service.

The dependency warning concerns Starlette's future TestClient migration away from `httpx`. It does not fail these tests or prevent normal application requests. The exact tested Python dependency versions are recorded in `requirements-lock.txt`.

## Checks not completed

- **Live YouTube API execution:** no user API key was supplied.
- **Live language-model execution:** no provider credentials/model were supplied.
- **Full browser rendering, mobile visual inspection and browser download interaction:** the runtime blocked Chromium startup. The browser smoke script is included for execution on a normal development computer; it is not marked as passed.
- **Docker image build/run:** not executed in this environment.
- **External hosting and GitHub publication:** no repository or host was created.
- **Real-world recommendation quality or creator performance:** not measured. No success-rate claim is made.

## Reproduce

From the project folder:

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

To match the tested Python environment exactly, install `requirements-lock.txt` instead. It includes test dependencies.

Optional interface-logic check (requires Node.js):

```sh
npm install --no-save jsdom@26.1.0
node tests/dom_smoke.cjs
```

Optional full-browser check on a computer able to run Chromium:

```sh
npm install --no-save playwright
npx playwright install chromium
node tests/browser_smoke.cjs
```

The two interface scripts start their own local server and temporary database. Run them from the project folder, one at a time. If the Python executable is named differently, set the `PYTHON` environment variable to its path. The browser check requires port 8765; the DOM check uses 8766.

## Local launcher check

The new `start.py` launcher was tested in Linux after a fresh dependency setup. It started Uvicorn on loopback, passed the health check, generated a demo with 30 synthetic videos and four topics, and shut down on Ctrl+C. Run `python tests/local_launcher_smoke.py` after setup to repeat that check. macOS/Windows execution and opening the personal browser remain unverified.
