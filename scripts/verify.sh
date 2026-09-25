#!/usr/bin/env bash
# Local entrypoint: no containers, package installs, or system service operations.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m unittest discover -s tests -v
shellcheck scripts/*.sh scripts/ci-bin/makepkg aur/served-bin/served-pacman tests/systemd.sh
actionlint
echo 'Local static checks passed; container and systemd validation run only on GitHub-hosted CI.'
