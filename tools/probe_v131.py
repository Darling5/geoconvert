# -*- coding: utf-8 -*-
"""验证 v131 + binary brackets 格式推断：解析 Block.osgb 并打印结构树。"""
import struct, sys

PATH = sys.argv[1] if len(sys.argv) > 1 else r'D:\User\Documents\xwechat_files\wxid_xpfto078g91j21_f6b3\msg\file\2026-09\terra_osgbs\Block.osgb'

class R:
    def __init__(self, data):
        self.d = data
        self.p = 0
        self.v = 0
        self.brackets = False
        self.begins = []
        self.sizes = []
        self.id_map = {}
        self.depth = 0

    def take(self, n):
        if self.p + n > len(self.d):
            raise EOFError('EOF at %d (+%d), total %d' % (self.p, n, len(self.d)))
        b = self.d[self.p:self.p+n]
        self.p += n
        return b

    def u8(self): return self.take(1)[0]
    def i32(self): return struct.unpack('<i', self.take(4))[0]
    def u32(self): return struct.unpack('<I', self.take(4))[0]
    def f32(self): return struct.unpack('<f', self.take(4))[0]
    def f64(self): return struct.unpack('<d', self.take(8))[0]
    def string(self):
        n = self.i32()
        return self.take(n).decode('utf-8', 'replace') if n > 0 else ''

    def begin(self):
        if self.brackets:
            self.begins.append(self.p)
            size = struct.unpack('<Q', self.take(8))[0] if self.v > 148 else struct.unpack('<i', self.take(4))[0]
            self.sizes.append(size)

    def end(self):
        if self.brackets and self.begins:
            self.begins.pop(); self.sizes.pop()

    def advance(self):
        """跳到当前块尾（readObject 末尾调用）"""
        if self.brackets and self.begins:
            pos = self.begins[-1] + self.sizes[-1]
            print('  ' * self.depth + '  [advance %d -> %d]' % (self.p, pos))
            self.p = pos
            self.begins.pop(); self.sizes.pop()

    def block_end(self):
        if self.begins:
            return self.begins[-1] + self.sizes[-1]
        return None


def read_object(r):
    cls = r.string()
    if cls == 'NULL':
        return None
    r.depth += 1
    print('  ' * r.depth + 'OBJ %s @%d' % (cls, r.p))
    r.begin()
    uid = r.u32()
    print('  ' * r.depth + ' uid=%d' % uid)
    if uid and uid in r.id_map:
        r.advance()
        r.depth -= 1
        return r.id_map[uid]
    obj = {'cls': cls}
    if uid:
        r.id_map[uid] = obj
    try:
        need_advance = read_fields(r, cls, obj)
    except Exception as e:
        print('  ' * r.depth + ' !! %s @%d' % (e, r.p))
        raise
    if need_advance:
        r.advance()
    r.depth -= 1
    return obj


def read_object_header(r, obj):
    obj['name'] = r.string()
    r.i32()  # DataVariance
    if r.v >= 77:
        if r.u8():
            # UserDataContainer 对象
            print('  ' * r.depth + ' UserDataContainer!')
            read_object(r)


def read_node_rest(r, obj):
    if r.u8():  # InitialBound
        r.begin()
        c = (r.f64(), r.f64(), r.f64())
        rad = r.f64()
        obj['initial_bound'] = (c, rad)
        print('  ' * r.depth + ' InitialBound center=%r r=%r' % (c, rad))
        r.end()
    for cb in ('cb1', 'cb2', 'cb3', 'cb4'):
        if r.u8():
            read_object(r)
    r.u8()   # CullingActive
    r.u32()  # NodeMask
    if r.v < 77:
        if r.u8():
            n = r.u32()
            for _ in range(n):
                r.string()
    if r.u8():
        obj['state_set'] = read_object(r)


