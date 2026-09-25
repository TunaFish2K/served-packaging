#!/usr/bin/env python3
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time


def wait(check):
    for _ in range(100):
        try:
            if check():
                return
        except (OSError, subprocess.CalledProcessError, json.JSONDecodeError):
            pass
        time.sleep(.1)
    raise AssertionError('timed out waiting for service')


with tempfile.TemporaryDirectory(prefix='served-pkg-', dir='/tmp') as root:
    home = Path(root)
    env = dict(os.environ, HOME=root)
    project = home / 'project'
    project.mkdir()
    def cli(*args):
        return subprocess.check_output(['/usr/bin/served', *args], env=env, cwd=project, stderr=subprocess.PIPE).decode()
    def services():
        return json.loads(cli('list', '--output=json'))['data']['services']
    def state(name, expected):
        return any(s['name'] == name and s['state'] == expected for s in services())
    daemon = subprocess.Popen(['/usr/bin/served', 'daemon'], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        wait(lambda: services() == [])
        cli('run', '--name', 'probe', '--no-tty', '--', 'sh', '-c', "printf 'package-ready\\n'; exec sleep 120")
        wait(lambda: state('probe', 'running'))
        wait(lambda: 'package-ready' in cli('history', 'probe', '--stdout'))
        cli('stop', 'probe')
        wait(lambda: state('probe', 'stopped'))
        cli('start', 'probe')
        wait(lambda: state('probe', 'running'))
        cli('disable', 'probe')
        (project / '.served.json5').write_text("{name:'persistent',command:'exec sleep 120',tty:false}")
        cli('enable')
        wait(lambda: state('persistent', 'running'))
        cli('shutdown')
        daemon.wait(timeout=15)
        daemon = subprocess.Popen(['/usr/bin/served', 'daemon'], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        wait(lambda: state('persistent', 'running'))
        cli('disable', 'persistent')
        # Run persistence is supported by JSON schema 2 and later releases.
        if json.loads(cli('version', '--output=json'))['schema_version'] >= 2:
            cli('run', '--name', 'persistent-run', '--no-tty', '--', 'sleep', '120')
            wait(lambda: state('persistent-run', 'running'))
            cli('shutdown')
            daemon.wait(timeout=15)
            daemon = subprocess.Popen(['/usr/bin/served', 'daemon'], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            wait(lambda: state('persistent-run', 'running'))
            cli('disable', 'persistent-run')
        print('CLI lifecycle, history and recovery passed')
    finally:
        subprocess.run(['/usr/bin/served', 'shutdown'], env=env, timeout=15, stdout=subprocess.DEVNULL)
        daemon.wait(timeout=15)
