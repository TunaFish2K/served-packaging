#!/usr/bin/env bash
# Runs as root only inside the disposable Arch container.
set -euo pipefail
# shellcheck source=scripts/ci-guard.sh
source "$(dirname "$0")/ci-guard.sh"
require_ci_container
cp -a /source/. /work
chown -R builder:builder /work
cd /work/aur/served-bin
runuser -u builder -- makepkg --printsrcinfo > /tmp/actual.SRCINFO
diff -u .SRCINFO /tmp/actual.SRCINFO
runuser -u builder -- makepkg --cleanbuild --noconfirm
mapfile -t packages < <(runuser -u builder -- makepkg --packagelist)
namcap PKGBUILD "${packages[@]}" | tee /tmp/namcap.log
if grep -q ' E: ' /tmp/namcap.log; then exit 1; fi
pacman -U --noconfirm "${packages[@]}"
[[ $(pacman -Qoq /usr/bin/served) == served-bin ]]
[[ $(pacman -Qoq /usr/lib/systemd/system/served@.service) == served-bin ]]
if pacman -Ql served-bin | grep -E ' /usr/local/| /etc/'; then exit 1; fi
ldd /usr/bin/served | tee /tmp/ldd.log
if grep -q 'not found' /tmp/ldd.log; then exit 1; fi
served version --output json
mandb -q
man -w served
man -w 5 served
systemd-analyze verify /usr/lib/systemd/system/served@.service
runuser -u builder -- python /work/tests/smoke.py
cp "${packages[@]}" /out/
cp /tmp/namcap.log /tmp/ldd.log /out/
