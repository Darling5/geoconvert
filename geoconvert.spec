# -*- mode: python ; coding: utf-8 -*-
# 相对路径基于本 spec 文件所在目录（SPECPATH），换机器/换目录无需改动
import os
from PyInstaller.utils.hooks import collect_submodules

ROOT = SPECPATH

hiddenimports = ['pyfqmr', 'scipy.sparse.csgraph', 'scipy.spatial', 'geoconvert.webui']
hiddenimports += collect_submodules('scipy.sparse')
hiddenimports += collect_submodules('PIL')
# pywebview（内嵌 WebView2 单窗口）及其 winforms/pythonnet 后端
hiddenimports += collect_submodules('webview')
hiddenimports += ['webview.platforms.winforms', 'webview.platforms.edgechromium']


a = Analysis(
    [os.path.join(ROOT, 'entry.py')],
    pathex=[ROOT],
    binaries=[],
    datas=[
        (os.path.join(ROOT, 'geoconvert', 'webui', 'index.html'), 'geoconvert/webui'),
        (os.path.join(ROOT, 'geoconvert', 'webui', 'preview.js'), 'geoconvert/webui'),
        (os.path.join(ROOT, 'geoconvert', 'webui', 'cc_globe.js'), 'geoconvert/webui'),
        (os.path.join(ROOT, 'geoconvert', 'webui', 'appicon.ico'), 'geoconvert/webui'),
        (os.path.join(ROOT, 'geoconvert', 'webui', 'cesium'), 'geoconvert/webui/cesium'),
    ],
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
    name='geoconvert',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(ROOT, 'tools', 'appicon.ico'),
)
# onedir：onefile 每次启动重解压 65MB + 实时杀毒扫描会让窗口延迟数分钟，onedir 只解压一次
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='geoconvert',
)
