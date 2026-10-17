#!/usr/bin/env python3
"""Package synthetic run evidence, excluding host state and Git internals."""
import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path


def archive(directory, destination):
    files = {}
    for path in sorted(directory.rglob('*')):
        relative = path.relative_to(directory)
        if not path.is_file() or path.is_symlink():
            continue
        if relative.parts[0] == 'workspace':
            if len(relative.parts) < 2 or relative.parts[1] in ('.git', 'home', 'installed'):
                continue
        if '__pycache__' in relative.parts:
            continue
        data = path.read_bytes()
        value = {'sha256': hashlib.sha256(data).hexdigest()}
        try:
            value['text'] = data.decode('utf-8')
        except UnicodeError:
            value['base64'] = base64.b64encode(data).decode('ascii')
        files[str(relative)] = value
    payload = {'schema_version': 1, 'source_run': directory.name, 'files': files,
               'excluded': ['workspace/.git', 'workspace/home', 'workspace/installed', 'symlinks', '__pycache__']}
    # Existing text records stay compatible; binary payloads retain exact bytes.
    destination.write_bytes(gzip.compress((json.dumps(payload, ensure_ascii=False) + '\n').encode(), mtime=0))
    return {'path': str(destination), 'sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
            'files': len(files), 'bytes': destination.stat().st_size}


def verify(path):
    payload = json.loads(gzip.decompress(path.read_bytes()))
    for name, value in payload['files'].items():
        if ('text' in value) == ('base64' in value):
            raise ValueError('ambiguous content encoding: ' + name)
        data = value['text'].encode() if 'text' in value else base64.b64decode(value['base64'], validate=True)
        if hashlib.sha256(data).hexdigest() != value['sha256']:
            raise ValueError('content digest mismatch: ' + name)
    return {'run': payload['source_run'], 'verified_files': len(payload['files'])}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    print(json.dumps(archive(args.source, args.out) if args.out else verify(args.source)))
