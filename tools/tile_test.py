# -*- coding: utf-8 -*-
"""实测马兰输油站位置各级别影像瓦片返回情况"""
import math, urllib.request, os

LAT, LON = 42.224739, 87.438424
OUT = r"D:\WEB\zicaiduck\geo-convert\tools\tile_test"
os.makedirs(OUT, exist_ok=True)

def tile_xy(lat, lon, z):
    n = 2 ** z
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)
    return x, y

def fetch(url, name):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read()
            with open(os.path.join(OUT, name), "wb") as f:
                f.write(data)
            print("%-28s HTTP %s  %6d bytes  %s" % (name, r.status, len(data), r.headers.get("Content-Type", "")))
    except Exception as e:
        print("%-28s FAIL: %s" % (name, e))

print("=== ArcGIS World_Imagery (当前 preview.js 卫星层, maximumLevel=19) ===")
for z in [15, 16, 17, 18, 19]:
    x, y = tile_xy(LAT, LON, z)
    fetch("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/%d/%d/%d" % (z, y, x),
          "arcgis_z%d.png" % z)

print("=== Tianditu img_w 影像 (候选替换层) ===")
# key 来自环境变量 TIANDITU_KEY（或 geo-convert 根目录 config.json），勿硬编码
KEY = os.environ.get("TIANDITU_KEY", "")
if os.path.isfile(os.path.join(os.path.dirname(__file__), "..", "config.json")):
    try:
        import json
        with open(os.path.join(os.path.dirname(__file__), "..", "config.json"), encoding="utf-8-sig") as f:
            KEY = KEY or json.load(f).get("tianditu_key", "")
    except (OSError, ValueError):
        pass
for z in ([15, 16, 17, 18] if KEY else []):
    x, y = tile_xy(LAT, LON, z)
    fetch("https://t0.tianditu.gov.cn/DataServer?T=img_w&x=%d&y=%d&l=%d&tk=%s" % (x, y, z, KEY),
          "tdt-img_z%d.png" % z)
if not KEY:
    print("%-28s 跳过：未配置 TIANDITU_KEY 环境变量或 config.json" % "tianditu")

print("=== Tianditu cia_w 注记 (当前 preview.js 注记层, maximumLevel=18) ===")
for z in ([17, 18] if KEY else []):
    x, y = tile_xy(LAT, LON, z)
    fetch("https://t0.tianditu.gov.cn/DataServer?T=cia_w&x=%d&y=%d&l=%d&tk=%s" % (x, y, z, KEY),
          "tdt-cia_z%d.png" % z)
