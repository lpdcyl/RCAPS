# RCAPS experiment backup (2026-11-05)

This backup supplements Git commit `377aed8313e98d3d33318a3750ce783c490814e8` and later branch history. The [main manifest](manifest.json) lists 2,163 previously untracked local experiment files (15,546,127,406 source bytes), including each path, size, SHA256, and provenance label. The [main recovery map](shard_main_manifest.json) records the original ZIP assets verified on GitHub and smaller replacement assets for the rest.

The archive includes failed and diagnostic run artifacts so that evidence is not lost. A `recorded_sidecar_sha256` label means a compressed trace matched the SHA256 in its neighboring `result.json`. An `unverified_sidecar` label means that reference was absent or differed; these files are preserved as forensic evidence and must not be counted as successful formal results. Independent replay outcomes remain separate from formal five-seed groups.

To restore after reinstall:

1. Clone `https://github.com/lpdcyl/RCAPS.git` and check out branch `codex/work3-upload-20261024`.
2. Download every ZIP asset listed in `shard_main_manifest.json` under `existing_assets` and `assets` from the [main Release](https://github.com/lpdcyl/RCAPS/releases/tag/experiment-backup-20261105).
3. Confirm each archive's SHA256 against the corresponding asset entry. Extract every archive into the repository root, preserving paths.
4. Run `python backup_20261105/backup.py verify-local`. It checks every restored file against the manifest.

The Release assets and the manifests are the backup pair. A Git clone by itself does not contain the large ZIP assets.

## Ignored V3 raw event streams

An additional [supplemental Release](https://github.com/lpdcyl/RCAPS/releases/tag/experiment-backup-20261105-v3-raw) holds 3,859 files (22,032,044,593 source bytes) excluded by nested `.gitignore` rules, primarily V3 `.jsonl.gz` event streams, plus run logs and seven JSON indexes. Its [separate manifest](ignored_manifest.json) lists the files; the [V3 recovery map](shard_v3_manifest.json) lists the original ZIP assets. The [tail recovery map](tail_v3_manifest.json) identifies complete ZIP assets and binary parts for the remaining ZIPs. The `trace_sha256` field in adjacent V3 result JSON describes the **input trace**, so it is not used as a digest of the raw event stream; each stream has its own SHA256 in the supplemental manifest.

Download the ZIP assets listed in `shard_v3_manifest.json` under `existing_assets` and in `tail_v3_manifest.json` under `existing_shard_assets` from the supplemental Release. Verify each downloaded asset against its listed size and SHA256. The remaining 11 ZIPs are reconstructed from binary parts tracked on the backup branch: the first 32 parts are in `backup_20261105/git_parts/`, and the final 15 are represented by 61 smaller files in `backup_20261105/git_small_parts/` according to `small_parts_manifest.json`. Run `python backup_20261105/push_git_small_parts.py restore`, then `python backup_20261105/backup_tail.py restore`. Extract all ZIPs into the repository root, preserving paths. Finally run `python backup_20261105/backup_ignored.py verify-local`.

## Paper and reviewer documents

The three user-requested files are tracked directly under [documents](documents). Their exact byte sizes and SHA256 values are in [documents_manifest.json](documents_manifest.json). They are present in a clone of the backup branch and do not require Release downloads.