def read_fields(r, cls, obj):
    if cls == 'osg::Group':
        read_object_header(r, obj)
        read_node_rest(r, obj)
        if r.u8():  # Children
            n = r.u32()
            print('  ' * r.depth + ' Children n=%d' % n)
            r.begin()
            obj['children'] = []
            for _ in range(n):
                c = read_object(r)
                if c is not None:
                    obj['children'].append(c)
            r.end()
    elif cls == 'osg::PagedLOD':
        read_object_header(r, obj)
        read_node_rest(r, obj)
        read_lod_fields(r, obj)
        # DatabasePath
        if r.u8():
            if r.u8():
                obj['database_path'] = r.string()
        if r.v < 70:
            r.u32()
        r.u32()  # NumChildrenThatCannotBeExpired
        r.u8()   # DisableExternalChildrenPaging
        if r.u8():  # RangeDataList
            n = r.u32()
            r.begin()
            obj['file_names'] = []
            for _ in range(n):
                obj['file_names'].append(r.string())
            print('  ' * r.depth + ' RangeData n=%d files=%r' % (n, obj['file_names'][:4]))
            r.end()
            pn = r.u32()
            r.begin()
            for _ in range(pn):
                r.f32(); r.f32()
            r.end()
        if r.u8():  # Children
            n = r.u32()
            print('  ' * r.depth + ' PagedLOD Children n=%d' % n)
            if n > 0:
                r.begin()
                obj['children'] = []
                for _ in range(n):
                    c = read_object(r)
                    if c is not None:
                        obj['children'].append(c)
                r.end()
    elif cls == 'osg::Geode':
        read_object_header(r, obj)
        read_node_rest(r, obj)
        if r.u8():  # Drawables
            n = r.u32()
            print('  ' * r.depth + ' Drawables n=%d' % n)
            r.begin()
            obj['drawables'] = []
            for _ in range(n):
                d = read_object(r)
                if d is not None:
                    obj['drawables'].append(d)
            r.end()
    elif cls == 'osg::Geometry':
        read_geometry(r, obj)
    elif cls == 'osg::StateSet':
        read_stateset(r, obj)
    elif cls in ('osg::Texture2D', 'osg::Texture1D'):
        read_texture(r, obj, cls)
    elif cls == 'osg::Material':
        read_material(r, obj)
    elif cls in ('osg::DrawArrays', 'osg::DrawArrayLengths', 'osg::DrawElementsUByte',
                 'osg::DrawElementsUShort', 'osg::DrawElementsUInt'):
        read_primitive_object(r, cls, obj)
    else:
        # 未知类：用块大小整体跳过（brackets 模式），返回 False 表示无需再 advance
        if r.brackets:
            print('  ' * r.depth + ' [SKIP %s]' % cls)
            r.advance()
            return False
        raise ValueError('unknown class %r' % cls)
    return True


def read_primitive_object(r, cls, obj):
    read_object_header(r, obj)
    r.i32()  # NumInstances
    mode = r.i32()  # Mode
    obj['mode'] = mode
    if cls == 'osg::DrawArrays':
        obj['first'] = r.i32()
        obj['count'] = r.i32()
        print('  ' * r.depth + ' DrawArrays mode=%d first=%d count=%d' % (mode, obj['first'], obj['count']))
    elif cls == 'osg::DrawArrayLengths':
        obj['first'] = r.i32()
        n = r.i32()
        obj['lengths'] = [r.i32() for _ in range(n)]
    elif cls == 'osg::DrawElementsUByte':
        n = r.i32()
        obj['indices'] = list(r.take(n))
        print('  ' * r.depth + ' DrawElemUByte mode=%d n=%d' % (mode, n))
    elif cls == 'osg::DrawElementsUShort':
        n = r.i32()
        obj['indices'] = list(struct.unpack('<%dH' % n, r.take(2 * n)))
        print('  ' * r.depth + ' DrawElemUShort mode=%d n=%d' % (mode, n))
    elif cls == 'osg::DrawElementsUInt':
        n = r.i32()
        obj['indices'] = list(struct.unpack('<%dI' % n, r.take(4 * n)))
        print('  ' * r.depth + ' DrawElemUInt mode=%d n=%d' % (mode, n))
    bend = r.block_end()
    print('  ' * r.depth + ' prim block check: pos=%d bend=%s' % (r.p, bend))


def read_lod_fields(r, obj):
    r.i32()  # CenterMode
    if r.u8():
        c = (r.f64(), r.f64(), r.f64())
        rad = r.f64()
        obj['center'] = c
        obj['radius'] = rad
        print('  ' * r.depth + ' UserCenter=%r r=%r' % (c, rad))
    obj['range_mode'] = r.i32()
    if r.u8():
        n = r.u32()
        r.begin()
        obj['range_list'] = []
        for _ in range(n):
            obj['range_list'].append((r.f32(), r.f32()))
        print('  ' * r.depth + ' RangeList n=%d %r' % (n, obj['range_list'][:4]))
        r.end()


