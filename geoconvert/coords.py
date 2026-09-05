# -*- coding: utf-8 -*-
"""共享坐标工具：UTM/WGS84/ECEF/ENU 变换（obj/osgb/tif 转换器共用）。"""
import math

WGS84_A = 6378137.0
WGS84_F = 1.0 / 298.257223563
WGS84_E2 = WGS84_F * (2 - WGS84_F)
WGS84_EP2 = WGS84_E2 / (1 - WGS84_E2)
UTM_K0 = 0.9996


def utm_to_latlon(easting, northing, zone, northern=True):
    x = easting - 500000.0
    y = northing if northern else northing - 10000000.0
    m = y / UTM_K0
    mu = m / (WGS84_A * (1 - WGS84_E2 / 4 - 3 * WGS84_E2 ** 2 / 64 - 5 * WGS84_E2 ** 3 / 256))
    e1 = (1 - math.sqrt(1 - WGS84_E2)) / (1 + math.sqrt(1 - WGS84_E2))
    j1 = 3 * e1 / 2 - 27 * e1 ** 3 / 32
    j2 = 21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32
    j3 = 151 * e1 ** 3 / 96
    j4 = 1097 * e1 ** 4 / 512
    fp = mu + j1 * math.sin(2 * mu) + j2 * math.sin(4 * mu) + \
        j3 * math.sin(6 * mu) + j4 * math.sin(8 * mu)
    c1 = WGS84_EP2 * math.cos(fp) ** 2
    t1 = math.tan(fp) ** 2
    r1 = WGS84_A * (1 - WGS84_E2) / (1 - WGS84_E2 * math.sin(fp) ** 2) ** 1.5
    n1 = WGS84_A / math.sqrt(1 - WGS84_E2 * math.sin(fp) ** 2)
    d = x / (n1 * UTM_K0)
    lat = fp - (n1 * math.tan(fp) / r1) * (
        d ** 2 / 2
        - (5 + 3 * t1 + 10 * c1 - 4 * c1 ** 2 - 9 * WGS84_EP2) * d ** 4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1 ** 2 - 252 * WGS84_EP2 - 3 * c1 ** 2) * d ** 6 / 720)
    lon = math.radians(zone * 6 - 183) + (
        d - (1 + 2 * t1 + c1) * d ** 3 / 6
        + (5 - 2 * c1 + 28 * t1 - 3 * c1 ** 2 + 8 * WGS84_EP2 + 24 * t1 ** 2) * d ** 5 / 120) / math.cos(fp)
    return math.degrees(lat), math.degrees(lon)


def geodetic_to_ecef(lat_deg, lon_deg, h):
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    s = math.sin(lat)
    n = WGS84_A / math.sqrt(1 - WGS84_E2 * s * s)
    return (
        (n + h) * math.cos(lat) * math.cos(lon),
        (n + h) * math.cos(lat) * math.sin(lon),
        (n * (1 - WGS84_E2) + h) * math.sin(lat),
    )


def ecef_to_geodetic(x, y, z):
    lon = math.atan2(y, x)
    p = math.hypot(x, y)
    lat = math.atan2(z, p * (1 - WGS84_E2))
    h = 0.0
    for _ in range(6):
        n = WGS84_A / math.sqrt(1 - WGS84_E2 * math.sin(lat) ** 2)
        h = p / math.cos(lat) - n if abs(math.cos(lat)) > 1e-9 else abs(z) - n
        lat = math.atan2(z, p * (1 - WGS84_E2 * n / (n + h)))
    n = WGS84_A / math.sqrt(1 - WGS84_E2 * math.sin(lat) ** 2)
    h = p / math.cos(lat) - n
    return math.degrees(lat), math.degrees(lon), h


def enu_to_ecef_transform(lat_deg, lon_deg, h, rot_deg=0.0):
    """ENU(东,北,上) → ECEF 的 4x4 变换（3D Tiles 列主序 16 元素）。

    rot_deg：绕上轴顺时针旋转（北偏东为正），用于贴图平面朝向调整。"""
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    sl, cl = math.sin(lon), math.cos(lon)
    sp, cp = math.sin(lat), math.cos(lat)
    east = (-sl, cl, 0.0)
    north = (-sp * cl, -sp * sl, cp)
    up = (cp * cl, cp * sl, sp)
    org = geodetic_to_ecef(lat_deg, lon_deg, h)
    th = math.radians(rot_deg)
    c, s = math.cos(th), math.sin(th)
    col0 = tuple(east[i] * c - north[i] * s for i in range(3))
    col1 = tuple(east[i] * s + north[i] * c for i in range(3))
    return [
        col0[0], col0[1], col0[2], 0.0,
        col1[0], col1[1], col1[2], 0.0,
        up[0], up[1], up[2], 0.0,
        org[0], org[1], org[2], 1.0,
    ]


def ecef_to_enu_transform(transform):
    """逆推 ENU 变换的原点经纬度/高度（用于校验或复用既有 tileset 的位置）。"""
    org = (transform[12], transform[13], transform[14])
    lat, lon, h = ecef_to_geodetic(*org)
    return lat, lon, h
