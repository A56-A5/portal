#!/usr/bin/env bash
#
# Portal installer.
#
#   curl -fsSL https://github.com/A56-A5/portal/releases/latest/download/install.sh | bash
#
# Installs Portal's system dependencies (ffmpeg, xdotool, clipboard tool,
# PyQt5's Xcb runtime library) via your distro's package manager, then
# installs the `portal` command itself in an isolated environment via
# pipx (falling back to `pip install --user` if pipx can't be set up).
#
# Safe to re-run: package-manager installs are skip-if-present, and the
# Python install step is idempotent (reinstalls/upgrades in place).
#
# Env vars you can override:
#   PORTAL_REPO   - git URL to install from (default: this repo, main branch)
#   PORTAL_REF    - branch/tag to install (default: main)

set -euo pipefail

PORTAL_REPO="${PORTAL_REPO:-https://github.com/A56-A5/portal.git}"
PORTAL_REF="${PORTAL_REF:-main}"

c_red="\033[31m"; c_green="\033[32m"; c_yellow="\033[33m"; c_bold="\033[1m"; c_reset="\033[0m"
info()  { printf "${c_bold}==>${c_reset} %s\n" "$1"; }
warn()  { printf "${c_yellow}warning:${c_reset} %s\n" "$1" >&2; }
error() { printf "${c_red}error:${c_reset} %s\n" "$1" >&2; }
die()   { error "$1"; exit 1; }

trap 'error "Install failed on line $LINENO. Nothing after that point was applied."' ERR

# ---------------------------------------------------------------------------
# Platform check - this script is Linux-only. Windows users have build.bat
# or `pip install .` from a checkout; there is no curl|bash equivalent on
# Windows and pretending otherwise would be misleading.
# ---------------------------------------------------------------------------
os_name="$(uname -s)"
if [ "$os_name" != "Linux" ]; then
    die "This installer is for Linux only (detected: $os_name). On Windows, run in PowerShell: irm https://github.com/A56-A5/portal/releases/latest/download/install.ps1 | iex"
fi

if [ "$(id -u)" -eq 0 ]; then
    warn "Running as root. Portal installs to your user account (via pipx/pip --user) - consider re-running as a normal user unless you specifically want a system-wide install."
fi

# ---------------------------------------------------------------------------
# System dependencies. Best-effort across common package managers; if none
# match, we tell the user exactly what to install by hand instead of
# guessing or silently skipping.
# ---------------------------------------------------------------------------
install_system_deps() {
    local pm="" install_cmd=""
    if command -v apt-get >/dev/null 2>&1; then
        pm="apt"; install_cmd="sudo apt-get update && sudo apt-get install -y ffmpeg xdotool wl-clipboard xclip python3-pip libxcb-cursor0"
    elif command -v dnf >/dev/null 2>&1; then
        pm="dnf"; install_cmd="sudo dnf install -y ffmpeg xdotool wl-clipboard xclip python3-pip xcb-util-cursor"
    elif command -v pacman >/dev/null 2>&1; then
        pm="pacman"; install_cmd="sudo pacman -Sy --needed --noconfirm ffmpeg xdotool wl-clipboard xclip python-pip xcb-util-cursor"
    elif command -v zypper >/dev/null 2>&1; then
        pm="zypper"; install_cmd="sudo zypper install -y ffmpeg xdotool wl-clipboard xclip python3-pip xcb-util-cursor"
    fi

    if [ -z "$pm" ]; then
        warn "Couldn't detect apt/dnf/pacman/zypper. Please install these manually before running 'portal': ffmpeg, xdotool, xclip (or wl-clipboard on Wayland), and PyQt5's xcb runtime library (e.g. libxcb-cursor0)."
        return
    fi

    info "Installing system packages via $pm (ffmpeg, xdotool, clipboard tool, Qt xcb runtime)..."
    eval "$install_cmd"
}

# ---------------------------------------------------------------------------
# Python version check
# ---------------------------------------------------------------------------
check_python() {
    command -v python3 >/dev/null 2>&1 || die "python3 not found. Install Python 3.9+ first."
    local ver
    ver="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
    python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' \
        || die "Portal needs Python 3.9+, found $ver."
    info "Using Python $ver"
}

# ---------------------------------------------------------------------------
# Install the `portal` command itself.
#
# Prefer pipx: it installs the app into its own isolated virtualenv and
# just symlinks the `portal` entry point onto your PATH, so it can't
# collide with or be broken by unrelated pip packages on your system.
# Falls back to `pip install --user` if pipx isn't available and can't
# be bootstrapped.
# ---------------------------------------------------------------------------
install_portal() {
    local target="git+${PORTAL_REPO}@${PORTAL_REF}"

    if ! command -v pipx >/dev/null 2>&1; then
        info "pipx not found - attempting to install it..."
        if command -v apt-get >/dev/null 2>&1; then
            sudo apt-get install -y pipx 2>/dev/null || python3 -m pip install --user pipx
        else
            python3 -m pip install --user pipx
        fi
        python3 -m pipx ensurepath >/dev/null 2>&1 || true
        export PATH="$HOME/.local/bin:$PATH"
    fi

    if command -v pipx >/dev/null 2>&1; then
        info "Installing Portal via pipx from ${PORTAL_REPO}@${PORTAL_REF}..."
        # --system-site-packages: pipx's venv is otherwise fully isolated,
        # which silently breaks the Hyprland/Sway layer-shell overlay -
        # python-gobject (the `gi` module) + gtk-layer-shell are SYSTEM
        # packages (installed via pacman/apt, linked against system GTK)
        # and cannot be meaningfully pip-installed into an isolated venv.
        # Without this flag, `import gi` fails inside the installed app
        # even when it works fine from a system-Python terminal, causing
        # Portal to silently fall back to hiding waybar via SIGUSR1 on
        # every transition instead of using the real layer-shell overlay.
        # This does not risk collisions: packages Portal actually pip-
        # installs (pynput, PyQt5, etc.) still take precedence over any
        # same-named system package inside the venv.
        pipx install --force --system-site-packages "$target"
    else
        warn "pipx unavailable - falling back to 'pip install --user'. This is fine, but Portal's dependencies will share your user site-packages instead of an isolated environment."
        python3 -m pip install --user --upgrade "$target"
    fi
}

# ---------------------------------------------------------------------------
# Verify `portal` actually landed on PATH and tell the user what to do if not
# ---------------------------------------------------------------------------
verify_install() {
    export PATH="$HOME/.local/bin:$PATH"
    if command -v portal >/dev/null 2>&1; then
        info "Done. Run: ${c_bold}portal${c_reset}"
        info "Uninstall later with: ${c_bold}portal uninstall${c_reset}"
    else
        warn "Installed, but 'portal' isn't on your PATH yet."
        echo "Add this to your ~/.bashrc or ~/.zshrc, then restart your terminal:"
        echo ""
        echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
        echo ""
    fi

    if [ -n "${WAYLAND_DISPLAY:-}" ] || [ "${XDG_SESSION_TYPE:-}" = "wayland" ]; then
        echo ""
        info "Wayland session detected. Portal supports Wayland via X11 compatibility mode."
    fi
}

main() {
    info "Installing Portal..."
    check_python
    install_system_deps
    install_portal
    verify_install
}

main "$@"
