import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BoundaryTests(unittest.TestCase):
    def test_ci_entrypoints_refuse_local_and_self_hosted_before_commands(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            marker = directory / 'executed'
            for name in ['docker', 'systemctl', 'pacman', 'sudo', 'runuser', 'chown', 'cp']:
                path = directory / name
                path.write_text(f'#!/bin/sh\necho called >> "{marker}"\nexit 99\n')
                path.chmod(0o755)
            for entry in ['scripts/ci-build.sh', 'scripts/ci-systemd.sh', 'scripts/ci-bin/makepkg', 'scripts/build.sh', 'tests/systemd.sh']:
                for hosted in ['', 'self-hosted']:
                    env = dict(os.environ, PATH=f'{temp}:' + os.environ['PATH'],
                               GITHUB_ACTIONS='true' if hosted else '', RUNNER_ENVIRONMENT=hosted, RUNNER_OS='Linux')
                    result = subprocess.run(['/bin/bash', str(ROOT / entry), '--ci-only'], env=env, capture_output=True, text=True)
                    self.assertNotEqual(result.returncode, 0, entry)
                    self.assertIn('Refusing container tests', result.stderr)
                    self.assertFalse(marker.exists(), entry)
            # Missing explicit opt-in also refuses a hosted-looking environment.
            env.update(GITHUB_ACTIONS='true', RUNNER_ENVIRONMENT='github-hosted')
            result = subprocess.run(['/bin/bash', str(ROOT / 'scripts/ci-systemd.sh')], env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(marker.exists())

    def test_local_entrypoint_and_image_do_not_start_containers_or_init(self):
        text = (ROOT / 'scripts/verify.sh').read_text()
        self.assertNotRegex(text, r'(?m)^\s*(docker|sudo|systemctl|pacman)\b')
        self.assertIn('CMD ["/usr/bin/bash"]', (ROOT / 'Dockerfile').read_text())

    def test_hook_failure_does_not_restart_services_and_skips_manual_units(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            log = directory / 'calls'
            mock = directory / 'systemctl'
            mock.write_text('''#!/bin/bash
printf '%s\\n' "$*" >> "$CALL_LOG"
case "$1" in
  list-units)
    [[ ${FAIL_LIST:-} != true ]] || exit 1
    printf 'served@alice.service loaded active running\\nserved@bob.service loaded active running\\n';;
  show)
    if [[ "$*" == *alice* ]]; then echo /usr/lib/systemd/system/served@.service
    else echo /etc/systemd/system/served@.service; fi;;
  reload|stop) exit 1;;
  *) exit 99;;
esac
''')
            mock.chmod(0o755)
            hook = directory / 'hook'
            hook.write_text((ROOT / 'aur/served-bin/served-pacman').read_text().replace('[[ -d /run/systemd/system ]] || exit 0', ': # test fixture supplies a mocked system manager'))
            env = dict(os.environ, PATH=f'{temp}:' + os.environ['PATH'], CALL_LOG=str(log))
            for operation in ['reload', 'stop']:
                result = subprocess.run(['/bin/bash', str(hook), operation], env=env, capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Skipping served@bob.service', result.stderr)
                calls = log.read_text()
                self.assertIn(f'{operation} served@alice.service', calls)
                self.assertNotIn(f'{operation} served@bob.service', calls)
                self.assertNotIn('restart ', calls)
                log.unlink()
            result = subprocess.run(['/bin/bash', str(hook), 'reload'], env=dict(env, FAIL_LIST='true'), capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn('reload ', log.read_text())
