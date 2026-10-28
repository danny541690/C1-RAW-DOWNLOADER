"""Durable QA state on isolated Git branches, with fast-forward-only commits.

No checkout, main-branch modification, force push, source RAW or credential data.
Artifacts remain a recovery fallback if saving the state branch fails.
"""
import argparse
import json
import subprocess
from pathlib import Path

LANES = ('inventory', 'worker-0', 'worker-1', 'worker-2')
FILES = ('inventory.json.gz', 'worker.json.gz')


def git(*args, data=None, check=True):
    return subprocess.run(['git', *args], input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=check)


def restore(directory, lease, lane):
    branch = 'jarvis-acceptance-state/' + lane
    ref = 'refs/heads/' + branch
    listing = git('ls-remote', '--exit-code', '--heads', 'origin', ref, check=False)
    directory.mkdir(parents=True, exist_ok=True)
    if any(directory.iterdir()):
        raise ValueError('RESTORE_DESTINATION_MUST_BE_EMPTY')
    if listing.returncode == 2:
        parent = None
    elif listing.returncode == 0:
        git('fetch', '--no-tags', '--depth=1', 'origin', ref)
        parent = git('rev-parse', 'FETCH_HEAD').stdout.decode().strip()
        names = git('ls-tree', '--name-only', parent).stdout.decode().splitlines()
        if set(names) - set(FILES):
            raise ValueError('UNEXPECTED_STATE_BRANCH_CONTENT')
        for name in names:
            (directory / name).write_bytes(git('show', parent + ':' + name).stdout)
    else:
        raise RuntimeError('STATE_REMOTE_UNAVAILABLE')
    lease.write_text(json.dumps(dict(branch=branch, parent=parent)))


def commit(directory, lease, lane):
    info = json.loads(lease.read_text())
    branch = 'jarvis-acceptance-state/' + lane
    if info['branch'] != branch:
        raise ValueError('STATE_BRANCH_SCOPE')
    entries = []
    for name in FILES:
        path = directory / name
        if path.is_file():
            blob = git('hash-object', '-w', '--stdin', data=path.read_bytes()).stdout.decode().strip()
            entries.append(f'100644 blob {blob}\t{name}\n')
    if not entries:
        return  # Authentication/setup may have failed before a checkpoint.
    tree = git('mktree', data=''.join(entries).encode()).stdout.decode().strip()
    if info['parent']:
        old_tree = git('rev-parse', info['parent'] + '^{tree}').stdout.decode().strip()
        if old_tree == tree:
            return
    args = ['-c', 'user.name=JARVIS acceptance worker', '-c',
            'user.email=jarvis-acceptance@users.noreply.github.com', 'commit-tree', tree]
    if info['parent']:
        args += ['-p', info['parent']]
    commit_sha = git(*args, data=b'Checkpoint read-only acceptance work [skip ci]\n').stdout.decode().strip()
    # Fast-forward only. A competing writer causes failure, never silent overwrite.
    git('push', 'origin', commit_sha + ':refs/heads/' + branch)
    info['parent'] = commit_sha
    lease.write_text(json.dumps(info))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=('restore', 'save'))
    parser.add_argument('--lane', choices=LANES, required=True)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--lease', type=Path, required=True)
    args = parser.parse_args()
    function = restore if args.operation == 'restore' else commit
    function(args.directory, args.lease, args.lane)


if __name__ == '__main__':
    main()
