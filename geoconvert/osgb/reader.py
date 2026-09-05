# -*- coding: utf-8 -*-
"""OSGB (OSG binary, Smart3D/ContextCapture 倾斜摄影) 解析器。

依据 OSG 3.2/3.4 序列化规范实现，按 FileVersion 条件分支处理字段差异。
Attributes 不含 0x4（无 binary brackets）时括号不占字节；本解析器仅支持
未压缩（compressor == "0"）的文件。
"""
import struct

HEADER_LOW = 0x6C910EA1
HEADER_HIGH = 0x1AFB4545

# 数组类型 → (元素格式, 每元素字节数, 元素元数)
# 依据 OSG 3.2/3.4 osgDB/DataTypes 权威枚举（两版本 0-25 完全一致）：
#   0-7 标量；8-10 Vec2b/3b/4b；11 直接是 Vec4ub（OSG 枚举怪癖，无 Vec2ub/3ub）；
#   12-14 Vec2s/3s/4s；15-17 Vec2/3/4f；18-20 Vec2/3/4d；21-25 Vec2ub/3ub/2us/3us/4us；
#   26-31 为 3.4 追加的 Vec2i/3i/4i/2ui/3ui/4ui
_ARRAY_TYPES = {
    0: ('b', 1, 1),    # ID_BYTE_ARRAY
    1: ('B', 1, 1),    # ID_UBYTE_ARRAY
    2: ('h', 2, 1),    # ID_SHORT_ARRAY
    3: ('H', 2, 1),    # ID_USHORT_ARRAY
    4: ('i', 4, 1),    # ID_INT_ARRAY
    5: ('I', 4, 1),    # ID_UINT_ARRAY
    6: ('f', 4, 1),    # ID_FLOAT_ARRAY
    7: ('d', 8, 1),    # ID_DOUBLE_ARRAY
    8: ('b', 1, 2),    # ID_VEC2B_ARRAY
    9: ('b', 1, 3),    # ID_VEC3B_ARRAY
    10: ('b', 1, 4),   # ID_VEC4B_ARRAY
    11: ('B', 1, 4),   # ID_VEC4UB_ARRAY
    12: ('h', 2, 2),   # ID_VEC2S_ARRAY
    13: ('h', 2, 3),   # ID_VEC3S_ARRAY
    14: ('h', 2, 4),   # ID_VEC4S_ARRAY
    15: ('f', 4, 2),   # ID_VEC2_ARRAY
    16: ('f', 4, 3),   # ID_VEC3_ARRAY
    17: ('f', 4, 4),   # ID_VEC4_ARRAY
    18: ('d', 8, 2),   # ID_VEC2D_ARRAY
    19: ('d', 8, 3),   # ID_VEC3D_ARRAY
    20: ('d', 8, 4),   # ID_VEC4D_ARRAY
    21: ('B', 1, 2),   # ID_VEC2UB_ARRAY
    22: ('B', 1, 3),   # ID_VEC3UB_ARRAY
    23: ('H', 2, 2),   # ID_VEC2US_ARRAY
    24: ('H', 2, 3),   # ID_VEC3US_ARRAY
    25: ('H', 2, 4),   # ID_VEC4US_ARRAY
    26: ('i', 4, 2),   # ID_VEC2I_ARRAY (OSG 3.4+)
    27: ('i', 4, 3),   # ID_VEC3I_ARRAY (OSG 3.4+)
    28: ('i', 4, 4),   # ID_VEC4I_ARRAY (OSG 3.4+)
    29: ('I', 4, 2),   # ID_VEC2UI_ARRAY (OSG 3.4+)
    30: ('I', 4, 3),   # ID_VEC3UI_ARRAY (OSG 3.4+)
    31: ('I', 4, 4),   # ID_VEC4UI_ARRAY (OSG 3.4+)
}

# PrimitiveSet 类型
ID_DRAWARRAYS = 50
ID_DRAWARRAYLENGTH = 51
ID_DRAWELEMENTS_UBYTE = 52
ID_DRAWELEMENTS_USHORT = 53
ID_DRAWELEMENTS_UINT = 54


class OsgError(Exception):
    pass


