"""Set up and run the planner on this computer. Python 3.12+ required."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import venv
import webbrowser

ROOT = Path(__file__).resolve().parent


def environment_python():
    return ROOT / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def prepare():
    if sys.version_info < (3, 12):
        raise RuntimeError('Install Python 3.12 or newer from https://www.python.org/downloads/ and run this file again.')
    executable = environment_python()
    if not executable.exists():
        print('Creating the project Python environment…', flush=True)
        venv.EnvBuilder(with_pip=True).create(ROOT / '.venv')
    requirements = ROOT / 'requirements.txt'
    fingerprint = hashlib.sha256(requirements.read_bytes() + sys.version.encode()).hexdigest()
    stamp = ROOT / '.venv' / '.planner-requirements'
    if not stamp.exists() or stamp.read_text() != fingerprint:
        print('Installing dependencies. The first start needs internet access and may take a few minutes.', flush=True)
        subprocess.run([str(executable), '-m', 'pip', 'install', '-r', str(requirements)], cwd=ROOT, check=True)
        stamp.write_text(fingerprint)
    if not (ROOT / '.env').exists():
        shutil.copyfile(ROOT / '.env.example', ROOT / '.env')
    return executable


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--setup-only', action='store_true')
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('Choose a port between 1024 and 65535.')
    executable = prepare()
    if args.setup_only:
        print('Setup complete. Run python3 start.py to open the app.')
        return 0
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1', args.port)) == 0:
            raise RuntimeError(f'Port {args.port} is already in use. Try: python3 start.py --port {args.port + 1 if args.port < 65535 else 8000}')
    address = f'http://127.0.0.1:{args.port}'
    print(f'\nStarting YouTube Content Planner at {address}', flush=True)
    process = subprocess.Popen([str(executable), '-m', 'uvicorn', 'app.main:app',
                                '--host', '127.0.0.1', '--port', str(args.port)], cwd=ROOT)
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        ready = False
        for _ in range(120):
            if process.poll() is not None:
                raise RuntimeError('The server stopped during startup. See the error above.')
            try:
                with opener.open(address + '/health', timeout=1) as response:
                    ready = json.load(response).get('status') == 'ok'
                if ready:
                    break
            except (urllib.error.URLError, OSError, ValueError):
                pass
            time.sleep(.25)
        if not ready:
            raise RuntimeError('The server did not become ready within 30 seconds. See the messages above.')
        print(f'\nApp is ready: {address}\nKeep this terminal open. Press Ctrl+C to stop.\nSelect Demo to use the app without API keys.\n', flush=True)
        if not args.no_browser:
            webbrowser.open(address)
        return process.wait()
    except KeyboardInterrupt:
        print('\nStopping the app…', flush=True)
        return 0
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (RuntimeError, OSError, subprocess.CalledProcessError) as error:
        print(f'\nUnable to start: {error}', file=sys.stderr)
        sys.exit(1)
