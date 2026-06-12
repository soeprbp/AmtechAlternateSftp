# Security Notes

## Secrets

Do not commit SFTP usernames, passwords, private keys, tokens, or customer-specific
connection details. Use environment variables, local encrypted password files, or
hand-edited local deployment copies.

Expected environment variables:

- `AMTECH_ALTERNATE_SFTP_USERNAME`
- `AMTECH_ALTERNATE_SFTP_PASSWORD`
- `AMTECH_ALTERNATE_SFTP_TARGET`
- `AMTECH_ALTERNATE_SFTP_REMOTE_DIR`
- `AMTECH_ALTERNATE_SFTP_PORT`
- `AMTECH_ALTERNATE_SFTP_IDENTITY_FILE`

## Host Keys

Password-based SFTP uses strict host-key checking by default. Do not enable
`TrustNewHostKey` unless you have independently verified the SFTP server identity.

## Data Safety

This tool sends `.dat` files from the configured source root and moves those source
files to `Backup` as `.bak` files after a successful upload. Back up your data,
test with staging paths first, and verify that the source and backup paths are
correct before scheduled use. Do not point this bundle at an upstream `.cov`
working folder.

## Logs

Runtime logs are ignored by the bundle `.gitignore`. Do not publish generated logs
without reviewing them for customer names, file names, paths, hosts, or other
operational details.