class Image:
    __slots__ = ('name', 'filename', 'data', 's', 't', 'pixel_format', 'origin',
                 'internal_format', 'data_type', 'packing')

    def __init__(self):
        self.name = ''
        self.filename = ''
        self.data = b''
        self.s = 0
        self.t = 0
        self.pixel_format = 0
        self.origin = 0
        self.internal_format = 0
        self.data_type = 0
        self.packing = 1


class Texture:
    __slots__ = ('name', 'image', 'wrap_s', 'wrap_t', 'min_filter', 'mag_filter')

    def __init__(self):
        self.name = ''
        self.image = None
        self.wrap_s = 10496  # REPEAT
        self.wrap_t = 10496
        self.min_filter = 9986
        self.mag_filter = 9729


class StateSet:
    __slots__ = ('name', 'modes', 'attributes', 'texture_modes', 'texture_attributes')

    def __init__(self):
        self.name = ''
        self.modes = {}
        self.attributes = []       # [(obj, value)]
        self.texture_modes = []    # [dict per unit]
        self.texture_attributes = []


class Geometry:
    __slots__ = ('name', 'vertices', 'normals', 'texcoords', 'colors',
                 'primitives', 'state_set')

    def __init__(self):
        self.name = ''
        self.vertices = None       # list[(x, y, z)]
        self.normals = None
        self.texcoords = []        # list[list[(u, v)]]
        self.colors = None
        self.primitives = []       # list[dict]
        self.state_set = None


class Node:
    __slots__ = ('cls', 'name', 'state_set', 'children', 'drawables',
                 'file_names', 'range_list', 'range_mode', 'center', 'radius',
                 'matrix', 'database_path', 'initial_bound')

    def __init__(self, cls):
        self.cls = cls
        self.name = ''
        self.state_set = None
        self.children = []
        self.drawables = []        # Geode 的 Geometry
        self.file_names = []       # PagedLOD PerRangeDataList
        self.range_list = []       # [(min, max)]
        self.range_mode = 0        # 0=DISTANCE_FROM_EYE_POINT 1=PIXEL_SIZE_ON_SCREEN
        self.center = None
        self.radius = None
        self.matrix = None         # MatrixTransform
        self.database_path = ''
        self.initial_bound = None


class _Reader:
    def __init__(self, data, verbose=False):
        self.d = data
        self.p = 0
        self.v = 0
        self.id_map = {}
        self.verbose = verbose
        self._log = []

    def _take(self, n):
        if self.p + n > len(self.d):
            raise OsgError('EOF at %d (+%d)' % (self.p, n))
        b = self.d[self.p:self.p + n]
        self.p += n
        return b

    def u8(self):
        return self._take(1)[0]

    def i32(self):
        return struct.unpack('<i', self._take(4))[0]

    def u32(self):
        return struct.unpack('<I', self._take(4))[0]

    def f32(self):
        return struct.unpack('<f', self._take(4))[0]

    def f64(self):
        return struct.unpack('<d', self._take(8))[0]

    def string(self):
        n = self.i32()
        if n < 0 or n > (1 << 24):
            raise OsgError('bad string len %d @%d' % (n, self.p - 4))
        return self._take(n).decode('utf-8', 'replace') if n else ''

    def log(self, msg):
        if self.verbose:
            self._log.append('@%06d %s' % (self.p, msg))


# ---------- 对象读取 ----------

_LAST_READER = None


def read_osgb(data, verbose=False):
    """解析 OSGB 二进制，返回根 Node。"""
    global _LAST_READER
    if len(data) < 24:
        raise OsgError('file too small')
    low, high = struct.unpack('<II', data[:8])
    if (low, high) != (HEADER_LOW, HEADER_HIGH):
        if struct.unpack('>II', data[:8]) == (HEADER_LOW, HEADER_HIGH):
            raise OsgError('big-endian osgb unsupported')
        raise OsgError('not an osgb file')
    r = _Reader(data, verbose)
    _LAST_READER = r
    r.p = 8
    _type = r.u32()          # 1 = scene, 2 = image, 3 = object
    r.v = r.i32()            # file version
    attributes = r.i32()
    if attributes & 0x4:
        raise OsgError('binary brackets (block size) not supported')
    if attributes & 0x1:
        nd = r.i32()
        for _ in range(nd):
            r.string()
            r.i32()
    compressor = r.string()
    if compressor != '0':
        raise OsgError('compressed osgb (%s) unsupported' % compressor)
    obj = _read_object(r)
    return obj


