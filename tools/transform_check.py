# -*- coding: utf-8 -*-
"""验证 UTM(SRSOrigin) -> WGS84 -> ENU(h=0)->ECEF 矩阵能否复现现有 kumishi transform。"""
import json
import math

# metadata.xml: EPSG:32645 (UTM 45N), SRSOrigin=(621038.4, 4671925.0, 808.3)
E, N, Z0 = 621038.400000, 4671925.000000, 808.300000
ZONE = 45

A = 6378137.0
F = 1 / 298.257223563
E2 = F * (2 - F)
EP2 = E2 / (1 - E2)
K0 = 0.9996


def utm_to_latlon(easting, northing, zone, northern=True):
    x = easting - 500000.0
    y = northing if northern else northing - 10000000.0
    m = y / K0
    mu = m / (A * (1 - E2 / 4 - 3 * E2 ** 2 / 64 - 5 * E2 ** 3 / 256))
    e1 = (1 - math.sqrt(1 - E2)) / (1 + math.sqrt(1 - E2))
    j1 = 3 * e1 / 2 - 27 * e1 ** 3 / 32
    j2 = 21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32
    j3 = 151 * e1 ** 3 / 96
    j4 = 1097 * e1 ** 4 / 512
    fp = mu + j1 * math.sin(2 * mu) + j2 * math.sin(4 * mu) + \
        j3 * math.sin(6 * mu) + j4 * math.sin(8 * mu)
    ep2p = EP2
    c1 = ep2p * math.cos(fp) ** 2
    t1 = math.tan(fp) ** 2
    r1 = A * (1 - E2) / (1 - E2 * math.sin(fp) ** 2) ** 1.5
    n1 = A / math.sqrt(1 - E2 * math.sin(fp) ** 2)
    d = x / (n1 * K0)
    lat = fp - (n1 * math.tan(fp) / r1) * (
        d ** 2 / 2
        - (5 + 3 * t1 + 10 * c1 - 4 * c1 ** 2 - 9 * ep2p) * d ** 4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1 ** 2 - 252 * ep2p - 3 * c1 ** 2) * d ** 6 / 720)
    lon = math.radians(zone * 6 - 183) + (
        d - (1 + 2 * t1 + c1) * d ** 3 / 6
        + (5 - 2 * c1 + 28 * t1 - 3 * c1 ** 2 + 8 * ep2p + 24 * t1 ** 2) * d ** 5 / 120) / math.cos(fp)
    return math.degrees(lat), math.degrees(lon)


def geodetic_to_ecef(lat_deg, lon_deg, h):
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    s = math.sin(lat)
    n = A / math.sqrt(1 - E2 * s * s)
    return (
        (n + h) * math.cos(lat) * math.cos(lon),
        (n + h) * math.cos(lat) * math.sin(lon),
        (n * (1 - E2) + h) * math.sin(lat),
    )


def enu_to_ecef_transform(lat_deg, lon_deg, h):
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    sl, cl = math.sin(lon), math.cos(lon)
    sp, cp = math.sin(lat), math.cos(lat)
    east = (-sl, cl, 0.0)
    north = (-sp * cl, -sp * sl, cp)
    up = (cp * cl, cp * sl, sp)
    org = geodetic_to_ecef(lat_deg, lon_deg, h)
    # column-major 16 元素
    return [
        east[0], east[1], east[2], 0.0,
        north[0], north[1], north[2], 0.0,
        up[0], up[1], up[2], 0.0,
        org[0], org[1], org[2], 1.0,
    ]


lat, lon = utm_to_latlon(E, N, ZONE)
print('SRSOrigin -> lat=%.7f lon=%.7f' % (lat, lon))

for h in (0.0, Z0):
    t = enu_to_ecef_transform(lat, lon, h)
    print('h=%-7.1f translation=(%.3f, %.3f, %.3f)' % (h, t[12], t[13], t[14]))

ts = json.load(open(r'D:\WEB\zicaiduck\www\public\kumishi\tileset.json'))
have = ts['root']['transform']
print('existing  translation=(%.3f, %.3f, %.3f)' % (have[12], have[13], have[14]))
t0 = enu_to_ecef_transform(lat, lon, 0.0)
diff = max(abs(a - b) for a, b in zip(t0, have))
print('max |mine(h=0) - existing| = %.4f' % diff)
print('existing transform:', ['%.6f' % v for v in have[:12]])
print('mine     transform:', ['%.6f' % v for v in t0[:12]])
