#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=scripts/ci-guard.sh
source scripts/ci-guard.sh
require_hosted_ci "${1:-}"
mkdir -p out/systemd
name="served-packaging-test-${GITHUB_RUN_ID:?}-${GITHUB_RUN_ATTEMPT:?}"
cleanup() {
    local result=$?
    docker logs "$name" > out/systemd/container.log 2>&1 || true
    docker exec "$name" journalctl --no-pager -n 400 > out/systemd/journal.log 2>&1 || true
    docker rm -f "$name" >/dev/null 2>&1 || true
    exit "$result"
}
trap cleanup EXIT
docker build -t served-packaging-check .
# Privileged systemd is confined to a disposable GitHub-hosted VM. NEVER run locally.
docker run -d --name "$name" --privileged --cgroupns=private \
    --tmpfs /run --tmpfs /run/lock --env container=docker \
    --env GITHUB_ACTIONS --env RUNNER_ENVIRONMENT --env RUNNER_OS --env SERVED_CI_CONTAINER=true \
    -v "$PWD/out:/packages:ro" -v "$PWD/tests:/tests:ro" -v "$PWD/scripts:/scripts:ro" \
    served-packaging-check /usr/lib/systemd/systemd --log-target=console >/dev/null
ready=false
for ((i=0; i<60; i++)); do
    if docker exec "$name" systemctl list-units --no-pager >/dev/null 2>&1; then
        ready=true
        break
    fi
    sleep 1
done
[[ "$ready" == true ]] || { echo 'systemd control interface did not become ready' >&2; exit 1; }
timeout 180 docker exec "$name" bash /tests/systemd.sh
