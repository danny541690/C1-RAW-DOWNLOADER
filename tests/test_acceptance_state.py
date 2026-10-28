import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from scripts import v093_acceptance_state as durable
from scripts.v093_acceptance_scheduler import load, save


class DurableStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Path(self.tmp.name)
        self.git('init', '--bare', str(self.p / 'remote.git'))
        self.repo = self.p / 'repo'
        self.git('init', str(self.repo))
        self.git('-C', str(self.repo), 'remote', 'add', 'origin', str(self.p / 'remote.git'))
        self.old_cwd = Path.cwd()
        os.chdir(self.repo)
        self.addCleanup(os.chdir, self.old_cwd)

    def git(self, *args):
        return subprocess.run(['git', *args], check=True, capture_output=True)

    def test_state_survives_fresh_working_directory_without_source_files(self):
        first, lease = self.p / 'first', self.p / 'lease.json'
        durable.restore(first, lease, 'worker-0')
        save(first / 'worker.json.gz', {'schema': 'test', 'completed': ['retained-sha']})
        durable.commit(first, lease, 'worker-0')
        second = self.p / 'second'
        durable.restore(second, self.p / 'lease-2.json', 'worker-0')
        self.assertEqual(load(second / 'worker.json.gz')['completed'], ['retained-sha'])
        self.assertEqual([p.name for p in second.iterdir()], ['worker.json.gz'])
        branches = self.git('ls-remote', '--heads', 'origin').stdout.decode()
        self.assertIn('refs/heads/jarvis-acceptance-state/worker-0', branches)
        self.assertNotIn('refs/heads/main', branches)

    def test_competing_writer_never_overwrites_newer_checkpoint(self):
        a, la = self.p / 'a', self.p / 'la.json'
        durable.restore(a, la, 'worker-1')
        save(a / 'worker.json.gz', {'generation': 1})
        durable.commit(a, la, 'worker-1')
        b, lb, c, lc = self.p / 'b', self.p / 'lb.json', self.p / 'c', self.p / 'lc.json'
        durable.restore(b, lb, 'worker-1')
        durable.restore(c, lc, 'worker-1')
        save(b / 'worker.json.gz', {'generation': 2})
        durable.commit(b, lb, 'worker-1')
        save(c / 'worker.json.gz', {'generation': 'stale'})
        with self.assertRaises(subprocess.CalledProcessError):
            durable.commit(c, lc, 'worker-1')
        d = self.p / 'd'
        durable.restore(d, self.p / 'ld.json', 'worker-1')
        self.assertEqual(load(d / 'worker.json.gz')['generation'], 2)

    def test_cross_worker_lease_is_rejected(self):
        a, lease = self.p / 'a', self.p / 'lease.json'
        durable.restore(a, lease, 'worker-0')
        save(a / 'worker.json.gz', {'generation': 1})
        with self.assertRaisesRegex(ValueError, 'STATE_BRANCH_SCOPE'):
            durable.commit(a, lease, 'worker-2')

    def test_multiple_saves_advance_lease_and_identical_save_is_noop(self):
        a, lease = self.p / 'a', self.p / 'lease.json'
        durable.restore(a, lease, 'worker-2')
        save(a / 'worker.json.gz', {'generation': 1})
        durable.commit(a, lease, 'worker-2')
        first = lease.read_text()
        save(a / 'worker.json.gz', {'generation': 1})
        durable.commit(a, lease, 'worker-2')
        self.assertEqual(first, lease.read_text())
        save(a / 'worker.json.gz', {'generation': 2})
        durable.commit(a, lease, 'worker-2')
        self.assertNotEqual(first, lease.read_text())


if __name__ == '__main__':
    unittest.main()
