<#
.SYNOPSIS
    Starts everything needed to run the TowAssist app, then runs it.

.DESCRIPTION
    Sets up the toolchain, starts the backend, boots an emulator, gives it a
    position, and launches the app pointed at the right API.

    Safe to re-run: anything already running is left alone.

.PARAMETER Api
    'local' (default) runs against the backend in Docker on this machine.
    'prod' runs against the deployed API and skips Docker entirely.

.PARAMETER ApiUrl
    An explicit API base URL, overriding -Api. Use this for a physical phone,
    which needs your machine's LAN address:
        -ApiUrl http://192.168.1.42:8000/api

.PARAMETER Avd
    Which emulator to boot. Defaults to 'towassist'. Run `flutter emulators`
    to see what you have. 'towassist_client' is the second one, for testing
    two sides of a job at once.

.PARAMETER Lat / -Lng
    The position to give the emulator. Defaults to Apapa, Lagos. This matters:
    a driver's real device position is what dispatch matches against, so an
    emulator with no fix is matched to nothing.

.PARAMETER SkipBackend
    Leave Docker alone. Use when the backend is already running, or with -Api prod.

.PARAMETER SkipEmulator
    Do not boot or wait for an emulator. Use when one is already running.

.PARAMETER SetupOnly
    Get everything ready - backend, emulator, position - then stop without
    launching the app. Prints the command to run it yourself.

.EXAMPLE
    .\scripts\start-mobile.ps1
    Backend in Docker, emulator 'towassist', app against localhost.

.EXAMPLE
    .\scripts\start-mobile.ps1 -Api prod
    Against the deployed API. No Docker needed.

.EXAMPLE
    .\scripts\start-mobile.ps1 -Avd towassist_client -SkipBackend
    A second emulator alongside one already running.
