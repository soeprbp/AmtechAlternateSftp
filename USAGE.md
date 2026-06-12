# Usage

## Manual Run

Use the launcher from the bundle folder:

```powershell
.\Launch-AmtechAlternateSftp.ps1
```

That command:

1. Reads the current `.dat` files from the configured source share.
2. Uploads them to the configured SFTP location.
3. Renames the originals to `.bak` and moves them into `Backup` after a successful send.
4. Assumes you have already backed up anything you cannot afford to lose.

The bundle intentionally ignores `.cov` files. If upstream middleware creates both
`.cov` and `.dat` artifacts, point `SourceRoot` at the folder containing the final
send-ready `EDIPOH.dat`, `EDIPOD.dat`, and `EDIITEM.dat` files.

## Stage-Only Run

If you want to stage and inspect without sending:

```powershell
.\Launch-AmtechAlternateSftp.ps1 -StageOnly
```

## Task Registration

To create the hidden daily tasks, run:

```powershell
.\Register-AmtechAlternateSftpTasks.ps1
```

## What To Edit Later

If a new site needs a different source share, SFTP host, or remote directory, edit
`Launch-AmtechAlternateSftp.ps1` and, if needed, the task installer.

If you only need to update the schedule or the launcher path, edit `Register-AmtechAlternateSftpTasks.ps1`.

Do not put real SFTP passwords, Pushbullet tokens, Pushover tokens, or API keys
in the repo. Use local environment variables or a local encrypted password file.

Read `DISCLAIMER.md` before treating the bundle as anything other than a temporary operational copy.
