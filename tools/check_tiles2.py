# -*- coding: utf-8 -*-
"""瓦片像素分析：判断 ArcGIS/天地图返回的是真实影像还是灰色占位图。"""
import io
import math
import urllib.request

opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
UA = {'User-Agent': 'Mozilla/5.0'}
TDT_KEY = '654e9ced28089ca0b5caff0d5c23d5b6'


def fetch_bytes(url):
    req = urllib.request.Request(url, headers=UA)
    with opener.open(req, timeout=12) as r:
        return r.read()


def tile_xy(lon, lat, z):
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n)
    return min(x, n - 1), min(y, n - 1)


def analyze(url):
    from PIL import Image
    try:
        d = fetch_bytes(url)
    except Exception as e:
        return f'HTTP ERR {e}'
    try:
        im = Image.open(io.BytesIO(d)).convert('RGB')
    except Exception as e:
        return f'decode ERR {e}'
    w, h = im.size
    # 8x8 采样网格
    vals = set()
    gray_all = True
    for i in range(8):
        for j in range(8):
            px = im.getpixel((int((i + 0.5) / 8 * (w - 1)), int((j + 0.5) / 8 * (h - 1))))
            r, g, b = px[:3]
            if abs(r - g) > 6 or abs(g - b) > 6:
                gray_all = False
            vals.add((r // 8, g // 8, b // 8))  # 粗量化去噪
    corner = im.getpixel((2, 2))
    center = im.getpixel((w // 2, h // 2))
    return (f'{len(d)}B {w}x{h} 采样色数={len(vals)} 全灰={gray_all} '
            f'角={corner} 心={center}')


arc = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
tdt = 'https://t3.tianditu.gov.cn/DataServer?T={t}&x={x}&y={y}&l={z}&tk=' + TDT_KEY

print('=== ArcGIS 赤道0,0 海洋 ===')
for z in (10, 14, 16, 17, 18, 19):
    x, y = tile_xy(0, 0, z)
    print(f'  z{z}: {analyze(arc.format(z=z, x=x, y=y))}')

print('=== ArcGIS 偏远陆地 z19（内蒙古草原 111.5E, 43.0N）===')
for z in (17, 18, 19):
    x, y = tile_xy(111.5, 43.0, z)
    print(f'  z{z}: {analyze(arc.format(z=z, x=x, y=y))}')

print('=== 天地图 img_w 赤道0,0（境外，应为占位图）===')
for z in (8, 14):
    x, y = tile_xy(0, 0, z)
    print(f'  z{z}: {analyze(tdt.format(t="img_w", x=x, y=y, z=z))}')

print('=== 天地图 img_w 云南 rural 98.5E,25.0N ===')
for z in (16, 17, 18):
    x, y = tile_xy(98.5, 25.0, z)
    print(f'  z{z}: {analyze(tdt.format(t="img_w", x=x, y=y, z=z))}')

print('=== 天地图 cia_w 赤道0,0（境外注记，看是否也占位）===')
for z in (8,):
    x, y = tile_xy(0, 0, z)
    print(f'  z{z}: {analyze(tdt.format(t="cia_w", x=x, y=y, z=z))}')
