#!/usr/bin/env python3
"""Audit a resolved research archive; optionally extract into ignored staging.

Does not download, run imported code, or promote files into version control.
Only Python's standard library is required.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile
import zipfile

REPO = Path(__file__).resolve().parents[1]
MAX_FILE = 128 * 1024 * 1024
MAX_TOTAL = 512 * 1024 * 1024
MAX_ENTRIES = 10000
BLOCKED_PARTS = {'.git', '.aws', '.ssh', '.codex', '.venv', 'node_modules',
                 '__pycache__', 'cache', 'browser', 'browser_state', 'restricted'}
SECRET = re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|'
                    rb'gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,}|'
                    rb'AKIA[A-Z0-9]{16}')


def audit_archive(path, expected_size=None):
    path = Path(path)
    actual_size = path.stat().st_size
    if expected_size is not None and actual_size != expected_size:
        raise ValueError(f'Archive size mismatch: {actual_size} != {expected_size}')
    if actual_size > MAX_TOTAL:
        raise ValueError('Compressed archive exceeds size limit')
    entries = []
    seen = set()
    total = 0
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_ENTRIES:
            raise ValueError('Too many archive entries')
        for info in infos:
            name = info.filename
            rel = PurePosixPath(name)
            parts = rel.parts
            if (not parts or rel.is_absolute() or '..' in parts or '\\' in name
                    or ':' in name or any(ord(c) < 32 for c in name)
                    or name.rstrip('/') != str(rel) or str(rel) == '_import_manifest.json'):
                raise ValueError(f'Unsafe archive path: {name!r}')
            normalized = str(rel).casefold()
            if normalized in seen:
                raise ValueError(f'Duplicate archive path: {name!r}')
            seen.add(normalized)
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode) or stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR):
                raise ValueError(f'Unsupported archive entry: {name!r}')
            lowered = [p.lower() for p in parts]
            basename = lowered[-1]
            if (set(lowered) & BLOCKED_PARTS or basename.startswith('.env')
                    or any(term in basename for term in ('credential', 'cookie', 'token', 'password'))
                    or basename.endswith(('.pem', '.key'))):
                raise ValueError(f'Sensitive or cache entry requires manual review: {name!r}')
            total += info.file_size
            if info.file_size > MAX_FILE or total > MAX_TOTAL:
                raise ValueError('Uncompressed archive exceeds size limit')
            if info.is_dir():
                continue
            # Reading also validates CRC. Never deserialize or execute imported code.
            payload = archive.read(info)
            if SECRET.search(payload):
                raise ValueError(f'Potential credential requires manual review: {name!r}')
            entries.append({'path': str(rel), 'size_bytes': len(payload),
                            'sha256': hashlib.sha256(payload).hexdigest()})
    # Detect file/directory conflicts before creating any output.
    files = {e['path'].casefold() for e in entries}
    for entry in entries:
        if any(str(p).casefold() in files for p in PurePosixPath(entry['path']).parents if str(p) != '.'):
            raise ValueError('Archive contains a file/directory path conflict')
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'archive_name': path.name, 'size_bytes': actual_size,
            'sha256': digest,
            'uncompressed_size_bytes': total, 'files': entries,
            'review_status': 'staging_only_not_approved_for_commit'}


def stage_archive(path, destination, expected_size=None):
    report = audit_archive(path, expected_size)
    destination = Path(destination)
    # Require a fresh directory and a real parent; never overwrite prior work.
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        raise ValueError('Destination already exists; choose a new staging directory')
    with tempfile.TemporaryDirectory(prefix='.archive-', dir=destination.parent) as temp:
        root = Path(temp)
        with zipfile.ZipFile(path) as archive:
            for entry in report['files']:
                target = root / entry['path']
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(entry['path']))
                target.chmod(0o600)
        (root / '_import_manifest.json').write_text(json.dumps(report, indent=2) + '\n')
        os.rename(root, destination)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--extract', action='store_true', help='Stage reviewed bytes; never executes code')
    args = parser.parse_args()
    registry = json.loads((REPO / 'research/sources.json').read_text())
    matches = [s for s in registry['library_archives'] if s['name'] == args.archive.name]
    if len(matches) != 1:
        parser.error('Archive name must match one registered research source')
    source = matches[0]
    try:
        if args.extract:
            report = stage_archive(args.archive, REPO / 'data/staging' / args.archive.stem,
                                   source['expected_size_bytes'])
        else:
            report = audit_archive(args.archive, source['expected_size_bytes'])
    except (ValueError, OSError, zipfile.BadZipFile, RuntimeError) as error:
        parser.exit(1, f'Archive not staged: {error}\n')
    report['library_file_id'] = source['library_file_id']
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
