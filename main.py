#!/usr/bin/env python3
"""Koi Rider -- an entry for make.fun's ai-excited-01.

A tiny astronaut surfs a giant glowing koi as it leaps diagonally through
a neon storm: one bold shape, high-contrast saturated colour, dark dramatic
sky, motion everywhere. Pure Python 3 stdlib, no network, fully
deterministic: the same bytes come out of every run.

Run locally:  mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
Writes exactly one file: <MAKEFUN_OUTPUT_DIR>/entry.png (1024x1024).
"""

import math
import os
import random
import struct
import zlib

W = H = 1024

# ---------------------------------------------------------------------------
# Framebuffer and tiny raster helpers
# ---------------------------------------------------------------------------

fb = bytearray(W * H * 3)


def _blend(i, r, g, b, a):
    """Alpha-blend one pixel (flat index i) towards (r, g, b) by a (0..1)."""
    fb[i] = int(fb[i] + (r - fb[i]) * a + 0.5)
    fb[i + 1] = int(fb[i + 1] + (g - fb[i + 1]) * a + 0.5)
    fb[i + 2] = int(fb[i + 2] + (b - fb[i + 2]) * a + 0.5)


def disc(cx, cy, rad, color, alpha=1.0):
    """Filled disc, hard edge."""
    r, g, b = color
    x0 = max(0, int(cx - rad))
    x1 = min(W - 1, int(cx + rad) + 1)
    y0 = max(0, int(cy - rad))
    y1 = min(H - 1, int(cy + rad) + 1)
    r2 = rad * rad
    for y in range(y0, y1 + 1):
        dy = y - cy
        dx = math.sqrt(max(0.0, r2 - dy * dy))
        xa = max(x0, int(cx - dx))
        xb = min(x1, int(cx + dx))
        base = (y * W + xa) * 3
        for x in range(xa, xb + 1):
            _blend(base, r, g, b, alpha)
            base += 3


def soft_disc(cx, cy, rad, color, alpha=1.0):
    """Disc with a smooth radial falloff (a glow)."""
    r, g, b = color
    x0 = max(0, int(cx - rad))
    x1 = min(W - 1, int(cx + rad) + 1)
    y0 = max(0, int(cy - rad))
    y1 = min(H - 1, int(cy + rad) + 1)
    r2 = rad * rad
    for y in range(y0, y1 + 1):
        dy = y - cy
        dx = math.sqrt(max(0.0, r2 - dy * dy))
        xa = max(x0, int(cx - dx))
        xb = min(x1, int(cx + dx))
        base = (y * W + xa) * 3
        for x in range(xa, xb + 1):
            d2 = (x - cx) * (x - cx) + dy * dy
            fall = 1.0 - d2 / r2
            _blend(base, r, g, b, alpha * fall * fall)
            base += 3


def line(x0, y0, x1, y1, width, color, alpha=1.0):
    """Thick line drawn as a chain of small discs."""
    dist = math.hypot(x1 - x0, y1 - y0)
    steps = max(1, int(dist / max(1.0, width * 0.6)))
    for s in range(steps + 1):
        t = s / steps
        disc(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, width / 2.0, color, alpha)


def polyline(points, width, color, alpha=1.0):
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        line(x0, y0, x1, y1, width, color, alpha)


def poly(points, color, alpha=1.0):
    """Scanline-filled polygon."""
    r, g, b = color
    ys = [p[1] for p in points]
    y0 = max(0, int(min(ys)))
    y1 = min(H - 1, int(max(ys)) + 1)
    n = len(points)
    for y in range(y0, y1 + 1):
        xs = []
        for i in range(n):
            x0, ya = points[i]
            x1, yb = points[(i + 1) % n]
            if (ya <= y < yb) or (yb <= y < ya):
                t = (y - ya) / (yb - ya)
                xs.append(x0 + (x1 - x0) * t)
        xs.sort()
        for j in range(0, len(xs) - 1, 2):
            xa = max(0, int(xs[j]))
            xb = min(W - 1, int(xs[j + 1]))
            base = (y * W + xa) * 3
            for x in range(xa, xb + 1):
                _blend(base, r, g, b, alpha)
                base += 3


