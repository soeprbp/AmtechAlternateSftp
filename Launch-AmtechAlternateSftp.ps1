<#
Amtech Alternate SFTP bundle

Licensed under the MIT License.

Dependencies:
- PowerShell 5.1 or later
- Python 3.10 or later
- Python package: paramiko (`python -m pip install paramiko`)
- Network access to the source EDI share and the outbound SFTP server
- Read `DISCLAIMER.md` before using this bundle on any real data

Editable settings:
- SourceRoot
- RemoteUsername
- RemoteHost
- RemoteDir
- SftpPort
- PasswordFile
- TrustNewHostKey
- StageOnly
#>

param(
    [switch]$StageOnly,
    [string]$SourceRoot = '\\server\share\path\to\amtech\edi\outbound',
    [string]$RemoteUsername = $env:AMTECH_ALTERNATE_SFTP_USERNAME,
    [string]$RemoteHost = 'sftp.example.com',
    [string]$StagingRoot = (Join-Path $PSScriptRoot 'staging'),
    [string]$LogDir = (Join-Path $PSScriptRoot 'logs'),
    [string]$RemoteDir = '/remote/folder',
    [int]$SftpPort = 22,
    [string]$PasswordFile = (Join-Path $env:LOCALAPPDATA 'AmtechAlternateSftp\amtech_alternate_sftp_password.xml'),
    [string]$PasswordEnvVar = 'AMTECH_ALTERNATE_SFTP_PASSWORD',
    [bool]$TrustNewHostKey = $false
)

$ErrorActionPreference = 'Stop'

$bundleRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $bundleRoot

# This launcher only wires the site-specific settings into the Python worker.
if (-not $RemoteUsername) {
    throw 'Set AMTECH_ALTERNATE_SFTP_USERNAME or edit Launch-AmtechAlternateSftp.ps1.'
}

$RemoteTarget = '{0}@{1}' -f $RemoteUsername, $RemoteHost

if (-not $StageOnly) {
    if (Test-Path -LiteralPath $PasswordFile) {
        $secureString = Import-Clixml -LiteralPath $PasswordFile
        $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureString)
        try {
            Set-Item -Path "Env:$PasswordEnvVar" -Value ([System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr))
        }
        finally {
            if ($bstr -ne [IntPtr]::Zero) {
                [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
            }
        }
    }

    if (-not (Test-Path -Path "Env:$PasswordEnvVar")) {
        throw "Missing SFTP password. Set $PasswordEnvVar or create $PasswordFile."
    }
}

$arguments = @(
    'amtech_alternate_sftp.py',
    '--source-root',
    $SourceRoot,
    '--staging-root',
    $StagingRoot,
    '--log-dir',
    $LogDir,
    '--mode',
    'current',
    '--sftp-target',
    $RemoteTarget,
    '--sftp-port',
    "$SftpPort",
    '--remote-dir',
    $RemoteDir,
    '--sftp-password-env',
    $PasswordEnvVar
)

if ($TrustNewHostKey) {
    $arguments += '--trust-new-host-key'
}

if (-not $StageOnly) {
    $arguments += '--send-sftp'
    $arguments += '--archive-source-after-send'
}

python @arguments