def _read_object(r):
    cls = r.string()
    if cls == 'NULL':
        return None
    r.log('OBJ %s' % cls)
    uid = r.u32()
    if uid and uid in r.id_map:
        return r.id_map[uid]
    if cls == 'osg::PagedLOD':
        obj = Node(cls)
    elif cls == 'osg::Geode':
        obj = Node(cls)
    elif cls == 'osg::Group':
        obj = Node(cls)
    elif cls == 'osg::MatrixTransform':
        obj = Node(cls)
    elif cls == 'osg::Geometry':
        obj = Geometry()
    elif cls == 'osg::StateSet':
        obj = StateSet()
    elif cls in ('osg::Texture2D', 'osg::Texture1D'):
        obj = Texture()
    elif cls == 'osg::Material':
        obj = Node(cls)   # 只需跳过：材质不影响几何
    else:
        raise OsgError('unknown class %r @%d' % (cls, r.p))
    if uid:
        r.id_map[uid] = obj
    _read_fields(r, cls, obj)
    return obj


def _read_object_header(r, obj):
    """osg::Object 基类字段: Name / DataVariance / UserDataContainer(v>=77)"""
    obj.name = r.string()
    r.log('Name=%r' % obj.name)
    r.i32()  # DataVariance
    if r.v >= 77:
        if r.u8():
            raise OsgError('UserDataContainer not supported')


def _read_fields(r, cls, obj):
    v = r.v
    if cls == 'osg::PagedLOD':
        # associates: osg::Object osg::Node osg::LOD osg::PagedLOD（无 Group）
        _read_object_header(r, obj)
        _read_node_rest(r, obj)
        _read_lod_fields(r, obj)
        # DatabasePath (user): 框架 bool + 内部 hasp bool + string
        if r.u8():
            if r.u8():
                obj.database_path = r.string()
        if v < 70:
            r.u32()  # FrameNumberOfLastTraversal
        r.u32()  # NumChildrenThatCannotBeExpired
        r.u8()   # DisableExternalChildrenPaging
        # RangeDataList (user): 框架 bool + 文件名列表 + PriorityList
        if r.u8():
            n = r.u32()
            for _ in range(n):
                obj.file_names.append(r.string())
            pn = r.u32()
            for _ in range(pn):
                r.f32()
                r.f32()
            r.log('RangeDataList n=%d files=%r' % (n, obj.file_names[:3]))
        # Children (user): 框架 bool + 子节点列表
        if r.u8():
            n = r.u32()
            for _ in range(n):
                c = _read_object(r)
                if c is not None:
                    obj.children.append(c)
    elif cls == 'osg::Geode':
        # associates: osg::Object osg::Node osg::Geode（无 Group）
        _read_object_header(r, obj)
        _read_node_rest(r, obj)
        # Drawables (user): 框架 bool + 数量 + 对象列表
        if r.u8():
            n = r.u32()
            for _ in range(n):
                d = _read_object(r)
                if d is not None:
                    obj.drawables.append(d)
            r.log('Drawables n=%d' % len(obj.drawables))
    elif cls == 'osg::Group':
        _read_object_header(r, obj)
        _read_node_rest(r, obj)
        _read_group_children(r, obj)
    elif cls == 'osg::MatrixTransform':
        _read_object_header(r, obj)
        _read_node_rest(r, obj)
        _read_group_children(r, obj)
        # Transform: referenceFrame enum
        r.i32()
        # Matrix (matrix serializer): 16×f32
        m = struct.unpack('<16f', r._take(64))
        obj.matrix = [list(m[0:4]), list(m[4:8]), list(m[8:12]), list(m[12:16])]
    elif cls == 'osg::Geometry':
        _read_geometry(r, obj)
    elif cls == 'osg::StateSet':
        _read_stateset(r, obj)
    elif cls in ('osg::Texture2D', 'osg::Texture1D'):
        _read_texture(r, obj, cls)
    elif cls == 'osg::Material':
        _read_material_skip(r, obj)
    return obj


