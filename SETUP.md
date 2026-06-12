# Setup

## Requirements

- Windows with PowerShell 5.1 or later
- Python 3.10 or later
- Python package: `paramiko`
- Access to the source EDI share
- Outbound network access to the SFTP host
- Read `DISCLAIMER.md` before using the bundle on any real data

The configured source folder should contain the send-ready `EDIPOH.dat`,
`EDIPOD.dat`, and `EDIITEM.dat` files. This bundle does not process `.cov`
files.

Install the Python dependency:

```powershell
python -m pip install -r requirements.txt
```

## Edit The Launcher

Open `Launch-AmtechAlternateSftp.ps1` and update the editable settings near the top:

- `SourceRoot`
- `RemoteUsername`
- `RemoteHost`
- `RemoteDir`
- `SftpPort`
- `PasswordFile`
- `PasswordEnvVar`
- `TrustNewHostKey`

The launcher contains the most common hand-edit points for a new site.

## What Each Site Must Customize

Use placeholder values in Git and put real deployment values only in the local
copy that will run the job.

| Setting | Purpose | Safe example |
| --- | --- | --- |
| `SourceRoot` | Folder where the middleware leaves final send-ready `EDIPOH.dat`, `EDIPOD.dat`, and `EDIITEM.dat` files. | `\\fileserver\share\edi\outbound` |
| `RemoteUsername` | SFTP login name. Can be set directly or through `AMTECH_ALTERNATE_SFTP_USERNAME`. | `edi_upload_user` |
| `RemoteHost` | Partner or gateway SFTP host. | `sftp.partner.example` |
| `RemoteDir` | Remote folder where files should be uploaded. | `/incoming` |
| `SftpPort` | SFTP port supplied by the partner or gateway. | `22` |
| `PasswordFile` | Local encrypted Windows credential cache. | `%LOCALAPPDATA%\AmtechAlternateSftp\amtech_alternate_sftp_password.xml` |
| `PasswordEnvVar` | Environment variable read by the launcher for the SFTP password. | `AMTECH_ALTERNATE_SFTP_PASSWORD` |
| `TrustNewHostKey` | Emergency-only option for first connection to an untrusted host key. | `$false` |

Do not point `SourceRoot` at a middleware working folder that still contains
`.cov` files. Current-mode sends only the expected final `.dat` files and
archives them as `.bak` after a successful upload.

## Configure Credentials

Either:

1. Save the password into the local encrypted password file path used by the launcher, or
2. Set `AMTECH_ALTERNATE_SFTP_PASSWORD` in the current session.

If the username is not already set in the launcher, set `AMTECH_ALTERNATE_SFTP_USERNAME` in the current session as well.

The repository should not contain the cleartext password.

Do not store Pushbullet, Pushover, API-token, SFTP, or other alerting credentials
in this repository. If a local deployment adds notifications, keep those secrets
outside Git and document only the environment variable names.

## Host Key Verification

Password-based SFTP uses strict host-key checking by default. That means the SFTP
server host key must already be trusted by the Windows user running the job.

For an emergency first connection, the launcher has a `TrustNewHostKey` setting.
Only set it to `$true` after you have confirmed the server identity through an
approved channel, then set it back to `$false`.

## Optional Scheduled Tasks

If you want the three daily hidden tasks, run `Register-AmtechAlternateSftpTasks.ps1` after setting the username and password environment variables in the current session.
For scheduled runs, either hand-edit `RemoteUsername` in the launcher or set `AMTECH_ALTERNATE_SFTP_USERNAME` as a persistent user environment variable.

The defaults register runs at:

- 8:15 AM
- 12:00 PM
- 4:10 PM

Edit the task names, launcher path, or end date inside that script if needed.

## First-Run Checklist

1. Install Python and run `python -m pip install -r requirements.txt`.
2. Edit `Launch-AmtechAlternateSftp.ps1` with site-specific source and SFTP settings.
3. Confirm the source folder contains final `EDIPOH.dat`, `EDIPOD.dat`, and `EDIITEM.dat` files, not upstream `.cov` files.
4. Set the username and password locally through environment variables or the encrypted password file.
5. Run `.\Launch-AmtechAlternateSftp.ps1 -StageOnly`.
6. Review `staging` and `logs` to confirm the expected files are selected.
7. Test against a non-production SFTP target if one is available.
8. Run the normal launcher once under supervision.
9. Register scheduled tasks only after manual testing is clean.
10. Review the repo with `git status` and do not commit credentials, logs, or site-specific secrets.
