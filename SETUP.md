# Setup

## Requirements

- Windows with PowerShell 5.1 or later
- Python 3.10 or later
- Python package: `paramiko`
- Access to the source EDI share
- Outbound network access to the SFTP host
- Read `DISCLAIMER.md` before using the bundle on any real data

The configured source folder should contain the send-ready `.dat` files. This
bundle does not process `.cov` files.

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

## Configure Credentials

Either:

1. Save the password into the local encrypted password file path used by the launcher, or
2. Set `AMTECH_ALTERNATE_SFTP_PASSWORD` in the current session.

If the username is not already set in the launcher, set `AMTECH_ALTERNATE_SFTP_USERNAME` in the current session as well.

The repository should not contain the cleartext password.

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