def _read_node_rest(r, obj):
    """Node 字段（Object 头之后）：InitialBound/callbacks/NodeMask/StateSet。"""
    if r.u8():
        obj.initial_bound = (r.f64(), r.f64(), r.f64(), r.f64())
    for cb in ('ComputeBoundingSphereCallback', 'UpdateCallback',
               'EventCallback', 'CullCallback'):
        if r.u8():
            _read_object(r)
    r.u8()   # CullingActive
    r.u32()  # NodeMask
    if r.v < 77:
        if r.u8():
            n = r.u32()
            for _ in range(n):
                r.string()
    if r.u8():
        obj.state_set = _read_object(r)


def _read_group_children(r, obj):
    """Group::Children (user serializer)。"""
    if r.u8():
        n = r.u32()
        for _ in range(n):
            c = _read_object(r)
            if c is not None:
                obj.children.append(c)


def _read_lod_fields(r, obj):
    r.i32()  # CenterMode
    if r.u8():  # UserCenter
        obj.center = (r.f64(), r.f64(), r.f64())
        obj.radius = r.f64()
    obj.range_mode = r.i32()  # RangeMode
    if r.u8():  # RangeList
        n = r.u32()
        for _ in range(n):
            obj.range_list.append((r.f32(), r.f32()))
        r.log('RangeMode=%d RangeList=%r' % (obj.range_mode, obj.range_list[:4],))


def _read_material_skip(r, obj):
    # 经 hexdump 对齐验证（库米什 v80）：Object 头 + 2 callback bool +
    # ColorMode i32 + 5 个 user 块（bool + bool + 数据）
    _read_object_header(r, obj)
    if r.u8():
        _read_object(r)  # [StateAttribute] UpdateCallback
    if r.u8():
        _read_object(r)  # [StateAttribute] EventCallback
    r.i32()  # ColorMode
    # Ambient/Diffuse/Specular/Emission: 框架 bool + frontAndBack bool + 2×Vec4
    for _ in range(4):
        if r.u8():
            r.u8()
            r._take(32)
    # Shininess: 框架 bool + frontAndBack bool + 2×f32
    if r.u8():
        r.u8()
        r._take(8)


def _read_stateset(r, ss):
    _read_object_header(r, ss)
    # ModeList
    if r.u8():
        n = r.u32()
        for _ in range(n):
            k = r.i32()
            ss.modes[k] = r.i32()
        r.log('ModeList n=%d' % n)
    else:
        r.log('ModeList absent')
    # AttributeList
    if r.u8():
        n = r.u32()
        for _ in range(n):
            o = _read_object(r)
            r.i32()  # Value
            ss.attributes.append(o)
        r.log('AttributeList n=%d' % n)
    else:
        r.log('AttributeList absent')
    # TextureModeList: size + per-unit ModeList
    if r.u8():
        n = r.u32()
        for _ in range(n):
            m = {}
            mn = r.u32()
            for _ in range(mn):
                k = r.i32()
                m[k] = r.i32()
            ss.texture_modes.append(m)
        r.log('TextureModeList n=%d' % n)
    else:
        r.log('TextureModeList absent')
    # TextureAttributeList: size + per-unit AttributeList
    if r.u8():
        n = r.u32()
        for _ in range(n):
            an = r.u32()
            lst = []
            for _ in range(an):
                o = _read_object(r)
                r.i32()
                lst.append(o)
            ss.texture_attributes.append(lst)
        r.log('TextureAttributeList n=%d units' % n)
    # UniformList (user): 框架 bool + size + [object + value i32]
    if r.u8():
        n = r.u32()
        for _ in range(n):
            _read_object(r)
            r.i32()
    r.i32()  # RenderingHint
    r.i32()  # RenderBinMode
    r.i32()  # BinNumber
    r.string()  # BinName
    r.u8()  # NestRenderBins
    if r.u8():
        _read_object(r)  # UpdateCallback
    if r.u8():
        _read_object(r)  # EventCallback


