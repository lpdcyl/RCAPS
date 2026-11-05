# RCAPS experiment backup (2026-11-05)

This backup supplements Git commit `377aed8313e98d3d33318a3750ce783c490814e8` and later branch history. The GitHub Release tagged `experiment-backup-20261105` holds 12 ZIP assets containing 2,163 previously untracked local experiment files (15,546,127,406 source bytes). The [manifest](manifest.json) lists each path, size, SHA256, provenance label, and archive.

The archive includes failed and diagnostic run artifacts so that evidence is not lost. A `recorded_sidecar_sha256` label means a compressed trace matched the SHA256 in its neighboring `result.json`. An `unverified_sidecar` label means that reference was absent or differed; these files are preserved as forensic evidence and must not be counted as successful formal results. Independent replay outcomes remain separate from formal five-seed groups.

To restore after reinstall:

1. Clone `https://github.com/lpdcyl/RCAPS.git` and check out branch `codex/work3-upload-20261024` (or tag `experiment-backup-20261105`).
2. Download all 12 `rcaps-experiments-*.zip` assets from the [backup Release](https://github.com/lpdcyl/RCAPS/releases/tag/experiment-backup-20261105).
3. Confirm each archive's SHA256 against `manifest.json` (`assets[].sha256`). Extract every archive into the repository root, preserving paths.
4. Run `python backup_20261105/backup.py verify-local`. It checks every restored file against the manifest.

The Release and this manifest are the backup pair. A Git clone by itself does not contain the large ZIP assets.
