<#
.SYNOPSIS
    Puts the Flutter, Android SDK and JDK toolchain on PATH for this shell.

.DESCRIPTION
    Dot-source this - note the leading dot and space - so the changes apply to
    your current shell rather than a child process that exits immediately:

        . .\scripts\dev-env.ps1

    Running it as `.\scripts\dev-env.ps1` appears to work and then leaves your
    shell exactly as it was, which is a confusing five minutes.

    Nothing is installed or modified. Only this shell's environment changes;
    open a new window and it is gone.

.PARAMETER DevRoot
    Where the toolchain lives. Defaults to <your profile>\dev, which is where
    flutter, android-sdk and jdk were installed on this machine.

.EXAMPLE
    . .\scripts\dev-env.ps1
    flutter devices
#>
[CmdletBinding()]
param(
    [string]$DevRoot = (Join-Path $env:USERPROFILE 'dev')
)

$ErrorActionPreference = 'Stop'

function Write-Step($message) { Write-Host "  $message" }
function Write-Warn($message) { Write-Host "  ! $message" -ForegroundColor Yellow }

if (-not (Test-Path $DevRoot)) {
    Write-Warn "No toolchain directory at $DevRoot."
    Write-Warn "Pass -DevRoot with the path where flutter/android-sdk/jdk live."
    return
}

# --- JDK: pick the highest version present, rather than a pinned path that
# --- breaks silently the next time it is updated.
$jdkRoot = Join-Path $DevRoot 'jdk'
if (Test-Path $jdkRoot) {
    $jdk = Get-ChildItem $jdkRoot -Directory |
        Where-Object { Test-Path (Join-Path $_.FullName 'bin\java.exe') } |
        Sort-Object Name -Descending |
        Select-Object -First 1
    if ($jdk) {
        $env:JAVA_HOME = $jdk.FullName
        Write-Step "JAVA_HOME  = $env:JAVA_HOME"
    } else {
        Write-Warn "No JDK with bin\java.exe found under $jdkRoot"
    }
} else {
    Write-Warn "No jdk directory at $jdkRoot"
}

# --- Android SDK
$sdk = Join-Path $DevRoot 'android-sdk'
if (Test-Path $sdk) {
    $env:ANDROID_HOME = $sdk
    # Some tooling still reads the older name; set both so neither surprises you.
    $env:ANDROID_SDK_ROOT = $sdk
    Write-Step "ANDROID_HOME = $sdk"
} else {
    Write-Warn "No Android SDK at $sdk"
}

# --- PATH. Prepended so these win over any other copy already installed, and
# --- de-duplicated so repeated dot-sourcing does not grow PATH without bound.
$wanted = @(
    (Join-Path $DevRoot 'flutter\bin'),
    (Join-Path $sdk 'platform-tools'),
    (Join-Path $sdk 'emulator'),
    (Join-Path $sdk 'cmdline-tools\latest\bin'),
    (Join-Path $env:JAVA_HOME 'bin')
) | Where-Object { $_ -and (Test-Path $_) }

$existing = $env:PATH -split ';' | Where-Object { $_ -and ($wanted -notcontains $_) }
$env:PATH = (($wanted + $existing) -join ';')

foreach ($tool in 'flutter', 'adb', 'java', 'docker') {
    $found = Get-Command $tool -ErrorAction SilentlyContinue
    if ($found) {
        Write-Step "$tool -> $($found.Source)"
    } else {
        Write-Warn "$tool not found on PATH"
    }
}

Write-Host ""
Write-Host "  Toolchain ready for this shell." -ForegroundColor Green
Write-Host "  Next:  .\scripts\start-mobile.ps1" -ForegroundColor DarkGray
