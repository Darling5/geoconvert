# -*- coding: utf-8 -*-
"""load_texture 修复验证：RGBA 白底 TIF 不再出现白边。"""
import os
import sys
import tempfile

sys.path.insert(0, r'D:\WEB\zicaiduck\geo-convert')
from PIL import Image
from geoconvert.tifconv.convert import load_texture, encode_image

td = tempfile.mkdtemp(prefix='tif_fix_')

# 1. RGBA 白底（模拟 DJI/Pix4D DOM：无数据区 RGB=白 + alpha=0）
im = Image.new('RGBA', (800, 600), (255, 255, 255, 0))
for y in range(150, 450):
    for x in range(200, 600):
        im.putpixel((x, y), (200, 30, 40, 255))
p1 = os.path.join(td, 'rgba_white.tif')
im.save(p1)

out = load_texture(p1, 200, 16, 'png')
assert out.mode == 'RGBA', out.mode
w, h = out.size
# 四角应全透明
for pos in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1), (w // 2, 0), (0, h // 2)]:
    r, g, b, a = out.getpixel(pos)
    assert a == 0, f'角 {pos} 未透明: {out.getpixel(pos)}'
# 内容中心不透明且颜色正确
for pos in [(w // 2, h // 2)]:
    r, g, b, a = out.getpixel(pos)
    assert a == 255 and abs(r - 200) < 30 and g < 90 and b < 90, (pos, out.getpixel(pos))
# 透明边内缩 2px 处 RGB 不应是白色（防白渗色）
edge = out.getpixel((0, int(h * 0.5) - 1))
print('RGBA png 边缘像素(邻内容行首):', edge)
# 半透明边缘像素经反解后应接近内容色 (200,30,40)，而非被白色冲淡
# alpha<32 的像素反解数值不稳定但视觉不可见，不检查
semis = [(x, y) for y in range(h) for x in range(w)
         if 32 <= out.getpixel((x, y))[3] < 255]
assert semis, '应存在半透明过渡像素'
for x, y in semis[:200]:
    r, g, b, a = out.getpixel((x, y))
    assert r > 150 and g < 120 and b < 120, f'边缘({x},{y}) 被白色冲淡: {(r, g, b, a)}'
print(f'5. 半透明边缘反解 OK（{len(semis)} 个可见过渡像素保持内容色）')
enc = encode_image(out, 'png')
assert enc[:8] == b'\x89PNG\r\n\x1a\n'
print('1. RGBA 白底 TIF -> png 透明边缘 OK, png %d bytes' % len(enc))

# 2. jpeg 路径：返回 RGB、黑角
outj = load_texture(p1, 200, 16, 'jpeg')
assert outj.mode == 'RGB', outj.mode
r, g, b = outj.getpixel((0, 0))
assert (r, g, b) == (0, 0, 0), outj.getpixel((0, 0))
encj = encode_image(outj, 'jpeg')
print('2. RGBA 白底 TIF -> jpeg 黑角 OK')

# 3. 回归：无 alpha 黑边 TIF（旧行为不变）
im3 = Image.new('RGB', (800, 600), (0, 0, 0))
for y in range(150, 450):
    for x in range(200, 600):
        im3.putpixel((x, y), (30, 160, 240))
p3 = os.path.join(td, 'rgb_black.tif')
im3.save(p3)
out3 = load_texture(p3, 200, 16, 'png')
assert out3.mode == 'RGBA'
assert out3.getpixel((0, 0))[3] == 0, out3.getpixel((0, 0))
assert out3.getpixel((out3.size[0] // 2, out3.size[1] // 2))[3] == 255
print('3. 无 alpha 黑边 TIF 回归 OK')

# 4. 回归：不缩放路径（tex_max >= 原尺寸）
out4 = load_texture(p1, 2000, 16, 'png')
assert out4.size == (800, 600) and out4.mode == 'RGBA'
assert out4.getpixel((0, 0))[3] == 0 and out4.getpixel((400, 300))[3] == 255
print('4. 不缩放路径 OK')

print('ALL PASS')
