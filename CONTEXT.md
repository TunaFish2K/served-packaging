# Packaging decisions

- Upstream: TunaFish2K/served. This repository owns downstream packaging only.
- Initial target: AUR served-bin, full variant, Linux x86_64. No source package,
  headless split, ARM package or other distribution repository in this iteration.
- Stable release discovery polls hourly, requires a successful upstream release
  workflow and complete verified assets. No upstream workflow change is required.
- AUR publication is automatic after validation, but disabled until the owner registers
  an AUR account and supplies a dedicated SSH key. No key is generated or stored in Git.
- Initial baseline is the latest successful release, v0.15.1. At setup time the v0.15.2
  release workflow failed a macOS test and no v0.15.2 Release was published.
- Package installs files directly rather than invoking the upstream installer.
  First install opts in no users. Upgrade handoff and removal stop affect only active
  instances using the packaged vendor unit. User files remain untouched.
- GitHub and AUR have separate histories. AUR updates are idempotent and refuse unknown
  remote changes. A failed AUR push is retried even if the upstream version is unchanged.

## Test boundary after the desktop incident

- Do not run privileged systemd containers on developer machines or self-hosted runners.
- Local verification is static checks and mocked unit tests only. All Docker operations
  belong in GitHub-hosted disposable CI VMs, with separate build and systemd jobs.
- Environment guards prevent accidental execution; they are not security boundaries.
- The build image defaults to bash. Systemd is started explicitly only by the CI test.
- Cleanup is limited to containers created by this task. Never use global Docker prune.
