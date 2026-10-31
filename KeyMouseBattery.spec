# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ['winrt.windows.foundation', 'winrt.windows.foundation.collections', 'winrt.windows.storage.streams', 'winrt.windows.devices.bluetooth', 'winrt.windows.devices.bluetooth.advertisement', 'winrt.windows.devices.bluetooth.genericattributeprofile', 'winrt.windows.devices.enumeration']
hiddenimports += collect_submodules('keymousebattery')


a = Analysis(
    ['D:/GPT-DSH_cooperation/DSH/work/P002/KeyMouseBattery/KeyMouseBattery.pyw'],
    pathex=['D:/GPT-DSH_cooperation/DSH/work/P002/KeyMouseBattery', 'D:/GPT-DSH_cooperation/DSH/work/P002/KeyMouseBattery'],
    binaries=[],
    datas=[('D:/GPT-DSH_cooperation/DSH/work/P002/KeyMouseBattery/assets', 'assets')],
    hiddenimports=hiddenimports,
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
    [],
    exclude_binaries=True,
    name='KeyMouseBattery',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='D:/GPT-DSH_cooperation/DSH/work/P002/KeyMouseBattery/build/version_info.txt',
    icon=['D:/GPT-DSH_cooperation/DSH/work/P002/KeyMouseBattery/assets/app.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='KeyMouseBattery',
)