def _read_texture(r, tex, cls):
    _read_object_header(r, tex)
    # [StateAttribute] UpdateCallback / EventCallback
    if r.u8():
        _read_object(r)
    if r.u8():
        _read_object(r)
    # [Texture] WRAP_S/T/R、MIN/MAG_FILTER (user: bool + i32)
    for name in ('WRAP_S', 'WRAP_T', 'WRAP_R', 'MIN_FILTER', 'MAG_FILTER'):
        if r.u8():
            val = r.i32()
            if name == 'WRAP_S':
                tex.wrap_s = val
            elif name == 'WRAP_T':
                tex.wrap_t = val
            elif name == 'MIN_FILTER':
                tex.min_filter = val
            elif name == 'MAG_FILTER':
                tex.mag_filter = val
    r.f32()  # MaxAnisotropy
    r.u8()   # UseHardwareMipMapGeneration
    r.u8()   # UnRefImageDataAfterApply
    r.u8()   # ClientStorageHint
    r.u8()   # ResizeNonPowerOfTwoHint
    r._take(32)  # BorderColor 4×f64
    r.i32()  # BorderWidth
    r.i32()  # InternalFormatMode (enum)
    if r.u8():
        r.i32()  # InternalFormat (user)
    if r.u8():
        r.i32()  # SourceFormat (user)
    if r.u8():
        r.i32()  # SourceType (user)
    r.u8()   # ShadowComparison
    r.i32()  # ShadowCompareFunc
    r.i32()  # ShadowTextureMode
    r.f32()  # ShadowAmbient
    # v>=95: ImageAttachment; v>=98: Swizzle; v>=155: Min/MaxLOD —— v80 无
    # [Texture2D] Image (image serializer: bool + ReadImage)
    if r.u8():
        tex.image = _read_image(r)
        r.log('Image file=%r size=%dx%d bytes=%d' % (
            tex.image.filename, tex.image.s, tex.image.t,
            len(tex.image.data)))
    r.i32()  # TextureWidth
    r.i32()  # TextureHeight


def _read_image(r):
    """Image decision 语义（OSG 3.2/3.4 osgDB/DataTypes + InputStream.cpp）：
    0=IMAGE_INLINE_DATA（9×i32 参数 + u32 size + data + mipmap 表）
    1=IMAGE_INLINE_FILE（u32 size + 原始图像文件字节，Smart3D 常用）
    2=IMAGE_EXTERNAL（仅文件名） 3=IMAGE_WRITE_OUT（读时无数据）"""
    img = Image()
    if r.v > 94:
        r.string()  # ClassName "osg::Image"
    uid = r.u32()  # UniqueID
    if uid and uid in r.id_map:
        return r.id_map[uid]
    img.filename = r.string()
    r.i32()  # WriteHint
    decision = r.i32()
    r.log('Image decision=%d file=%r' % (decision, img.filename))
    if decision == 0:  # IMAGE_INLINE_DATA
        r.i32()  # Origin
        img.s = r.i32()
        img.t = r.i32()
        r.i32()  # R
        r.i32()  # InternalFormat
        img.pixel_format = r.i32()
        img.data_type = r.i32()
        img.packing = r.i32()
        r.i32()  # AllocationMode
        size = r.u32()
        if size:
            img.data = r._take(size)
        mipn = r.u32()
        for _ in range(mipn):
            r.u32()
    elif decision == 1:  # IMAGE_INLINE_FILE
        size = r.u32()
        if size:
            img.data = r._take(size)
    elif decision in (2, 3):  # IMAGE_EXTERNAL / IMAGE_WRITE_OUT
        pass
    else:
        raise OsgError('image decision %d unsupported' % decision)
    # readObjectFields("osg::Image")：Object 字段（Name/DataVariance/UserData）
    img.name = r.string()
    r.i32()  # DataVariance
    if r.v >= 77:
        if r.u8():
            _read_object(r)  # UserDataContainer
    if uid:
        r.id_map[uid] = img
    return img