#>
[CmdletBinding()]
param(
    [ValidateSet('local', 'prod')]
    [string]$Api = 'local',
    [string]$ApiUrl = '',
    [string]$Avd = 'towassist',
    [string]$Lat = '6.4550',
    [string]$Lng = '3.3841',
    [switch]$SkipBackend,
    [switch]$SkipEmulator,
    [switch]$SetupOnly
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot

function Write-Head($t) { Write-Host ""; Write-Host "== $t" -ForegroundColor Cyan }
function Write-Step($t) { Write-Host "   $t" }
function Write-Ok($t)   { Write-Host "   $t" -ForegroundColor Green }
function Write-Warn($t) { Write-Host "   ! $t" -ForegroundColor Yellow }
function Write-Fail($t) { Write-Host "   x $t" -ForegroundColor Red }

# ---------------------------------------------------------------- toolchain
Write-Head "Toolchain"
. (Join-Path $PSScriptRoot 'dev-env.ps1')

if (-not (Get-Command flutter -ErrorAction SilentlyContinue)) {
    Write-Fail "flutter is not available. Fix that before continuing."
    return
}

# ---------------------------------------------------------------- which API
# The emulator has its own network stack, so localhost there means the
# emulator itself. 10.0.2.2 is its alias for the host machine - the single
# most common reason the app appears to hang on the sign-in screen.
$LOCAL_API = 'http://10.0.2.2:8000/api'
$PROD_API  = 'https://api-production-ddde.up.railway.app/api'

if ($ApiUrl -ne '') {
    $target = $ApiUrl
    $usingLocal = $false
} elseif ($Api -eq 'prod') {
    $target = $PROD_API
    $usingLocal = $false
} else {
    $target = $LOCAL_API
    $usingLocal = $true
}

Write-Head "API"
Write-Step "app will talk to: $target"

# ---------------------------------------------------------------- backend
if ($usingLocal -and -not $SkipBackend) {
    Write-Head "Backend"
    Push-Location $repoRoot
    try {
        # -ErrorAction Stop is required: with the script-level 'Stop'
        # preference a *non-terminating* web error still skips catch and
        # aborts, and without it a failure does not reach catch at all.
        $already = $false
        try {
            $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/health' `
                                   -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
            if ($r.StatusCode -eq 200) { $already = $true }
        } catch {
            $already = $false
        }

        if ($already) {
            Write-Ok "already running on port 8000"
        } else {
            Write-Step "docker compose up -d --build (first run pulls images, be patient)"
            docker compose up -d --build
            if ($LASTEXITCODE -ne 0) {
                Write-Fail "docker compose failed (exit $LASTEXITCODE)"
                return
            }

            Write-Step "waiting for the API to answer"
            $up = $false
            foreach ($i in 1..40) {
                Start-Sleep -Seconds 3
                try {
                    $r = Invoke-WebRequest -Uri 'http://localhost:8000/health' -TimeoutSec 3 -UseBasicParsing
                    if ($r.StatusCode -eq 200) { $up = $true; break }
                } catch { }
            }
            if ($up) {
                Write-Ok "API healthy at http://localhost:8000"
            } else {
                Write-Fail "API did not come up. Check: docker compose logs api"
                return
            }
        }
    } finally {
        Pop-Location
    }
} elseif (-not $usingLocal) {
    Write-Head "Backend"
    Write-Step "skipped - using a remote API"
}

# ---------------------------------------------------------------- emulator
$device = ''
if (-not $SkipEmulator) {
    Write-Head "Emulator"

    $running = @(adb devices | Select-String -Pattern '^emulator-\d+\s+device$')
    if ($running.Count -gt 0) {
        $device = ($running[0].ToString() -split '\s+')[0]
        Write-Ok "already running: $device"
    } else {
        Write-Step "booting '$Avd' (this takes a minute)"
        # Started detached: the emulator holds its console open for as long as
        # it runs, so waiting on the process would wait forever.
        Start-Process -FilePath (Join-Path $env:ANDROID_HOME 'emulator\emulator.exe') `
                      -ArgumentList @('-avd', $Avd, '-no-snapshot-save', '-no-boot-anim') `
                      -WindowStyle Minimized

        foreach ($i in 1..60) {
            Start-Sleep -Seconds 5
            $running = @(adb devices | Select-String -Pattern '^emulator-\d+\s+device$')
            if ($running.Count -gt 0) {
                $device = ($running[0].ToString() -split '\s+')[0]
                break
            }
        }
        if ($device -eq '') {
            Write-Fail "emulator did not appear. Check the AVD name: flutter emulators"
            return
        }
        Write-Ok "booted: $device"
    }

    # Wait for the system to finish starting, or the position and install below
    # land on a device that is not ready for them yet.
    Write-Step "waiting for Android to finish booting"
    foreach ($i in 1..40) {
        $boot = (adb -s $device shell getprop sys.boot_completed)
        if ("$boot".Trim() -eq '1') { break }
        Start-Sleep -Seconds 3
    }

    # geo fix takes LONGITUDE first, which is the reverse of how coordinates
    # are normally written. Getting it backwards puts the driver in the ocean.
    adb -s $device emu geo fix $Lng $Lat | Out-Null
    Write-Ok "position set to $Lat, $Lng"

    foreach ($p in @(
        'android.permission.POST_NOTIFICATIONS',
        'android.permission.ACCESS_FINE_LOCATION',
        'android.permission.ACCESS_COARSE_LOCATION'
    )) {
        # Fails harmlessly if the app is not installed yet.
        try { adb -s $device shell pm grant ng.towassist.app $p | Out-Null } catch { }
    }
}

# ---------------------------------------------------------------- run
Write-Head "Running the app"
Write-Step "sign in with one of:"
Write-Step "  alice@towassist.com / Commuter123!   (customer)"
Write-Step "  dan@towassist.com   / Driver123!     (driver - has the Driver Console)"
Write-Host ""
Write-Step "r = hot reload,  R = hot restart,  q = quit"
Write-Host ""

if ($SetupOnly) {
    Write-Ok 'everything is ready'
    Write-Host ''
    Write-Step 'run it yourself with:'
    if ($device -ne '') {
        Write-Host "     cd mobile; flutter run -d $device --dart-define=API_BASE_URL=$target" -ForegroundColor White
    } else {
        Write-Host "     cd mobile; flutter run --dart-define=API_BASE_URL=$target" -ForegroundColor White
    }
    return
}

Push-Location (Join-Path $repoRoot 'mobile')
try {
    flutter pub get | Out-Null
    if ($device -ne '') {
        flutter run -d $device --dart-define=API_BASE_URL=$target
    } else {
        flutter run --dart-define=API_BASE_URL=$target
    }
} finally {
    Pop-Location
}
