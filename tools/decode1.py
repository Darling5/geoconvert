# -*- coding: utf-8 -*-
"""手动逐字段解码第一个 PagedLOD，定位字段对齐错误。"""
import struct

FILE = r'D:\BaiduNetdiskDownload\库米什压气站模型\OSGB\Data\Tile_+002_+003\Tile_+002_+003.osgb'

data = open(FILE, 'rb').read()
print('file size:', len(data))
print('hex 0..80:', ' '.join('%02x' % b for b in data[:80]))

p = 8
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

ty = u32(); print('@%d type=%d' % (p, ty))
ver = i32(); print('@%d version=%d' % (p, ver))
attrs = i32(); print('@%d attributes=%d (0x%x)' % (p, attrs, attrs))
comp = string(); print('@%d compressor=%r' % (p, comp))

cls = string(); print('@%d class=%r' % (p, cls))
uid = u32(); print('@%d uid=%d' % (p, uid))
name = string(); print('@%d name=%r' % (p, name))
dv = i32(); print('@%d DataVariance=%d' % (p, dv))
if ver >= 77:
    has_udc = u8(); print('@%d UserDataContainer?=%d' % (p, has_udc))

# Node fields
ib = u8(); print('@%d InitialBound?=%d' % (p, ib))
if ib:
    print('  center=(%r,%r,%r) radius=%r' % (f64(), f64(), f64(), f64()))
for cb in ('ComputeBoundingSphereCallback', 'UpdateCallback', 'EventCallback', 'CullCallback'):
    b = u8()
    print('@%d %s?=%d' % (p, cb, b))
    if b:
        sub = string()
        print('  -> %r' % sub)
        p2 = p  # 无法完整解析，停在这里
        raise SystemExit('callback 需要单独解析')
ca = u8(); print('@%d CullingActive=%d' % (p, ca))
nm = u32(); print('@%d NodeMask=0x%x' % (p, nm))
if ver < 77:
    ndesc = u8(); print('@%d Descriptions?=%d' % (p, ndesc))
ss = u8(); print('@%d StateSet?=%d' % (p, ss))

# LOD fields
cm = i32(); print('@%d CenterMode=%d' % (p, cm))
uc = u8(); print('@%d UserCenter?=%d' % (p, uc))
if uc:
    print('  center=(%r,%r,%r) radius=%r' % (f64(), f64(), f64(), f64()))
rm = i32(); print('@%d RangeMode=%d' % (p, rm))
rl = u8(); print('@%d RangeList?=%d' % (p, rl))
if rl:
    n = u32(); print('@%d RangeList n=%d' % (p, n))
    for i in range(n):
        print('  range[%d]=(%r,%r)' % (i, f32(), f32()))

# PagedLOD fields
dp = u8(); print('@%d DatabasePath?=%d' % (p, dp))
if dp:
    s = string(); print('  database_path=%r' % s)
if ver < 70:
    print('@%d FrameNumberOfLastTraversal=%d' % (p, u32()))
nce = u32(); print('@%d NumChildrenThatCannotBeExpired=%d' % (p, nce))
decp = u8(); print('@%d DisableExternalChildrenPaging=%d' % (p, decp))
rdl = u8(); print('@%d RangeDataList?=%d' % (p, rdl))
if rdl:
    n = u32(); print('@%d RangeDataList n=%d' % (p, n))
    for i in range(n):
        print('  file[%d]=%r' % (i, string()))
    pn = u32(); print('@%d PriorityList n=%d' % (p, pn))
    for i in range(pn):
        print('  prio[%d]=(%r,%r)' % (i, f32(), f32()))
ch = u8(); print('@%d Children?=%d' % (p, ch))
if ch:
    n = u32(); print('@%d Children n=%d' % (p, n))
    for i in range(n):
        c = string()
        print('  child[%d] class=%r' % (i, c))
print('END @%d, remaining %d bytes' % (p, len(data) - p))
