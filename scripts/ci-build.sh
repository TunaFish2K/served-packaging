#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=scripts/ci-guard.sh
source scripts/ci-guard.sh
require_hosted_ci "${1:-}"
mkdir -p out
docker build -t served-packaging-check .
docker run --rm --env GITHUB_ACTIONS --env RUNNER_ENVIRONMENT --env RUNNER_OS \
    --env SERVED_CI_CONTAINER=true -v "$PWD:/source:ro" -v "$PWD/out:/out" \
    served-packaging-check bash /source/scripts/build.sh
