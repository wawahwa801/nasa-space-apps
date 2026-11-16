"""Export committed deployment sources; no local .env, venv or model files."""
import argparse
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('Choose a new output path; existing archives are preserved.')
    root = Path(__file__).resolve().parents[1]
    paths = ['Dockerfile', '.dockerignore', 'deploy/run_fullstack.py',
             'frontend', 'fire-dashboard', 'backend', 'ml/*.py', 'physics-flex2/*.py']
    # Export HEAD rather than a working directory that could contain credentials.
    archive = subprocess.check_output(['git', 'archive', '--format=zip', 'HEAD', *paths], cwd=root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('xb') as stream:
        stream.write(archive)
    print('Exported committed source bundle:', args.out)


if __name__ == '__main__':
    main()
