"""Build the complete, checksummed runtime bundle for the animated hybrid."""
import argparse
import json
from pathlib import Path

from hybrid_artifacts import build_bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    digest = build_bundle(Path(__file__).resolve().parents[1], args.out)
    print(json.dumps(dict(file=str(args.out), sha256=digest,
                         s3_key=f'models/flex2-hybrid/{digest}/bundle.zip')))


if __name__ == '__main__':
    main()
