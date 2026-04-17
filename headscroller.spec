# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for bundling headscroller.py into a standalone binary

import os
import mediapipe

mediapipe_path = os.path.dirname(mediapipe.__file__)

a = Analysis(
    ['headscroller.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('face_landmarker.task', '.'),
        (mediapipe_path, 'mediapipe'),
    ],
    hiddenimports=[
        'mediapipe',
        'mediapipe.tasks',
        'mediapipe.tasks.python',
        'mediapipe.tasks.python.vision',
        'mediapipe.tasks.python.vision.face_landmarker',
        'cv2',
        'numpy',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'IPython', 'jupyter', 'pandas', 'scipy', 'sympy'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='headscroller',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    target_arch='arm64',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='headscroller',
)
