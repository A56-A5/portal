# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('portal.ico', '.'), ('portal.png', '.'), ('config.json', '.')],
    hiddenimports=['controllers', 'controllers.keyboard_controller', 'controllers.mouse_controller', 'controllers.clipboard_controller', 'controllers.audio_controller', 'network', 'network.share_manager', 'network.audio_manager', 'network.connection_handler', 'network.input_handler', 'gui', 'gui.main_window', 'gui.log_viewer', 'utils', 'utils.config', 'pynput.keyboard', 'pynput.mouse', 'sounddevice', 'numpy'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Portal-v1.0',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['portal.ico'],
)