def read_material(r, obj):
    read_object_header(r, obj)
    if r.u8(): read_object(r)
    if r.u8(): read_object(r)
    r.i32()
    for _ in range(4):
        if r.u8():
            r.u8()
            r.take(32)
    if r.u8():
        r.u8()
        r.take(8)


def read_stateset(r, ss):
    read_object_header(r, ss)
    if r.u8():  # ModeList
        n = r.u32()
        if n > 0:
            r.begin()
            for _ in range(n):
                r.i32(); r.i32()
            r.end()
        print('  ' * r.depth + ' ModeList n=%d' % n)
    if r.u8():  # AttributeList
        n = r.u32()
        if n > 0:
            r.begin()
            for _ in range(n):
                read_object(r); r.i32()
            r.end()
        print('  ' * r.depth + ' AttributeList n=%d' % n)
    if r.u8():  # TextureModeList
        n = r.u32()
        r.begin()
        for _ in range(n):
            mn = r.u32()
            if mn > 0:
                r.begin()
                for _ in range(mn):
                    r.i32(); r.i32()
                r.end()
        r.end()
        print('  ' * r.depth + ' TextureModeList n=%d' % n)
    if r.u8():  # TextureAttributeList
        n = r.u32()
        r.begin()
        for _ in range(n):
            an = r.u32()
            if an > 0:
                r.begin()
                for _ in range(an):
                    read_object(r); r.i32()
                r.end()
        r.end()
        print('  ' * r.depth + ' TextureAttributeList n=%d' % n)
    if r.u8():  # UniformList
        n = r.u32()
        r.begin()
        for _ in range(n):
            read_object(r); r.i32()
        r.end()
    r.i32(); r.i32(); r.i32()
    r.string()
    r.u8()
    if r.u8(): read_object(r)
    if r.u8(): read_object(r)


def read_texture(r, tex, cls):
    read_object_header(r, tex)
    if r.u8(): read_object(r)
    if r.u8(): read_object(r)
    for _ in range(5):
        if r.u8():
            r.i32()
    r.f32()
    r.u8(); r.u8(); r.u8(); r.u8()
    r.take(32)
    r.i32()
    r.i32()  # InternalFormatMode
    if r.u8(): r.i32()
    if r.u8(): r.i32()
    if r.u8(): r.i32()
    r.u8()
    r.i32(); r.i32()
    r.f32()
    if r.v >= 95:  # ImageAttachment (check 恒 false)
        r.u8()
    if r.v >= 98:  # Swizzle (check 恒 true)
        if r.u8():
            r.string()
    if r.u8():  # Image
        read_image(r)
    r.i32()
    r.i32()


def read_image(r):
    cls = r.string() if r.v > 94 else ''
    uid = r.u32()
    fname = r.string()
    r.i32()  # WriteHint
    decision = r.i32()
    print('  ' * r.depth + ' Image cls=%r uid=%d file=%r decision=%d' % (cls, uid, fname, decision))
    if decision == 0:
        r.i32(); r.i32(); r.i32(); r.i32(); r.i32()
        r.i32(); r.i32(); r.i32(); r.i32()
        size = r.u32()
        if size:
            r.take(size)
        mipn = r.u32()
        for _ in range(mipn):
            r.u32()
    elif decision == 1:
        size = r.u32()
        if size:
            r.take(size)
    # Object fields
    r.string()
    r.i32()
    if r.v >= 77:
        if r.u8():
            read_object(r)


def read_geometry(r, g):
    read_object_header(r, g)
    if r.u8(): g['state_set'] = read_object(r)
    if r.u8():  # InitialBound (Drawable BoundingBox)
        r.begin()
        r.take(48)
        r.end()
    if r.u8(): read_object(r)  # ComputeBoundingBoxCallback
    if r.u8(): read_object(r)  # Shape
    r.u8(); r.u8(); r.u8()
    if r.u8(): read_object(r)  # Update
    if r.u8(): read_object(r)  # Event
    if r.u8(): read_object(r)  # Cull
    if r.u8(): read_object(r)  # Draw
    if r.v >= 112:
        n = r.u32()
        print('  ' * r.depth + ' PrimitiveSetList n=%d' % n)
        g['primitives'] = []
        for _ in range(n):
            g['primitives'].append(read_object(r))
        for key in ('VertexArray', 'NormalArray', 'ColorArray', 'SecondaryColorArray', 'FogCoordArray'):
            if r.u8():
                arr = read_array_object(r)
                g[key] = arr
                print('  ' * r.depth + ' %s: %s' % (key, arr and ('%s n=%d' % (arr['cls'], len(arr['data'])))))
        n = r.u32()
        print('  ' * r.depth + ' TexCoordArrayList n=%d' % n)
        g['texcoords'] = []
        for _ in range(n):
            g['texcoords'].append(read_array_object(r))
        n = r.u32()
        g['vertex_attribs'] = []
        for _ in range(n):
            read_array_object(r)
    else:
        raise ValueError('v<112 not handled in this probe')


