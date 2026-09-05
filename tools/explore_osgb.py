#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""逆向分析 .osgb 二进制结构：找长度前缀字符串、数值序列模式"""

import struct
import sys

path = sys.argv[1] if len(sys.argv) > 1 else (
    r"D:\BaiduNetdiskDownload\库米什压气站模型\OSGB\Data\Tile_+002_+003\Tile_+002_+003.osgb"
)
data = open(path, "rb").read()
print(f"file: {path}  size: {len(data)}")

# 1. 找所有 长度前缀字符串（uint32 len + 可打印 ascii，len>=2）
print("\n=== length-prefixed strings ===")
i = 0
found = []
while i < len(data) - 4:
    n = struct.unpack_from("<I", data, i)[0]
    if 2 <= n <= 64 and i + 4 + n <= len(data):
        s = data[i + 4 : i + 4 + n]
        if all(32 <= b < 127 for b in s):
            found.append((i, n, s.decode("ascii")))
            i += 4 + n
            continue
    i += 1
for off, n, s in found[:60]:
    ctx = data[max(0, off - 8) : off]
    ctx_hex = " ".join(f"{b:02X}" for b in ctx)
    print(f"  offset {off:6d} len={n:2d} {s!r}   prefix8: {ctx_hex}")
print(f"  ... total {len(found)} strings")

# 2. 前 120 字节的 u32 序列（跳过 8 字节 magic）
print("\n=== header u32 dump (offset: value) ===")
for off in range(8, 80, 4):
    v = struct.unpack_from("<I", data, off)[0]
    f = struct.unpack_from("<f", data, off)[0]
    print(f"  +{off:3d}: u32={v:10d} 0x{v:08X}  f32={f:.6g}")

# 3. 统计文件尾部特征（是否有嵌入 jpeg/png）
print("\n=== embedded image scan ===")
for magic, name in [(b"\xff\xd8\xff", "JPEG"), (b"\x89PNG", "PNG")]:
    pos = data.find(magic)
    while pos != -1 and pos < len(data):
        print(f"  {name} at offset {pos}")
        pos = data.find(magic, pos + 1)
        if pos > 0 and data.count(magic) > 20:
            break
