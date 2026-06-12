# Amtech Alternate SFTP

![Amtech Alternate SFTP logo](assets/amtech-alternate-sftp-logo.svg)

This bundle is a portable Amtech Alternate SFTP workflow.
It is designed to be easy to copy into a separate Git repository, review, and hand-edit
without touching any live production implementation.

Licensed under the MIT License.
See `DISCLAIMER.md` for the use-at-your-own-risk and backup-your-data notice.

## What It Does

- stages current `.dat` flat-file EDI documents from the configured source share
- sends them to the configured SFTP host and remote folder
- archives the originals to `Backup` as `.bak` files only after a successful send
- keeps the workflow intentionally narrow so it can serve as a temporary fallback

## File Types

- Send-ready files are `.dat` files in the configured source root.
- Current-mode uploads are limited to `EDIPOH.dat`, `EDIPOD.dat`, and `EDIITEM.dat`.
- Historical/archive files are `.bak` files under the source root's `Backup` folder.
- `.cov` files are not used by this bundle as SFTP send inputs.

## Files

- `Launch-AmtechAlternateSftp.ps1`
- `Register-AmtechAlternateSftpTasks.ps1`
- `amtech_alternate_sftp.py`
- `SETUP.md`
- `USAGE.md`
- `SECURITY.md`
- `LICENSE`
- `DISCLAIMER.md`
- `requirements.txt`

## Quick Start

Read `SETUP.md` first, then use `USAGE.md` for day-to-day operation.

## Before You Distribute Or Deploy

This repository is intentionally de-branded. Before using it at a new site, make
these values local to that site and do not commit the real values back to Git:

| Setting | Where to put it | Example placeholder |
| --- | --- | --- |
| Source folder containing final outbound files | `Launch-AmtechAlternateSftp.ps1` `SourceRoot` | `\\fileserver\share\edi\outbound` |
| SFTP username | `RemoteUsername` or `AMTECH_ALTERNATE_SFTP_USERNAME` | `edi_upload_user` |
| SFTP host | `RemoteHost` | `sftp.partner.example` |
| SFTP remote folder | `RemoteDir` | `/incoming` |
| SFTP port | `SftpPort` | `22` |
| SFTP password | Local encrypted file or `AMTECH_ALTERNATE_SFTP_PASSWORD` | Do not commit |
| Task schedule/name/end date | `Register-AmtechAlternateSftpTasks.ps1` | Site-specific |

Do not include Pushbullet, Pushover, SFTP, API, or other alerting credentials in
this repo. Keep them in environment variables, a local secret store, or a private
deployment-only copy.

## Notes

- The source share path and SFTP target are editable in the launcher script.
- The scheduled task names and password-file path are editable in the task installer.
- This bundle is intentionally separate from any live production implementation.
- Review `SECURITY.md` before publishing logs, defaults, or deployment-specific copies.
- Read `DISCLAIMER.md` before using the bundle in a real environment.
