<#
Amtech Alternate SFTP scheduled-task helper

Licensed under the MIT License.

Dependencies:
- PowerShell 5.1 or later
- A saved password in $PasswordFile, or AMTECH_ALTERNATE_SFTP_PASSWORD in the current session
- Permission to create Windows scheduled tasks for the current user

Editable settings:
- LauncherPath
- TaskNamePrefix
- PasswordFile
- EndDate
#>

param(
    [string]$PasswordFile = (Join-Path $env:LOCALAPPDATA 'AmtechAlternateSftp\amtech_alternate_sftp_password.xml'),
    [string]$TaskNamePrefix = 'AmtechAlternateSftp',
    [string]$LauncherPath = (Join-Path $PSScriptRoot 'Launch-AmtechAlternateSftp.ps1'),
    [datetime]$EndDate = (Get-Date '2026-07-03 23:59:59')
)

$ErrorActionPreference = 'Stop'

$bundleRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $bundleRoot

if (-not $env:AMTECH_ALTERNATE_SFTP_PASSWORD) {
    throw 'Set AMTECH_ALTERNATE_SFTP_PASSWORD before running this installer so the encrypted password file can be created.'
}

$passwordDirectory = Split-Path -Parent $PasswordFile
New-Item -ItemType Directory -Force -Path $passwordDirectory | Out-Null

$securePassword = ConvertTo-SecureString $env:AMTECH_ALTERNATE_SFTP_PASSWORD -AsPlainText -Force
$securePassword | Export-Clixml -LiteralPath $PasswordFile

$launcherResolved = (Resolve-Path -LiteralPath $LauncherPath).Path
# Register per-user hidden tasks for unattended local operation.
$taskUser = "$env:USERDOMAIN\$env:USERNAME"
$principal = New-ScheduledTaskPrincipal -UserId $taskUser -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -Hidden -StartWhenAvailable -MultipleInstances IgnoreNew

$timeSpecs = @(
    @{ Suffix = '0815'; At = [datetime]'08:15' },
    @{ Suffix = '1200'; At = [datetime]'12:00' },
    @{ Suffix = '1610'; At = [datetime]'16:10' }
)

foreach ($spec in $timeSpecs) {
    $taskName = "$TaskNamePrefix-$($spec.Suffix)"
    $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument (
        '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}" -PasswordFile "{1}"' -f $launcherResolved, $PasswordFile
    )
    $trigger = New-ScheduledTaskTrigger -Daily -At $spec.At
    $trigger.EndBoundary = $EndDate.ToString('s')

    if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }

    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal | Out-Null
    Write-Host "Registered $taskName"
}

Write-Host "Password file: $PasswordFile"
