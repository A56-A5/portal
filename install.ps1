<#
    Portal installer for Windows.

        irm https://github.com/A56-A5/portal/releases/latest/download/install.ps1 | iex

    Installs Git, ffmpeg, and Python (via winget) if missing, then installs
    the `portal` command itself in an isolated environment via pipx
    (falling back to `pip install --user` if pipx can't be set up).

    Safe to re-run: winget installs are skip-if-present, and the pipx
    install step is idempotent (reinstalls/upgrades in place).

    Override via environment variables before piping, e.g.:
        $env:PORTAL_REF = "main"; irm .../install.ps1 | iex
    (default: latest published GitHub release, resolved automatically)

    Written to run under both Windows PowerShell 5.1 and PowerShell 7+ -
    no ternary/null-coalescing operators, no param() block (doesn't play
    well with `iex` on piped scripts).
#>

$ErrorActionPreference = "Stop"

$PortalRepo = if ($env:PORTAL_REPO) { $env:PORTAL_REPO } else { "https://github.com/A56-A5/portal.git" }

function Write-Info    { param($msg) Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Warn2   { param($msg) Write-Warning $msg }
function Write-Fail    { param($msg) Write-Host "error: $msg" -ForegroundColor Red; exit 1 }

# ---------------------------------------------------------------------------
# Resolve which ref to install. Defaults to the latest published GitHub
# release (NOT the main branch tip) - a public installer pulling straight
# from a branch's HEAD installs whatever the most recent commit happens to
# be, including anything mid-debug or broken, with zero warning to whoever
# is running it. $env:PORTAL_REF still overrides this explicitly (e.g. set
# it to "main") for anyone who deliberately wants the bleeding edge.
# ---------------------------------------------------------------------------
function Resolve-LatestReleaseTag {
    try {
        # Older Windows PowerShell 5.1 can default to TLS 1.0/1.1, which
        # GitHub's API rejects outright - force 1.2 before the call so this
        # doesn't silently fail on anything but the newest Windows installs.
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $release = Invoke-RestMethod -Uri "https://api.github.com/repos/A56-A5/portal/releases/latest" -ErrorAction Stop
        return $release.tag_name
    } catch {
        return $null
    }
}

$PortalRef = $env:PORTAL_REF
if (-not $PortalRef) {
    $LatestTag = Resolve-LatestReleaseTag
    if ($LatestTag) {
        $PortalRef = $LatestTag
        Write-Info "Installing latest release: $PortalRef"
    } else {
        $PortalRef = "main"
        Write-Warn2 "Could not reach GitHub's API to determine the latest release - falling back to the main branch, which may be unstable. Set `$env:PORTAL_REF to a specific tag (e.g. v1.2.0) to pin a known-good version instead."
    }
}

# ---------------------------------------------------------------------------
# Platform check
# ---------------------------------------------------------------------------
if (-not $IsWindows -and $PSVersionTable.PSVersion.Major -ge 6) {
    Write-Fail "This installer is for Windows only. On Linux, use: curl -fsSL https://github.com/A56-A5/portal/releases/latest/download/install.sh | bash"
}

# ---------------------------------------------------------------------------
# Refresh $env:Path from the registry so anything winget/pip just installed
# in *this* session is picked up without needing a new terminal window.
# ---------------------------------------------------------------------------
function Update-SessionPath {
    $machine = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $user    = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user"
}

function Test-Command {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

# ---------------------------------------------------------------------------
# winget - used to install Python/Git/ffmpeg if missing. If winget itself
# isn't available (older Windows 10 without App Installer), we don't try
# to install it ourselves - we just tell the user what's missing and how
# to get it, rather than silently failing later with a confusing error.
# ---------------------------------------------------------------------------
$script:HasWinget = Test-Command "winget"
if (-not $script:HasWinget) {
    Write-Warn2 "winget not found. Missing dependencies below will need to be installed manually. (winget ships with Windows 11 and modern Windows 10 via the 'App Installer' package from the Microsoft Store.)"
}

function Install-WithWinget {
    param([string]$Id, [string]$FriendlyName)
    if (-not $script:HasWinget) {
        Write-Warn2 "Please install $FriendlyName manually, then re-run this installer."
        return $false
    }
    Write-Info "Installing $FriendlyName via winget..."
    winget install --id $Id -e --accept-source-agreements --accept-package-agreements --silent | Out-Null
    Update-SessionPath
    return $true
}

# ---------------------------------------------------------------------------
# Python
# ---------------------------------------------------------------------------
function Get-PythonCommand {
    foreach ($cand in @("python", "py")) {
        if (Test-Command $cand) {
            $verOk = & $cand -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)" 2>$null
            if ($LASTEXITCODE -eq 0) { return $cand }
        }
    }
    return $null
}

$PythonCmd = Get-PythonCommand
if (-not $PythonCmd) {
    Write-Info "Python 3.9+ not found."
    if (Install-WithWinget -Id "Python.Python.3.12" -FriendlyName "Python 3.12") {
        $PythonCmd = Get-PythonCommand
    }
    if (-not $PythonCmd) {
        Write-Fail "Python 3.9+ is required. Install it from https://python.org/downloads (check 'Add python.exe to PATH' during setup), then re-run this installer."
    }
}
Write-Info "Using $PythonCmd ($(& $PythonCmd --version))"

# ---------------------------------------------------------------------------
# Git - needed since we install directly from the repo (git+https URL)
# rather than from a package index.
# ---------------------------------------------------------------------------
if (-not (Test-Command "git")) {
    Write-Info "git not found."
    if (Install-WithWinget -Id "Git.Git" -FriendlyName "Git") {
        if (-not (Test-Command "git")) {
            Write-Fail "Git installed but not yet on PATH in this session. Close this terminal, open a new one, and re-run the installer."
        }
    } else {
        Write-Fail "Git is required. Install it from https://git-scm.com/download/win, then re-run this installer."
    }
}

# ---------------------------------------------------------------------------
# ffmpeg - used internally for audio capture/streaming
# ---------------------------------------------------------------------------
if (-not (Test-Command "ffmpeg")) {
    Write-Info "ffmpeg not found."
    Install-WithWinget -Id "Gyan.FFmpeg" -FriendlyName "ffmpeg" | Out-Null
    if (-not (Test-Command "ffmpeg")) {
        Write-Warn2 "ffmpeg still isn't on PATH. Audio sharing won't work until it is - see https://ffmpeg.org/download.html, or restart your terminal if winget just installed it."
    }
}

# ---------------------------------------------------------------------------
# pipx - installs `portal` into its own isolated environment so its
# dependencies can't collide with anything else on your system, while
# still exposing a plain `portal` command on PATH.
# ---------------------------------------------------------------------------
if (-not (Test-Command "pipx")) {
    Write-Info "Installing pipx..."
    & $PythonCmd -m pip install --user --upgrade pipx
    & $PythonCmd -m pipx ensurepath | Out-Null
    Update-SessionPath
}

$target = "git+$PortalRepo@$PortalRef"

if (Test-Command "pipx") {
    Write-Info "Installing Portal via pipx from $PortalRepo@$PortalRef..."
    pipx install --force $target
} else {
    Write-Warn2 "pipx still unavailable after install attempt - falling back to 'pip install --user'. This works, but Portal's dependencies will share your user site-packages instead of an isolated environment."
    & $PythonCmd -m pip install --user --upgrade $target
}

# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------
Update-SessionPath
if (Test-Command "portal") {
    Write-Info "Done. Run: portal"
    Write-Info "Uninstall later with: portal uninstall"
} else {
    Write-Warn2 "Installed, but 'portal' isn't on PATH in this session yet. Close and reopen your terminal, then run 'portal'."
}