ARRAY_INFO = {
    'osg::ByteArray': ('b', 1, 1), 'osg::UByteArray': ('B', 1, 1),
    'osg::ShortArray': ('h', 2, 1), 'osg::UShortArray': ('H', 2, 1),
    'osg::IntArray': ('i', 4, 1), 'osg::UIntArray': ('I', 4, 1),
    'osg::FloatArray': ('f', 4, 1), 'osg::DoubleArray': ('d', 8, 1),
    'osg::Vec2bArray': ('b', 1, 2), 'osg::Vec3bArray': ('b', 1, 3), 'osg::Vec4bArray': ('b', 1, 4),
    'osg::Vec2ubArray': ('B', 1, 2), 'osg::Vec3ubArray': ('B', 1, 3), 'osg::Vec4ubArray': ('B', 1, 4),
    'osg::Vec2sArray': ('h', 2, 2), 'osg::Vec3sArray': ('h', 2, 3), 'osg::Vec4sArray': ('h', 2, 4),
    'osg::Vec2usArray': ('H', 2, 2), 'osg::Vec3usArray': ('H', 2, 3), 'osg::Vec4usArray': ('H', 2, 4),
    'osg::Vec2iArray': ('i', 4, 2), 'osg::Vec3iArray': ('i', 4, 3), 'osg::Vec4iArray': ('i', 4, 4),
    'osg::Vec2uiArray': ('I', 4, 2), 'osg::Vec3uiArray': ('I', 4, 3), 'osg::Vec4uiArray': ('I', 4, 4),
    'osg::Vec2Array': ('f', 4, 2), 'osg::Vec3Array': ('f', 4, 3), 'osg::Vec4Array': ('f', 4, 4),
    'osg::Vec2dArray': ('d', 8, 2), 'osg::Vec3dArray': ('d', 8, 3), 'osg::Vec4dArray': ('d', 8, 4),
}


def read_array_object(r):
    cls = r.string()
    if cls == 'NULL':
        return None
    r.depth += 1
    r.begin()
    uid = r.u32()
    read_object_header(r, {'cls': cls})
    binding = r.i32()
    normalize = r.u8()
    preserve = r.u8()
    fmt, esz, per = ARRAY_INFO[cls]
    count = r.u32()
    total = count * esz * per
    # 验证：count 数据应恰好到块尾
    bend = r.block_end()
    ok = (bend is not None and r.p + total == bend)
    data = r.take(total) if ok else None
    print('  ' * r.depth + 'ARRAY %s uid=%d bind=%d norm=%d pres=%d count=%d total=%d pos=%d bend=%s ok=%s' % (
        cls, uid, binding, normalize, preserve, count, total, r.p, bend, ok))
    r.advance()
    r.depth -= 1
    return {'cls': cls, 'count': count, 'data': data, 'ok': ok}


def read_primitive_set_object(r, cls):
    pass  # 由 read_object 分发


def main():
    data = open(PATH, 'rb').read()
    print('file size:', len(data))
    r = R(data)
    low, high = struct.unpack('<II', data[:8])
    assert (low, high) == (0x6C910EA1, 0x1AFB4545), 'bad magic'
    r.p = 8
    ty = r.u32()
    r.v = r.i32()
    attr = r.i32()
    print('type=%d version=%d attributes=0x%x' % (ty, r.v, attr))
    r.brackets = bool(attr & 0x4)
    if attr & 0x1:
        nd = r.i32()
        for _ in range(nd):
            r.string(); r.i32()
    comp = r.string()
    print('compressor=%r' % comp)
    obj = read_object(r)
    print()
    print('final pos: %d / %d' % (r.p, len(data)))
    print('bracket stack depth:', len(r.begins))
    print('OK' if r.p == len(data) else 'MISMATCH')


if __name__ == '__main__':
    main()
