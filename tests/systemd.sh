#!/usr/bin/env bash
# Runs inside a disposable systemd container, never on the developer host.
set -euo pipefail
# shellcheck source=scripts/ci-guard.sh
source "$(dirname "$0")/../scripts/ci-guard.sh"
require_ci_container
[[ ${container:-} == docker ]]
packages=(/packages/*.pkg.tar.zst)
pacman -U --noconfirm "${packages[@]}"
if systemctl is-active --quiet served@alice.service; then exit 1; fi
if systemctl is-active --quiet served@bob.service; then exit 1; fi
for user in alice bob; do
    install -d -o "$user" -g "$user" "/home/$user/project"
    printf '%s\n' "{name:'probe',command:'exec sleep 300',tty:false,persist_logs:true}" > "/home/$user/project/.served.json5"
    chown "$user:$user" "/home/$user/project/.served.json5"
done
cli() { runuser -u "$1" -- env HOME="/home/$1" /usr/bin/served "${@:2}"; }
wait_ready() {
    for ((i=0; i<100; i++)); do
        if cli "$1" list >/dev/null 2>&1; then return; fi
        sleep .1
    done
    return 1
}
systemctl start served@alice.service served@bob.service
wait_ready alice
wait_ready bob
cli alice enable --workdir /home/alice/project
cli bob enable --workdir /home/bob/project
systemctl stop served@bob.service
pid() { cli alice list --output json | python -c 'import json,sys; print(json.load(sys.stdin)["data"]["services"][0]["pid"])'; }
for ((i=0; i<100; i++)); do
    old_pid=$(pid)
    [[ "$old_pid" != None ]] && break
    sleep .1
done
[[ "$old_pid" != None ]]
old_manager=$(systemctl show -p MainPID --value served@alice.service)
pacman -U --noconfirm "${packages[@]}"
wait_ready alice
[[ $(pid) == "$old_pid" ]]
# Handoff re-execs the manager, so its PID may stay the same.
kill -0 "$old_pid"
if systemctl is-active --quiet served@bob.service; then exit 1; fi
[[ $(systemctl show -p MainPID --value served@alice.service) != 0 ]]
[[ "$old_manager" != 0 ]]
pacman -R --noconfirm served-bin
if systemctl is-active --quiet served@alice.service; then exit 1; fi
if kill -0 "$old_pid" 2>/dev/null; then exit 1; fi
[[ -e /home/alice/project/.served.json5 ]]
[[ -L /home/alice/.config/served/enabled/probe ]]
[[ -d /home/alice/.local/state/served/logs/probe ]]
echo 'systemd upgrade preserves service PID; removal stops instances and keeps user data'
