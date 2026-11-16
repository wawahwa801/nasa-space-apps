"""Versioned hybrid artifacts: no executable code is downloaded from S3."""
import hashlib
import json
from pathlib import Path
import re
import stat
import tempfile
import zipfile

import boto3
from botocore.config import Config

FORMAT = 'pyroclast-hybrid-v1'
FILES = (
    'geometry/snapshot.json', 'geometry/training/final.pt',
    'geometry/training/run.json', 'geometry/training/metrics.jsonl',
    'geometry/expanded/manifest.json', 'geometry/expanded/prepared.npz',
    'geometry/expanded/features.csv', 'baseline/manifest.json',
    'baseline/prepared.npz', 'baseline/selected.pt',
)
MAX_ARCHIVE = 256 * 1024 * 1024
MAX_EXPANDED = 512 * 1024 * 1024


class ArtifactUnavailable(Exception):
    pass


def sha256(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def build_bundle(repo, destination):
    repo, destination = Path(repo), Path(destination)
    sources = {}
    for name in FILES:
        if name.startswith('geometry/'):
            source = repo / 'ml/data/flex2-geometry-model' / name.removeprefix('geometry/')
        elif name == 'baseline/selected.pt':
            source = repo / 'ml/artifacts/flex2-study/selected.pt'
        else:
            source = repo / 'ml/data/flex2-study' / name.removeprefix('baseline/')
        if not source.is_file():
            raise ArtifactUnavailable('Missing runtime artifact: ' + name)
        sources[name] = source
    snapshot = json.loads(sources['geometry/snapshot.json'].read_text())
    for name, spec in snapshot['files'].items():
        source = sources.get('geometry/' + name)
        if source is None or source.stat().st_size != spec['bytes'] or sha256(source) != spec['sha256']:
            raise ArtifactUnavailable('Hybrid snapshot verification failed')
    manifest = dict(format=FORMAT, files={name:dict(bytes=p.stat().st_size, sha256=sha256(p)) for name,p in sources.items()})
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation preserves already-published package identities.
    with zipfile.ZipFile(destination, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('bundle.json', json.dumps(manifest, sort_keys=True))
        for name, source in sources.items():
            archive.write(source, name)
    return sha256(destination)


def verify_directory(root):
    root = Path(root)
    manifest_path = root / 'bundle.json'
    if manifest_path.is_symlink() or manifest_path.stat().st_size > 32768:
        raise ArtifactUnavailable('Invalid bundle manifest')
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('format') != FORMAT or set(manifest.get('files', {})) != set(FILES):
        raise ArtifactUnavailable('Unsupported hybrid package')
    total = 0
    for name in FILES:
        path = root / name
        spec = manifest['files'][name]
        total += spec['bytes']
        if path.is_symlink() or not path.is_file() or path.stat().st_size != spec['bytes'] or sha256(path) != spec['sha256']:
            raise ArtifactUnavailable('Hybrid package file verification failed')
    if total > MAX_EXPANDED:
        raise ArtifactUnavailable('Hybrid package is too large')
    return manifest


def extract_bundle(archive_path, destination):
    destination = Path(destination)
    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
        names = [m.filename for m in members]
        if len(names) != len(set(names)) or set(names) != set(FILES) | {'bundle.json'}:
            raise ArtifactUnavailable('Unexpected or duplicate package entries')
        if sum(m.file_size for m in members) > MAX_EXPANDED:
            raise ArtifactUnavailable('Expanded package is too large')
        for member in members:
            if member.is_dir() or stat.S_ISLNK(member.external_attr >> 16):
                raise ArtifactUnavailable('Package links are not allowed')
            # Names are restricted to the exact fixed FILES set above.
            target = destination / member.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open('xb') as output:
                while block := source.read(1024 * 1024):
                    output.write(block)
    verify_directory(destination)


class S3ArtifactCache:
    def __init__(self, cache_dir, bucket, prefix='models/flex2-hybrid/', region=None, client=None):
        self.root = Path(cache_dir)
        self.bucket, self.prefix, self.region = bucket, prefix, region
        self.client = client

    def prepare(self, model):
        digest = model.get('sha256')
        if not isinstance(digest, str) or not re.fullmatch('[a-fA-F0-9]{64}', digest):
            raise ArtifactUnavailable('Registry record needs a package SHA-256')
        digest = digest.lower()
        if not self.bucket or model.get('s3_bucket') != self.bucket or not model.get('s3_key', '').startswith(self.prefix):
            raise ArtifactUnavailable('Registry artifact is outside the configured hybrid location')
        target = self.root / digest
        if target.exists():
            verify_directory(target)
            return target
        self.root.mkdir(parents=True, exist_ok=True)
        if self.client is None:
            self.client = boto3.Session(region_name=self.region).client('s3', config=Config(
                connect_timeout=5, read_timeout=30,
                retries={'total_max_attempts': 3, 'mode': 'standard'}))
        with tempfile.TemporaryDirectory(dir=self.root, prefix='download-') as temp:
            temp = Path(temp)
            package = temp / 'bundle.zip'
            response = self.client.get_object(Bucket=self.bucket, Key=model['s3_key'])
            with response['Body'] as stream:
                if response.get('ContentLength', MAX_ARCHIVE + 1) > MAX_ARCHIVE:
                    raise ArtifactUnavailable('S3 package is too large')
                size = 0
                with package.open('xb') as output:
                    for block in iter(lambda: stream.read(1024 * 1024), b''):
                        size += len(block)
                        if size > MAX_ARCHIVE:
                            raise ArtifactUnavailable('S3 package is too large')
                        output.write(block)
            if sha256(package) != digest:
                raise ArtifactUnavailable('S3 package checksum does not match registry')
            extracted = temp / 'extracted'
            extract_bundle(package, extracted)
            try:
                extracted.rename(target)
            except OSError:
                if not target.is_dir():
                    raise
                verify_directory(target)
        return target