def ellipse_poly(cx, cy, rx, ry, angle_deg, steps=28):
    """Points of a rotated ellipse (for poly / polyline use)."""
    a = math.radians(angle_deg)
    ca, sa = math.cos(a), math.sin(a)
    pts = []
    for i in range(steps):
        t = 2.0 * math.pi * i / steps
        x = rx * math.cos(t)
        y = ry * math.sin(t)
        pts.append((cx + x * ca - y * sa, cy + x * sa + y * ca))
    return pts


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_color(c0, c1, t):
    return (int(lerp(c0[0], c1[0], t)),
            int(lerp(c0[1], c1[1], t)),
            int(lerp(c0[2], c1[2], t)))


# ---------------------------------------------------------------------------
# Scene
# ---------------------------------------------------------------------------

rng = random.Random(20261116)


def background():
    """Deep indigo night sky, darker at the bottom, with nebula glows."""
    top = (13, 16, 54)
    mid = (30, 14, 72)
    bot = (5, 6, 18)
    for y in range(H):
        if y < H // 2:
            c = lerp_color(top, mid, y / (H // 2))
        else:
            c = lerp_color(mid, bot, (y - H // 2) / (H // 2))
        row = bytes(c) * W
        fb[y * W * 3:(y + 1) * W * 3] = row
    # Soft nebula glows.
    soft_disc(720, 180, 300, (255, 40, 180), 0.30)
    soft_disc(170, 820, 300, (0, 200, 255), 0.26)
    soft_disc(880, 320, 210, (255, 180, 60), 0.22)
    soft_disc(500, 520, 340, (120, 60, 255), 0.16)


def stars():
    for _ in range(230):
        x = rng.uniform(0, W)
        y = rng.uniform(0, H)
        br = rng.uniform(0.35, 1.0)
        s = rng.uniform(0.6, 1.8)
        disc(x, y, s, (255, 255, 255), br * 0.85)
    for _ in range(14):
        x = rng.uniform(40, W - 40)
        y = rng.uniform(40, H - 40)
        ln = rng.uniform(6, 12)
        line(x - ln, y, x + ln, y, 1.2, (200, 230, 255), 0.8)
        line(x, y - ln, x, y + ln, 1.2, (200, 230, 255), 0.8)
        disc(x, y, 1.8, (255, 255, 255), 0.95)


def planet():
    """A ringed planet tucked into the top-left corner."""
    cx, cy, rad = 150, 140, 92
    soft_disc(cx, cy, rad + 26, (150, 170, 255), 0.25)
    disc(cx, cy, rad, (198, 205, 255), 1.0)
    # Bands across the planet.
    for dy, col in ((-38, (168, 178, 240)), (-8, (148, 158, 230)),
                    (26, (176, 186, 244)), (58, (150, 160, 232))):
        disc(cx, cy + dy, rad * 0.92, col, 0.55)
    disc(cx - 30, cy - 34, 20, (225, 230, 255), 0.7)
    # Ring: tilted ellipse outline, back half hidden behind the planet.
    ring = ellipse_poly(cx, cy, rad + 62, 26, -18)
    polyline(ring, 7, (120, 220, 255), 0.55)
    polyline(ring, 2.5, (220, 245, 255), 0.9)


def rain():
    """Diagonal neon rain streaks."""
    for _ in range(170):
        x = rng.uniform(-40, W)
        y = rng.uniform(-40, H)
        ln = rng.uniform(28, 70)
        col = rng.choice([(160, 230, 255), (255, 255, 255),
                          (255, 120, 220)])
        a = rng.uniform(0.08, 0.26)
        line(x, y, x - ln * 0.42, y + ln, rng.uniform(1.0, 2.0), col, a)


def lightning():
    """One jagged bolt from the top-right storm."""
    pts = [(872, 30), (806, 148), (858, 172), (782, 302),
           (836, 326), (742, 478)]
    polyline(pts, 15, (255, 220, 90), 0.22)
    polyline(pts, 7, (255, 240, 140), 0.55)
    polyline(pts, 3, (255, 255, 240), 1.0)
    branch = [(806, 148), (742, 210), (700, 236)]
    polyline(branch, 2.5, (255, 255, 240), 0.9)
    soft_disc(742, 478, 60, (255, 230, 120), 0.35)


# The koi leaps along a cubic Bezier from bottom-left to top-right.
P0 = (95.0, 905.0)
P1 = (300.0, 620.0)
P2 = (640.0, 330.0)
P3 = (925.0, 235.0)

RADII = [(0.00, 18), (0.25, 56), (0.50, 98), (0.75, 92),
         (0.90, 70), (1.00, 52)]


def bez(t):
    mt = 1.0 - t
    x = (mt ** 3 * P0[0] + 3 * mt * mt * t * P1[0]
         + 3 * mt * t * t * P2[0] + t ** 3 * P3[0])
    y = (mt ** 3 * P0[1] + 3 * mt * mt * t * P1[1]
         + 3 * mt * t * t * P2[1] + t ** 3 * P3[1])
    return x, y


def radius_at(t):
    for (t0, r0), (t1, r1) in zip(RADII, RADII[1:]):
        if t0 <= t <= t1:
            return lerp(r0, r1, (t - t0) / (t1 - t0))
    return RADII[-1][1]


def body_color(t):
    if t < 0.45:
        return lerp_color((255, 72, 40), (255, 148, 42), t / 0.45)
    return lerp_color((255, 148, 42), (255, 212, 110), (t - 0.45) / 0.55)


def tangent_at(t):
    e = 0.004
    x0, y0 = bez(max(0.0, t - e))
    x1, y1 = bez(min(1.0, t + e))
    d = math.hypot(x1 - x0, y1 - y0) or 1.0
    return (x1 - x0) / d, (y1 - y0) / d


def normal_at(t):
    tx, ty = tangent_at(t)
    nx, ny = -ty, tx
    if ny < 0:  # keep the normal pointing "down" (belly side)
        nx, ny = -nx, -ny
    return nx, ny


def koi():
    spine = [(bez(i / 60.0), radius_at(i / 60.0)) for i in range(61)]
    # Neon halo first, so the body sits inside it.
    for (x, y), r in spine:
        soft_disc(x, y, r + 17, (0, 220, 255), 0.30)
    for (x, y), r in spine:
        soft_disc(x, y, r + 8, (255, 60, 200), 0.16)
    # Body: overlapping discs along the spine.
    for i, ((x, y), r) in enumerate(spine):
        disc(x, y, r, body_color(i / 60.0), 1.0)
    # Top shade (darker red) and pale belly, offset along the normal.
    for i, ((x, y), r) in enumerate(spine):
        t = i / 60.0
        nx, ny = normal_at(t)
        disc(x - nx * r * 0.42, y - ny * r * 0.42, r * 0.55,
             (205, 42, 22), 0.45)
        disc(x + nx * r * 0.38, y + ny * r * 0.38, r * 0.58,
             (255, 236, 200), 0.8)
    # Scales: two dotted rows along the back, sizes varied like a koi's.
    for i in range(6, 58, 2):
        t = i / 60.0
        x, y = bez(t)
        nx, ny = normal_at(t)
        r = radius_at(t)
        for off in (-0.18, 0.30):
            disc(x + nx * r * off, y + ny * r * off,
                 5 + (i % 3), (255, 110, 55), 0.42)
    # Dorsal fin: wavy crest along the upper side.
    crest = []
    for i in range(20, 44):
        t = i / 60.0
        x, y = bez(t)
        nx, ny = normal_at(t)
        r = radius_at(t)
        crest.append((x - nx * r * 0.95, y - ny * r * 0.95))
    crest2 = []
    for i in range(43, 19, -1):
        t = i / 60.0
        x, y = bez(t)
        nx, ny = normal_at(t)
        r = radius_at(t)
        wave = 1.32 + 0.16 * math.sin(i * 1.1)
        crest2.append((x - nx * r * wave, y - ny * r * wave))
    poly(crest + crest2, (255, 88, 48), 0.92)
    # A lighter rim along the fin's outer edge.
    polyline(crest2, 3, (255, 170, 120), 0.8)
    # Pectoral fin near the head, lower side.
    hx, hy = bez(0.88)
    nx, ny = normal_at(0.88)
    fin = ellipse_poly(hx + nx * 62, hy + ny * 62, 46, 18, 38)
    poly(fin, (255, 120, 60), 0.85)
    # Flowing forked tail: two tapering ribbons curving away from the base.
    tx, ty = bez(0.0)
    for ctrl, end, col in (
            ((40, 850), (-30, 800), (255, 96, 52)),
            ((70, 985), (10, 1040), (235, 60, 40))):
        steps = 26
        for s in range(steps + 1):
            u = s / steps
            mt = 1.0 - u
            qx = (mt * mt * tx + 2 * mt * u * ctrl[0] + u * u * end[0])
            qy = (mt * mt * ty + 2 * mt * u * ctrl[1] + u * u * end[1])
            disc(qx, qy, lerp(20, 3, u), col, 0.92)
    # Light edge along the upper lobe.
    line(tx, ty - 10, -28, 806, 3, (255, 220, 180), 0.75)
    line(tx, ty + 10, 12, 1036, 3, (255, 220, 180), 0.75)
    # Head: eye, whiskers, mouth.
    ex, ey = bez(0.965)
    nx, ny = normal_at(0.965)
    eye_x = ex - nx * 26
    eye_y = ey - ny * 26
    disc(eye_x, eye_y, 17, (255, 255, 255), 1.0)
    disc(eye_x + 3, eye_y - 2, 8.5, (12, 12, 26), 1.0)
    disc(eye_x - 3, eye_y - 6, 3.5, (255, 255, 255), 1.0)
    sx, sy = bez(1.0)
    polyline([(sx, sy - 6), (sx + 34, sy + 4), (sx + 62, sy + 30)],
             3, (255, 236, 200), 0.9)
    polyline([(sx, sy + 8), (sx + 30, sy + 26), (sx + 52, sy + 52)],
             3, (255, 236, 200), 0.9)
    line(sx - 18, sy + 26, sx + 6, sy + 34, 4, (120, 30, 20), 0.8)


def astronaut():
    """Tiny surfer standing on the koi's back, near the head."""
    t = 0.62
    bx, by = bez(t)
    nx, ny = normal_at(t)
    tx, ty = tangent_at(t)
    # Surfboard along the tangent, sitting on the back.
    cx, cy = bx - nx * (radius_at(t) * 0.98), by - ny * (radius_at(t) * 0.98)
    board = ellipse_poly(cx, cy, 64, 11,
                         math.degrees(math.atan2(ty, tx)))
    poly(board, (245, 250, 255), 1.0)
    # Feet on the board, legs, torso.
    hip_x, hip_y = cx + 5, cy - 42
    line(cx - 17, cy - 2, hip_x - 7, hip_y, 8, (235, 238, 245), 1.0)
    line(cx + 19, cy - 2, hip_x + 7, hip_y, 8, (235, 238, 245), 1.0)
    disc(hip_x, hip_y - 12, 18, (240, 242, 248), 1.0)  # torso
    # Backpack (behind, opposite the facing direction).
    disc(hip_x - 18, hip_y - 14, 11, (180, 186, 200), 1.0)
    # Arms out for balance.
    line(hip_x - 10, hip_y - 19, hip_x - 42, hip_y - 42, 7,
         (240, 242, 248), 1.0)
    line(hip_x + 10, hip_y - 19, hip_x + 44, hip_y - 37, 7,
         (240, 242, 248), 1.0)
    disc(hip_x - 42, hip_y - 42, 6, (240, 242, 248), 1.0)
    disc(hip_x + 44, hip_y - 37, 6, (240, 242, 248), 1.0)
    # Helmet + visor.
    hx, hy = hip_x + 2, hip_y - 44
    disc(hx, hy, 26, (248, 250, 255), 1.0)
    disc(hx + 5, hy - 1, 18, (10, 22, 62), 1.0)
    disc(hx - 1, hy - 9, 5.5, (180, 230, 255), 0.95)
    disc(hx + 10, hy + 6, 3, (120, 200, 255), 0.9)
    # Red scarf streaming behind, for motion.
    scarf = [(hx - 20, hy + 7), (hx - 42, hy + 2), (hx - 64, hy + 14),
             (hx - 86, hy + 7), (hx - 108, hy + 22)]
    polyline(scarf, 7, (255, 58, 58), 1.0)
    polyline(scarf, 2.5, (255, 150, 150), 0.9)


def splash_and_streaks():
    """Water droplets where the tail leaves the sea, plus speed lines."""
    for _ in range(46):
        x = rng.uniform(40, 330)
        y = rng.uniform(830, 1010)
        r = rng.uniform(2, 7)
        col = rng.choice([(255, 255, 255), (140, 225, 255)])
        disc(x, y, r, col, rng.uniform(0.4, 0.95))
    for _ in range(10):
        x = rng.uniform(60, 320)
        y = rng.uniform(860, 1000)
        polyline(ellipse_poly(x, y, rng.uniform(14, 30), rng.uniform(5, 9),
                              rng.uniform(-30, 30), 20),
                 2, (190, 235, 255), 0.5)
    # Speed streaks parallel to the leap, just off the body.
    for i in range(26):
        t = rng.uniform(0.08, 0.95)
        x, y = bez(t)
        nx, ny = normal_at(t)
        side = rng.choice([-1, 1])
        off = radius_at(t) * rng.uniform(1.25, 1.9) * side
        sx, sy = x + nx * off, y + ny * off
        tx, ty = tangent_at(t)
        ln = rng.uniform(40, 95)
        line(sx, sy, sx + tx * ln, sy + ty * ln,
             rng.uniform(2, 4), (255, 255, 255), rng.uniform(0.15, 0.4))


def shockwave():
    """One faint neon ring around the leap's midpoint."""
    ring = ellipse_poly(520, 560, 430, 210, -32, 48)
    polyline(ring, 7, (0, 220, 255), 0.10)
    polyline(ring, 2.5, (140, 240, 255), 0.28)


def vignette():
    for cx, cy in ((-60, -60), (W + 60, -60), (-60, H + 60), (W + 60, H + 60)):
        soft_disc(cx, cy, 420, (2, 3, 10), 0.5)


def draw():
    background()
    stars()
    planet()
    rain()
    lightning()
    shockwave()
    koi()
    astronaut()
    splash_and_streaks()
    vignette()


# ---------------------------------------------------------------------------
# PNG encoder (stdlib only: zlib + struct)
# ---------------------------------------------------------------------------

def encode_png():
    raw = bytearray()
    stride = W * 3
    for y in range(H):
        raw.append(0)  # filter: None
        raw += fb[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(raw), 9)

    def chunk(typ, data):
        out = struct.pack(">I", len(data)) + typ + data
        out += struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
        return out

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", comp) + chunk(b"IEND", b""))


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    draw()
    data = encode_png()
    path = os.path.join(out_dir, "entry.png")
    with open(path, "wb") as f:
        f.write(data)
    print(f"wrote {path} ({len(data)} bytes, {W}x{H})")


if __name__ == "__main__":
    main()
