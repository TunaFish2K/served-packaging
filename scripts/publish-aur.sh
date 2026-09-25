#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ${AUR_PUBLISH_ENABLED:-false} != true ]]; then
    python3 scripts/publish_aur.py
    exit 0
fi
: "${AUR_SSH_PRIVATE_KEY:?Set the AUR_SSH_PRIVATE_KEY Actions secret before enabling publication}"
key_dir=$(mktemp -d)
trap 'rm -rf "$key_dir"' EXIT
chmod 700 "$key_dir"
printf '%s\n' "$AUR_SSH_PRIVATE_KEY" > "$key_dir/key"
chmod 600 "$key_dir/key"
unset AUR_SSH_PRIVATE_KEY
# Published on https://aur.archlinux.org/; a mismatch must be reviewed, never accepted silently.
ssh-keyscan -T 15 -t ed25519 aur.archlinux.org > "$key_dir/known_hosts" 2>/dev/null
fingerprint=$(ssh-keygen -lf "$key_dir/known_hosts" | awk '{print $2}')
[[ "$fingerprint" == 'SHA256:RFzBCUItH9LZS0cKB5UE6ceAYhBD5C8GeOBip8Z11+4' ]] || {
    echo 'AUR host key fingerprint changed; verify it against the official site.' >&2
    exit 1
}
export GIT_SSH_COMMAND="ssh -i $key_dir/key -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$key_dir/known_hosts"
python3 scripts/publish_aur.py
