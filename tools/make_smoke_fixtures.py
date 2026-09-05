# -*- coding: utf-8 -*-
"""生成 exe 冒烟测试夹具：微型 OBJ（带纹理）+ 微型 TIF。"""
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

BASE = os.path.dirname(os.path.abspath(__file__))
OBJ_DIR = os.path.join(BASE, 'smoke', 'obj')
TIF_DIR = os.path.join(BASE, 'smoke', 'tif')
os.makedirs(OBJ_DIR, exist_ok=True)
os.makedirs(TIF_DIR, exist_ok=True)

# --- 微型 OBJ：一个 4x4m 平板（上下两面各 2 三角形）+ 侧面，带 UV ---
from PIL import Image

img = Image.new('RGB', (64, 64))
for y in range(64):
    for x in range(64):
        img.putpixel((x, y), (200, (x * 4) % 256, (y * 4) % 256))
img.save(os.path.join(OBJ_DIR, 'tex.jpg'), quality=90)

verts = [
    (0, 0, 0), (4, 0, 0), (4, 4, 0), (0, 4, 0),      # 底面
    (0, 0, 1), (4, 0, 1), (4, 4, 1), (0, 4, 1),      # 顶面
]
faces = [
    ('4/4', '1/1', '2/2'), ('4/4', '2/2', '3/3'),     # 底面
    ('5/1', '8/4', '7/3'), ('5/1', '7/3', '6/2'),     # 顶面
    ('1/1', '5/1', '6/1'), ('1/1', '6/1', '2/1'),     # 侧面若干
    ('2/1', '6/1', '7/1'), ('2/1', '7/1', '3/1'),
    ('3/1', '7/1', '8/1'), ('3/1', '8/1', '4/1'),
    ('4/1', '8/1', '5/1'), ('4/1', '5/1', '1/1'),
]
with open(os.path.join(OBJ_DIR, 'smoke.obj'), 'w', encoding='utf-8') as f:
    f.write('mtllib smoke.mtl\n')
    for v in verts:
        f.write('v %s %s %s\n' % v)
    for vt in [(0, 0), (1, 0), (1, 1), (0, 1)]:
        f.write('vt %s %s\n' % vt)
    f.write('usemtl mat0\ns off\n')
    for a in faces:
        f.write('f %s\n' % ' '.join(a))
with open(os.path.join(OBJ_DIR, 'smoke.mtl'), 'w', encoding='utf-8') as f:
    f.write('newmtl mat0\nKa 1 1 1\nKd 1 1 1\nmap_Kd tex.jpg\n')

# --- 微型 TIF：512x512 带黑边（模拟 DOM 黑边透明语义） ---
w = h = 512
im = Image.new('RGB', (w, h), (0, 0, 0))
for y in range(32, h - 32):
    for x in range(32, w - 32):
        im.putpixel((x, y), (150, 120, 90))
im.save(os.path.join(TIF_DIR, 'smoke.tif'))

print('fixtures ready:', OBJ_DIR, TIF_DIR)
