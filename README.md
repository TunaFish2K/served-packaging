# served packaging

Distribution packaging for [TunaFish2K/served](https://github.com/TunaFish2K/served).
The first package is **served-bin**, the official full Linux x86_64 binary repackaged
for Arch Linux. This repository does not compile served or change its source.

**AUR publication starts disabled.** The GitHub workflow validates packages and updates
this repository. An AUR account and dedicated SSH key are required before publishing.
Do not assume `yay -S served-bin` is available until the first AUR push succeeds.

## Automated updates

The `AUR package` workflow checks every hour at minute 37. It also supports manual
runs, an explicit stable tag, a check-only mode, and packaging refreshes.

1. Read the upstream latest non-draft stable release and resolve its tag commit.
2. Require the latest release workflow attempt for that commit to have succeeded.
3. Require the full x86_64 archive and SHA-256 sidecar, download both and compare.
4. Update fixed URLs/checksums in `PKGBUILD`; generate `.SRCINFO` with `makepkg`.
5. Build as an ordinary user in an Arch container. Check with namcap, install the
   package, exercise CLI operations, and test systemd upgrade/removal separately.
6. Commit a changed recipe to this repository and, when enabled, export it to AUR.

Every publishing run validates the candidate, even when its version is unchanged.
Unchanged recipes create no new package commit. This also lets failed AUR pushes retry.
Generated `.pkg.tar.zst` files and diagnostics are retained as Actions artifacts for
14 days. AUR receives only the recipe, metadata and package helper files.

Automatic downgrades and same-version archive replacements fail for investigation.
A missing or failed upstream release does not advance the package. New upstream
versions start at `pkgrel=1`; `refresh` increments it for packaging-only changes.
AUR history is separate from this repository. Unknown remote changes are never
force-pushed over. If a push succeeds but recording its revision fails, the next run
recognizes identical contents and records the revision without creating another commit.

GitHub schedules can be delayed. Public repositories with no activity for 60 days may
have schedules disabled: check the Actions page and re-enable scheduling if necessary.
Use a manual run for an immediate update. See [GitHub event documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

## Package behavior

- Binary: `/usr/bin/served`; template: `/usr/lib/systemd/system/served@.service`.
- Manuals: `/usr/share/man`; skill: `/usr/share/served/skills/served`.
- No instance is enabled or started during first installation.
- To opt in: `sudo systemctl enable --now served@USERNAME.service` (not root).
- Upgrades hand off active package-managed instances; stopped instances stay stopped.
  Handoff failures report diagnostics, without automatically restarting the business
  services. Inspect `systemctl status` and `journalctl` before a controlled restart.
- Removal stops active package-managed instances and retains user configuration,
  registry records and logs. If stopping fails, the pre-removal hook aborts removal.
- Manually installed units are skipped by the package hooks. See
  [migration instructions](aur/served-bin/MIGRATION.md) for `/usr/local` and `/etc` conflicts.

`run` recovery behavior follows the upstream version. Tests exercise persistent run
recovery when the installed release advertises JSON schema 2 or later; older releases
are tested for enabled-service recovery instead.

## Enable AUR publication

1. Register at https://aur.archlinux.org/ and verify `served-bin` is available, or that
   your account owns/co-maintains it. The GitHub username does not create an AUR account.
2. Generate a dedicated Ed25519 key locally. Add its public key to your AUR account.
   Store the private key in the **AUR_SSH_PRIVATE_KEY** Actions secret of this repository.
   Never put a private key in Git or in an issue.
3. Set the repository Actions variable **AUR_PUBLISH_ENABLED** to `true`.
4. Run `AUR package` manually with `check_only=false`. Inspect the publication summary
   and the new AUR package page. No manual approval is required on subsequent updates.

The SSH host fingerprint is pinned to the Ed25519 fingerprint published on the
[AUR homepage](https://aur.archlinux.org/). A host-key change fails until verified.
Only the publication job receives the SSH secret; pull requests only validate.
The publication job rejects an obsolete GitHub checkout and pushes without force.

To pause AUR publication, set the variable to `false`. GitHub validation continues.
If an external maintainer changes AUR, reconcile the recipe and remote history manually,
then update `aur/served-bin/aur-published.json` with the reviewed remote commit.

## Local checks

Install Python 3, Git, shellcheck and actionlint, then run:

```sh
scripts/verify.sh
```

This entrypoint runs unit tests, validates workflow/shell syntax and checks recipe
metadata without executing PKGBUILD. It does not start containers, install packages
or call the host system manager. Hook tests replace systemctl with a local mock.

## CI execution boundary

All container work runs on GitHub-hosted `ubuntu-24.04` runners. The workflow has four
stages: static checks, ordinary Arch package build/install, systemd integration, and
publication. Both package and systemd checks must pass before publication.

The build image defaults to a shell, never systemd. Full systemd testing uses a
privileged Arch container **only inside the disposable GitHub-hosted VM**. A privileged
container can affect its host's devices; private cgroups do not isolate that risk.
Never run this test on a desktop or a self-hosted runner.

CI entrypoints require `--ci-only`, `GITHUB_ACTIONS=true`,
`RUNNER_ENVIRONMENT=github-hosted`, and `RUNNER_OS=Linux`. Container-internal scripts
also require an explicit CI container marker. These checks prevent accidental local
execution; environment variables are not a security boundary. Do not spoof them locally.

The systemd job waits for the actual control interface, has bounded startup/test
execution, and exports journal/container logs before removing its test container.
It mounts no host devices, cgroup filesystem or Docker socket. The surrounding disposable
VM, not the privileged container alone, separates this test from a developer workstation.

For an update, trigger `AUR package` in GitHub Actions. Use `check_only` to validate
without publishing; use `refresh` after local packaging changes to bump `pkgrel`.
An Arch maintainer can instead run `python3 scripts/update.py --refresh` with native
makepkg, but the default local verification never invokes makepkg.

`GH_TOKEN` is optional for public API discovery locally. The Docker makepkg wrapper
is restricted to hosted CI. See [the incident record](docs/INCIDENT-2026-09-25.md) for
why these boundaries are enforced.
