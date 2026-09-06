## Install

### Linux (one-liner)

```bash
curl -fsSL https://github.com/A56-A5/portal/releases/latest/download/install.sh | bash
```

Installs system dependencies (ffmpeg, xdotool, clipboard tools, etc.) then the `portal` command via [pipx](https://pypa.github.io/pipx/) (falls back to `pip install --user`).

### Windows (one-liner)

```powershell
irm https://github.com/A56-A5/portal/releases/latest/download/install.ps1 | iex
```

Run in PowerShell. Installs Python / Git / ffmpeg via `winget` if needed, then the `portal` command via pipx.

These URLs always point at whatever is attached to the **latest published release** — never at the `main` branch — so they can't break from an in-progress commit between releases.

---

## What's new in v1.2.0

**Wayland / Hyprland support**
- Real input capture on Hyprland via a direct evdev grab, independent of window stacking or focus.
- Keyboard and mouse injection on Wayland clients via `ydotool`, so a Hyprland machine works correctly as either the sending or receiving side.
- A genuine `wlr-layer-shell` overlay on the compositor's `overlay` layer for Hyprland/Sway — waybar is no longer hidden/toggled on every transition; it stays up the whole time.

**Audio**
- Fixed silent audio on receive: removed an invalid ffmpeg device flag that could target a nonexistent PulseAudio/PipeWire sink.
- Fixed audio capturing the wrong output on machines with multiple audio devices (e.g. HDMI + Bluetooth) — now resolves the actual active default sink instead of an arbitrary one.

**Mouse**
- Fixed the cursor snapping to the center of the screen on every transition instead of preserving your actual crossing point — entry position is now preserved proportionally, so it behaves like moving between two real adjacent monitors regardless of resolution differences between machines.
- Fixed a Windows-server-specific bug where the shared cursor could stop responding entirely after a transition.

**Keyboard**
- Fixed a crash on every keystroke when sharing to a Wayland client (missing keycode table).

**Stability**
- Fixed the input-sharing overlay and connection state getting stuck active if the peer disconnected mid-session, requiring a restart to regain local control.
- Fixed a Windows-specific crash-handling bug.
- Unified logging so terminal output and `logs.log` stay in sync — failures no longer show up in only one place.

**UI**
- Added live connection/audio status indicators (Connecting / Connected / Disconnected / Audio Connected, etc.) instead of a static "running" label.

**File transfer & clipboard**
- Robust bidirectional file transfer between Windows and Linux, including full Windows `CF_HDROP` support.
- Background file transfers with proper download cleanup.
- More reliable clipboard sync with clearer notifications and logging.

**Packaging**
- New `portal` CLI: `portal` to launch, `portal uninstall` to remove, `portal --help` for usage.
- Unified PyInstaller build process with a proper spec file.
- Both installers now resolve and install the latest published GitHub release by default, instead of always tracking the `main` branch tip.

---

Full changelog: `v1.0.2...v1.2.0`
