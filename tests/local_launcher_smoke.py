"""Run after `python start.py --setup-only`; uses a temporary research database."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as temp:
    with open(Path(temp) / 'server.log', 'w+') as log:
        process = subprocess.Popen([sys.executable, str(root / 'start.py'), '--no-browser', '--port', '8018'],
            cwd=root, stdout=log, stderr=subprocess.STDOUT,
            env={**os.environ, 'DATABASE_PATH': str(Path(temp) / 'test.db'), 'APP_ACCESS_TOKEN': '',
                 'YOUTUBE_API_KEY': '', 'LLM_API_KEY': ''})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            ready = False
            for _ in range(120):
                if process.poll() is not None:
                    log.seek(0)
                    raise RuntimeError(log.read())
                try:
                    with opener.open('http://127.0.0.1:8018/health', timeout=1) as response:
                        ready = json.load(response)['status'] == 'ok'
                    if ready:
                        break
                except (urllib.error.URLError, OSError):
                    pass
                time.sleep(.25)
            assert ready, 'Launcher did not start the server'
            request = urllib.request.Request('http://127.0.0.1:8018/api/research',
                data=json.dumps({'niche': 'AI coding tools', 'mode': 'demo'}).encode(),
                headers={'Content-Type': 'application/json'})
            with opener.open(request, timeout=15) as response:
                result = json.load(response)
            assert result['video_count'] == 30
            assert len(result['opportunities']) == 4
            print('PASS: launcher starts the app, health check succeeds, demo returns 30 videos and 4 topics.')
        finally:
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
                process.wait(timeout=15)
