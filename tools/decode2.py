# -*- coding: utf-8 -*-
"""decode2: 按 go-osg UserSerializer 框架bool+内部bool 双 bool 解读验证 PagedLOD。
目标：从 @128 起重新对齐，若能消费完全部 17928 字节即确认。"""
import struct

FILE = r'D:\BaiduNetdiskDownload\库米什压气站模型\OSGB\Data\Tile_+002_+003\Tile_+002_+003.osgb'

data = open(FILE, 'rb').read()
print('file size:', len(data))

p = 0
def u32():
    global p
    v = struct.unpack('<I', data[p:p+4])[0]
    p += 4
    return v
def i32():
    global p
    v = struct.unpack('<i', data[p:p+4])[0]
    p += 4
    return v
def u8():
    global p
    v = data[p]
    p += 1
    return v
def string():
    global p
    n = i32()
    s = data[p:p+n].decode('utf-8', 'replace') if n else ''
    p += n
    return s
def f32():
    global p
    v = struct.unpack('<f', data[p:p+4])[0]
    p += 4
    return v
def f64():
    global p
    v = struct.unpack('<d', data[p:p+8])[0]
    p += 8
    return v

# ---- 快进到 @128（前段与 decode1 一致，已验证）----
p = 8  # skip magic
ty = u32(); ver = i32(); attrs = i32(); comp = string()
print('type=%d ver=%d attrs=%d comp=%r' % (ty, ver, attrs, comp))
cls = string(); uid = u32(); name = string(); dv = i32()
if ver >= 77:
    u8()  # UserDataContainer
u8()  # InitialBound
for _ in range(4):
    u8()  # callbacks
u8()  # CullingActive
u32()  # NodeMask
u8()  # StateSet
cm = i32()
uc = u8()
if uc:
    f64(); f64(); f64(); f64()
rm = i32()
rl = u8()
if rl:
    n = u32()
    for _ in range(n):
        f32(); f32()
print('@%d (应=128) CenterMode=%d UserCenter=%d RangeMode=%d RangeList=%d' % (p, cm, uc, rm, rl))

# ---- PagedLOD 专属（go-osg 双 bool 版本）----
dp_ok = u8(); print('@%d DatabasePath.ok=%d' % (p, dp_ok))
if dp_ok:
    hasp = u8(); print('@%d DatabasePath.hasp=%d' % (p, hasp))
    if hasp:
        print('  database_path=%r' % string())
if ver < 70:
    print('@%d FrameNumberOfLastTraversal=%d' % (p, u32()))
nce = u32(); print('@%d NumChildrenThatCannotBeExpired=%d' % (p, nce))
decp = u8(); print('@%d DisableExternalChildrenPaging=%d' % (p, decp))
rdl = u8(); print('@%d RangeDataList.ok=%d' % (p, rdl))
if rdl:
    n = u32(); print('@%d RangeDataList n=%d' % (p, n))
    for i in range(n):
        print('  file[%d]=%r' % (i, string()))
    pn = u32(); print('@%d PriorityList n=%d' % (p, pn))
    for i in range(pn):
        print('  prio[%d]=(%r,%r)' % (i, f32(), f32()))
ch_ok = u8(); print('@%d Children.ok=%d' % (p, ch_ok))
if ch_ok:
    n = u32(); print('@%d Children n=%d' % (p, n))
    for i in range(n):
        c = string()
        print('  child[%d] class=%r @%d' % (i, c, p))
        raise SystemExit('child 递归需 reader.py 完成；先看首个 child class 是否 osg::Geode')
print('END @%d, remaining %d bytes' % (p, len(data) - p))
