# Moving from the served online installer

The Arch package owns `/usr/bin/served` and `/usr/lib/systemd/system/served@.service`.
It never removes files installed manually in `/usr/local` or `/etc`.

An old `/usr/local/bin/served` can take precedence in PATH. An old
`/etc/systemd/system/served@.service` overrides the packaged template.

1. List your instances with `systemctl list-units --all 'served@*.service'`.
2. Inspect `systemctl cat served@USERNAME.service` and record enabled/active states.
3. In a maintenance window, stop affected instances. This stops their managed services.
   On releases before persistent run support, recreate `served run` services afterward;
   save their commands, options and environment before stopping.
4. Back up and remove only the old files you own in `/usr/local/bin/served` and
   `/etc/systemd/system/served@.service`. Review instance-specific overrides separately.
5. Run `sudo systemctl daemon-reload`, verify `command -v served` resolves to
   `/usr/bin/served`, and inspect the unit again.
6. Restore the previously active instances. Enable additional instances explicitly with
   `sudo systemctl enable --now served@USERNAME.service`.

Keep all user configuration, runtime records and logs. Do not invoke the upstream
uninstaller after moving to package-managed files. Subsequent pacman upgrades reload
active package-managed instances via handoff. Stopped instances stay stopped.

Removing the package stops active package-managed instances but leaves user data intact.