def _read_geometry(r, g):
    v = r.v
    _read_object_header(r, g)
    # [Drawable] v<154: associates 无 osg::Node → 直接 Drawable 字段
    if r.u8():  # StateSet
        g.state_set = _read_object(r)
    if r.u8():  # InitialBound (OSG 3.2: BoundingBox = 2×Vec3d)
        r._take(48)
    if r.u8():  # ComputeBoundingBoxCallback
        _read_object(r)
    if r.u8():  # Shape
        _read_object(r)
    r.u8()  # SupportsDisplayList
    r.u8()  # UseDisplayList
    r.u8()  # UseVertexBufferObjects
    if r.u8():  # UpdateCallback
        _read_object(r)
    if r.u8():  # EventCallback
        _read_object(r)
    if r.u8():  # CullCallback
        _read_object(r)
    if r.u8():  # DrawCallback
        _read_object(r)
    # [Geometry] v<112: PrimitiveSetList + VertexData 系列（每个 user 序列化器
    # 都有框架 bool，readArray 内部还有 hasArray/hasIndices 两个 bool）
    n = r.u32()
    for _ in range(n):
        g.primitives.append(_read_primitive_set(r))
    if r.u8():  # VertexData 框架 bool
        g.vertices = _read_array_data(r)
    if r.u8():  # NormalData
        g.normals = _read_array_data(r)
    if r.u8():  # ColorData
        _read_array_data(r)
    if r.u8():  # SecondaryColorData
        _read_array_data(r)
    if r.u8():  # FogCoordData
        _read_array_data(r)
    # TexCoordData
    if r.u8():
        tn = r.u32()
        for _ in range(tn):
            g.texcoords.append(_read_array_data(r))
    # VertexAttribData
    if r.u8():
        an = r.u32()
        for _ in range(an):
            _read_array_data(r)
    # FastPathHint (user): check 恒 false → 二进制只写框架 bool 0
    r.u8()
    r.log('Geometry done: verts=%d prims=%d tex=%d @%d/%d' % (
        len(g.vertices or ()), len(g.primitives), len(g.texcoords),
        r.p, len(r.d)))


def _read_primitive_set(r):
    ty = r.i32()
    mode = r.i32()
    ps = {'type': ty, 'mode': mode}
    if r.v > 96:
        r.i32()  # NumInstances
    if ty == ID_DRAWARRAYS:
        ps['first'] = r.i32()
        ps['count'] = r.u32()
    elif ty == ID_DRAWARRAYLENGTH:
        ps['first'] = r.i32()
        n = r.i32()
        ps['lengths'] = [r.i32() for _ in range(n)]
    elif ty == ID_DRAWELEMENTS_UBYTE:
        n = r.i32()
        ps['indices'] = list(r._take(n))
    elif ty == ID_DRAWELEMENTS_USHORT:
        n = r.i32()
        ps['indices'] = list(struct.unpack('<%dH' % n, r._take(2 * n)))
    elif ty == ID_DRAWELEMENTS_UINT:
        n = r.i32()
        ps['indices'] = list(struct.unpack('<%dI' % n, r._take(4 * n)))
    else:
        raise OsgError('unknown primitive type %d' % ty)
    r.log('PrimitiveSet ty=%d mode=%d n=%d' % (
        ty, mode, len(ps.get('indices', ()))))
    return ps


def _read_array_data(r):
    """readArray（v<112 格式）：hasArray bool → (id, type, size, data)
    hasIndices bool → 同构数组；Binding/Normalize int32。
    注意：user 序列化器的框架 bool 由调用方读取。"""
    has = r.u8()
    arr = None
    if has:
        arr = _read_raw_array(r)
    has_idx = r.u8()
    if has_idx:
        _read_raw_array(r)
    r.i32()  # Binding
    r.i32()  # Normalize
    return arr


def _read_raw_array(r):
    arr_id = r.i32()
    ty = r.i32()
    n = r.i32()
    if ty not in _ARRAY_TYPES:
        raise OsgError('unknown array type %d @%d' % (ty, r.p))
    fmt, esz, per = _ARRAY_TYPES[ty]
    total = n * esz * per
    raw = r._take(total)
    count = n * per
    vals = list(struct.unpack('<%d%s' % (count, fmt), raw))
    if per > 1:
        arr = [tuple(vals[i:i + per]) for i in range(0, count, per)]
    else:
        arr = vals
    r.log('array id=%d type=%d n=%d' % (arr_id, ty, n))
    return arr
