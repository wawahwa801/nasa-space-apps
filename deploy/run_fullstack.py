"""Run and supervise the frontend and API together inside the deployment image."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading


def main():
    root = Path(__file__).resolve().parents[1]
    stopped = threading.Event()
    for name in (signal.SIGTERM, signal.SIGINT):
        signal.signal(name, lambda *_: stopped.set())
    env = dict(os.environ, BACKEND_URL='http://127.0.0.1:5000')
    children = []
    try:
        children.append(subprocess.Popen([
            sys.executable, '-m', 'gunicorn', '--bind', '127.0.0.1:5000',
            '--workers', '1', '--threads', '2', '--timeout', '180',
            '--access-logfile', '-', 'app:create_app()',
        ], cwd=root / 'backend', env=env))
        children.append(subprocess.Popen([
            'node', 'node_modules/next/dist/bin/next', 'start',
            '--hostname', '0.0.0.0', '--port', '8080',
        ], cwd=root / 'frontend', env=env))
        while not stopped.wait(.25):
            if any(child.poll() is not None for child in children):
                return 1
        return 0
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == '__main__':
    sys.exit(main())
