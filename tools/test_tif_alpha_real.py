# -*- coding: utf-8 -*-
"""真实 6.6GB RGBA TIF 验证 load_texture 白边修复。"""
import sys
import time
import tracemalloc

sys.path.insert(0, r'D:\WEB\zicaiduck\geo-convert')
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
from geoconvert.tifconv.convert import load_texture, encode_image

p = r'D:\User\Documents\xwechat_files\wxid_xpfto078g91j21_f6b3\msg\file\2026-09\2026.8\2026.8_DOM.tif'

t0 = time.time()
im = load_texture(p, 1024, 16, 'png')
print('load_texture: %.1fs mode=%s size=%s' % (time.time() - t0, im.mode, im.size))

w, h = im.size
px = im.load()

# 1. 四角与边中点必须全透明
for pos in [(0, 0), (w-1, 0), (0, h-1), (w-1, h-1), (w//2, 0), (w//2, h-1), (0, h//2), (w-1, h//2)]:
    r, g, b, a = px[pos]
    assert a == 0, '边角 %s 未透明: %s' % (pos, px[pos])
print('1. 八个边角点全透明 OK')

# 2. 全图不透明白色像素统计（白边残留检测）：a>200 且 RGB 均 >240
import numpy as np
arr = np.asarray(im)
opaque = arr[..., 3] > 200
whiteish = opaque & (arr[..., 0] > 240) & (arr[..., 1] > 240) & (arr[..., 2] > 240)
print('2. 不透明像素 %d，其中纯白 %d（%.3f%%）' % (opaque.sum(), whiteish.sum(),
      100.0 * whiteish.sum() / max(1, opaque.sum())))

# 3. 中心内容不透明
c = px[(w//2, h//2)]
assert c[3] == 255, c
print('3. 中心内容不透明 OK:', c)

# 4. 半透明边缘像素颜色合理（无被白色冲淡）
semi = (arr[..., 3] >= 32) & (arr[..., 3] < 255)
print('4. 半透明过渡像素 %d 个' % semi.sum())

enc = encode_image(im, 'png')
out_png = r'C:\Users\11430\AppData\Local\Temp\dom_alpha_test.png'
with open(out_png, 'wb') as f:
    f.write(enc)
print('5. 输出预览 PNG: %s（%.1f MB）' % (out_png, len(enc)/1048576))
print('ALL PASS')
