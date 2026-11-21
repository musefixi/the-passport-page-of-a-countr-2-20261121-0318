#!/usr/bin/env python3
"""Draw the data-page spread of a passport from Sorvena, a country that
isn't there.

Pure Python 3 standard library: a small framebuffer renderer, a vector
stroke font for the document typography, a 5x7 pixel font for the
machine-readable zone (with real ICAO check digits), and a zlib PNG
encoder. No network, no PIL, no assets. Deterministic: two runs produce
byte-identical output.

The document: Republic of Sorvena, a small mountain-and-coast republic
whose language, Sorvenian, is printed beside English in every field.
Holder Marta Ellin Voran of Valdora, passport issued 03 JUN 2021, valid
to 03 JUN 2031. The facing page carries her travel history inside that
validity: Drevania by the Brelin Pass road border (Aug 2022, on a
multiple-entry visa sticker), Ostravia by air (Feb 2023), and Lumenport
by ferry (Sep 2024) -- plus the telling paperwork: by the Treaty of
Valdora no visa is needed for the first two, and Sorvena's mountain
toll stamp, paid in Valdora, because the holder is a licensed guide of
the High Sorvenian Alps and toll-exempt by endorsement.
"""

import math
import os
import struct
import zlib
from pathlib import Path

# ---------------------------------------------------------------- canvas

W, H = 1024, 640          # final image size
SS = 2                    # supersample factor
CW, CH = W * SS, H * SS   # canvas size

PAPER = (243, 238, 224)
PAPER_D = (232, 224, 203)
NAVY = (26, 41, 74)
INK = (40, 40, 46)
GREY = (96, 98, 104)
FAINT = (178, 186, 178)
TEAL = (43, 92, 84)
GOLD = (148, 114, 42)
DARKRED = (148, 40, 38)
STAMP_BLUE = (40, 66, 142)
STAMP_BLUE2 = (30, 52, 116)
STAMP_PURPLE = (98, 54, 132)
STAMP_RED = (160, 54, 44)
STAMP_GREEN = (32, 108, 64)

FB = bytearray(CW * CH * 3)


def blend(c1, c2, t):
    return (int(c1[0] + (c2[0] - c1[0]) * t),
            int(c1[1] + (c2[1] - c1[1]) * t),
            int(c1[2] + (c2[2] - c1[2]) * t))


def put(x, y, color):
    if 0 <= x < CW and 0 <= y < CH:
        i = (y * CW + x) * 3
        FB[i] = color[0]
        FB[i + 1] = color[1]
        FB[i + 2] = color[2]


def rect(x, y, w, h, color):
    """Filled rectangle in final-image coordinates."""
    x0, y0 = int(x * SS), int(y * SS)
    x1, y1 = int((x + w) * SS), int((y + h) * SS)
    x0 = max(0, x0)
    y0 = max(0, y0)
    x1 = min(CW, x1)
    y1 = min(CH, y1)
    if x1 <= x0 or y1 <= y0:
        return
    row = bytes(color) * (x1 - x0)
    for yy in range(y0, y1):
        i = (yy * CW + x0) * 3
        FB[i:i + len(row)] = row


def rect_blend(x, y, w, h, color, t):
    """Rectangle blended toward the existing pixels by t (0..1)."""
    x0, y0 = max(0, int(x * SS)), max(0, int(y * SS))
    x1, y1 = min(CW, int((x + w) * SS)), min(CH, int((y + h) * SS))
    for yy in range(y0, y1):
        base = (yy * CW) * 3
        for xx in range(x0, x1):
            i = base + xx * 3
            FB[i] = int(FB[i] + (color[0] - FB[i]) * t)
            FB[i + 1] = int(FB[i + 1] + (color[1] - FB[i + 1]) * t)
            FB[i + 2] = int(FB[i + 2] + (color[2] - FB[i + 2]) * t)


def poly(points, color):
    """Filled polygon, points in final-image coordinates."""
    pts = [(px * SS, py * SS) for px, py in points]
    ys = [p[1] for p in pts]
    y0, y1 = max(0, int(min(ys))), min(CH - 1, int(max(ys)) + 1)
    n = len(pts)
    for yy in range(y0, y1 + 1):
        cy = yy + 0.5
        xs = []
        for i in range(n):
            ax, ay = pts[i]
            bx, by = pts[(i + 1) % n]
            if (ay <= cy < by) or (by <= cy < ay):
                xs.append(ax + (cy - ay) * (bx - ax) / (by - ay))
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            xa, xb = int(xs[i]), int(xs[i + 1])
            for xx in range(max(0, xa), min(CW, xb + 1)):
                put(xx, yy, color)


def line(x1, y1, x2, y2, color, w=1.2):
    """Thick line as a quad."""
    dx, dy = x2 - x1, y2 - y1
    ln = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / ln * w / 2, dx / ln * w / 2
    poly([(x1 + nx, y1 + ny), (x2 + nx, y2 + ny),
          (x2 - nx, y2 - ny), (x1 - nx, y1 - ny)], color)
    disc(x1, y1, w / 2, color)
    disc(x2, y2, w / 2, color)


def disc(cx, cy, r, color):
    cx, cy, r = cx * SS, cy * SS, r * SS
    y0, y1 = max(0, int(cy - r)), min(CH - 1, int(cy + r) + 1)
    for yy in range(y0, y1 + 1):
        dy = yy + 0.5 - cy
        half = math.sqrt(max(0.0, r * r - dy * dy))
        xa, xb = int(cx - half), int(cx + half)
        for xx in range(max(0, xa), min(CW, xb + 1)):
            put(xx, yy, color)


def ellipse(cx, cy, rx, ry, color):
    cx, cy = cx * SS, cy * SS
    rx, ry = rx * SS, ry * SS
    y0, y1 = max(0, int(cy - ry)), min(CH - 1, int(cy + ry) + 1)
    for yy in range(y0, y1 + 1):
        dy = (yy + 0.5 - cy) / ry
        half = rx * math.sqrt(max(0.0, 1 - dy * dy))
        xa, xb = int(cx - half), int(cx + half)
        for xx in range(max(0, xa), min(CW, xb + 1)):
            put(xx, yy, color)


def ring(cx, cy, r, color, w=1.6):
    steps = max(24, int(r * 6))
    pts = [(cx + r * math.cos(a), cy + r * math.sin(a))
           for a in [i * 2 * math.pi / steps for i in range(steps + 1)]]
    for i in range(steps):
        line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], color, w)


def rrect(x, y, w, h, color, lw=1.6, rad=6):
    """Rounded-rectangle outline."""
    line(x + rad, y, x + w - rad, y, color, lw)
    line(x + rad, y + h, x + w - rad, y + h, color, lw)
    line(x, y + rad, x, y + h - rad, color, lw)
    line(x + w, y + rad, x + w, y + h - rad, color, lw)
    for cx, cy, a0 in ((x + rad, y + rad, 180), (x + w - rad, y + rad, 270),
                       (x + w - rad, y + h - rad, 0), (x + rad, y + h - rad, 90)):
        steps = 10
        pts = [(cx + rad * math.cos(math.radians(a0 + i * 90 / steps)),
                cy + rad * math.sin(math.radians(a0 + i * 90 / steps)))
               for i in range(steps + 1)]
        for i in range(steps):
            line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], color, lw)


# ------------------------------------------------------- vector stroke font
# Glyphs on a 0..4 x 0..7 grid, as lists of polylines.

GLYPHS = {
    'A': [[(0, 7), (2, 0), (4, 7)], [(1.1, 4.6), (2.9, 4.6)]],
    'B': [[(0, 0), (0, 7)], [(0, 0), (2.5, 0), (3.5, 1.2), (3.5, 2.3), (2.5, 3.5), (0, 3.5)],
          [(2.5, 3.5), (3.7, 4.7), (3.7, 5.9), (2.5, 7), (0, 7)]],
    'C': [[(3.8, 1.2), (2.8, 0.2), (1.2, 0.2), (0.2, 1.5), (0.2, 5.5), (1.2, 6.8), (2.8, 6.8), (3.8, 5.8)]],
    'D': [[(0, 0), (0, 7)], [(0, 0), (2.4, 0), (3.8, 2), (3.8, 5), (2.4, 7), (0, 7)]],
    'E': [[(3.6, 0), (0, 0), (0, 7), (3.6, 7)], [(0, 3.5), (2.8, 3.5)]],
    'F': [[(3.6, 0), (0, 0), (0, 7)], [(0, 3.5), (2.6, 3.5)]],
    'G': [[(3.8, 1.2), (2.8, 0.2), (1.2, 0.2), (0.2, 1.5), (0.2, 5.5), (1.2, 6.8), (2.8, 6.8), (3.8, 5.6), (3.8, 4.2), (2.4, 4.2)]],
    'H': [[(0, 0), (0, 7)], [(4, 0), (4, 7)], [(0, 3.5), (4, 3.5)]],
    'I': [[(2, 0), (2, 7)], [(0.6, 0), (3.4, 0)], [(0.6, 7), (3.4, 7)]],
    'J': [[(3.6, 0), (3.6, 5.4), (2.8, 6.8), (1.2, 6.8), (0.4, 5.6)]],
    'K': [[(0, 0), (0, 7)], [(3.8, 0), (0.4, 3.4)], [(1.2, 2.6), (3.9, 7)]],
    'L': [[(0, 0), (0, 7), (3.6, 7)]],
    'M': [[(0, 7), (0, 0), (2, 3), (4, 0), (4, 7)]],
    'N': [[(0, 7), (0, 0), (4, 7), (4, 0)]],
    'O': [[(1.2, 0.2), (2.8, 0.2), (3.8, 1.5), (3.8, 5.5), (2.8, 6.8), (1.2, 6.8), (0.2, 5.5), (0.2, 1.5), (1.2, 0.2)]],
    'P': [[(0, 7), (0, 0), (2.6, 0), (3.7, 1.2), (3.7, 2.6), (2.6, 3.8), (0, 3.8)]],
    'Q': [[(1.2, 0.2), (2.8, 0.2), (3.8, 1.5), (3.8, 5.5), (2.8, 6.8), (1.2, 6.8), (0.2, 5.5), (0.2, 1.5), (1.2, 0.2)],
          [(2.6, 5.2), (4, 7.2)]],
    'R': [[(0, 7), (0, 0), (2.6, 0), (3.7, 1.2), (3.7, 2.6), (2.6, 3.8), (0, 3.8)], [(2.2, 3.8), (3.9, 7)]],
    'S': [[(3.7, 1.1), (2.7, 0.2), (1.2, 0.2), (0.3, 1.2), (0.3, 2.4), (1.2, 3.3), (2.8, 3.9), (3.7, 4.8), (3.7, 6), (2.7, 6.9), (1.2, 6.9), (0.3, 6)]],
    'T': [[(0, 0), (4, 0)], [(2, 0), (2, 7)]],
    'U': [[(0, 0), (0, 5.4), (1, 6.8), (3, 6.8), (4, 5.4), (4, 0)]],
    'V': [[(0, 0), (2, 7), (4, 0)]],
    'W': [[(0, 0), (1, 7), (2, 3), (3, 7), (4, 0)]],
    'X': [[(0, 0), (4, 7)], [(4, 0), (0, 7)]],
    'Y': [[(0, 0), (2, 3.2), (4, 0)], [(2, 3.2), (2, 7)]],
    'Z': [[(0, 0), (4, 0), (0, 7), (4, 7)]],
    '0': [[(1.2, 0.2), (2.8, 0.2), (3.8, 1.5), (3.8, 5.5), (2.8, 6.8), (1.2, 6.8), (0.2, 5.5), (0.2, 1.5), (1.2, 0.2)]],
    '1': [[(1, 1.2), (2.2, 0), (2.2, 7)], [(0.8, 7), (3.4, 7)]],
    '2': [[(0.3, 1.3), (1.2, 0.2), (2.8, 0.2), (3.7, 1.3), (3.7, 2.6), (0.2, 7), (3.8, 7)]],
    '3': [[(0.4, 1.1), (1.4, 0.2), (2.7, 0.2), (3.6, 1.2), (3.6, 2.4), (2.6, 3.4), (1.4, 3.4)],
          [(2.6, 3.4), (3.7, 4.6), (3.7, 5.9), (2.7, 6.9), (1.3, 6.9), (0.3, 6)]],
    '4': [[(2.6, 7), (2.6, 0), (0, 4.6), (4, 4.6)]],
    '5': [[(3.7, 0), (0.4, 0), (0.3, 3.3), (2.5, 3.1), (3.7, 4.3), (3.7, 5.9), (2.6, 6.9), (1.1, 6.9), (0.3, 6)]],
    '6': [[(3.5, 1.4), (2.4, 0.3), (1.2, 0.6), (0.4, 2.2), (0.3, 5.2), (1.2, 6.8), (2.8, 6.8), (3.7, 5.6), (3.6, 4.2), (2.6, 3.4), (1.1, 3.5), (0.3, 4.4)]],
    '7': [[(0.2, 0), (3.8, 0), (1.6, 7)]],
    '8': [[(1.3, 3.4), (0.5, 2.5), (0.6, 1.1), (1.4, 0.2), (2.6, 0.2), (3.4, 1.1), (3.5, 2.5), (2.7, 3.4), (1.3, 3.4)],
          [(1.3, 3.4), (2.7, 3.4), (3.6, 4.6), (3.6, 5.9), (2.8, 6.9), (1.2, 6.9), (0.4, 5.9), (0.4, 4.6), (1.3, 3.4)]],
    '9': [[(0.5, 5.6), (1.6, 6.7), (2.8, 6.4), (3.6, 4.8), (3.7, 1.8), (2.8, 0.2), (1.3, 0.2), (0.3, 1.3), (0.4, 2.8), (1.4, 3.6), (2.9, 3.5), (3.7, 2.6)]],
    '.': [], ',': [], '-': [[(0.8, 3.5), (3.2, 3.5)]],
    '/': [[(0.6, 7), (3.4, 0)]],
    '(': [[(2.8, 0.4), (1.4, 1.8), (1.4, 5.2), (2.8, 6.6)]],
    ')': [[(1.2, 0.4), (2.6, 1.8), (2.6, 5.2), (1.2, 6.6)]],
    ':': [], '<': [[(3.4, 1), (0.6, 3.5), (3.4, 6)]],
    '+': [[(2, 1.5), (2, 5.5)], [(0.5, 3.5), (3.5, 3.5)]],
    "'": [[(2, 0), (1.7, 1.8)]],
}


def text_width(s, size, spacing=0.0):
    adv = size * 0.60 + spacing
    return adv * len(s) - spacing if s else 0.0


def draw_text(x, y, s, size, color, spacing=0.0, align='left', weight=None):
    """Stroke-font text; (x, y) is the top-left of the cap line."""
    s = s.upper()
    w = text_width(s, size, spacing)
    if align == 'center':
        x -= w / 2
    elif align == 'right':
        x -= w
    adv = size * 0.60 + spacing
    gw = size * 0.52 / 4.0     # grid unit in x
    gh = size / 7.0            # grid unit in y
    lw = weight if weight is not None else max(0.7, size * 0.075)
    for ch in s:
        if ch == '.':
            disc(x + 2 * gw, y + 6.6 * gh, lw * 0.62, color)
        elif ch == ',':
            disc(x + 2 * gw, y + 6.6 * gh, lw * 0.62, color)
            line(x + 2.3 * gw, y + 6.8 * gh, x + 1.6 * gw, y + 7.8 * gh, color, lw)
        elif ch == ':':
            disc(x + 2 * gw, y + 2.0 * gh, lw * 0.62, color)
            disc(x + 2 * gw, y + 5.2 * gh, lw * 0.62, color)
        elif ch == '·':
            disc(x + 2 * gw, y + 3.5 * gh, lw * 0.62, color)
        elif ch in GLYPHS:
            for stroke in GLYPHS[ch]:
                pts = [(x + gx * gw, y + gy * gh) for gx, gy in stroke]
                for i in range(len(pts) - 1):
                    line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], color, lw)
        x += adv
    return w


def label(x, y, en, sv, size=8.5):
    """Bilingual field label: English / Sorvenian, small caps grey."""
    draw_text(x, y, en, size, GREY, spacing=0.4)
    w = text_width(en, size, 0.4)
    draw_text(x + w + 4, y, '/ ' + sv, size, blend(GREY, TEAL, 0.35), spacing=0.4)


def field(x, y, en, sv, value, vsize=15):
    label(x, y, en, sv)
    draw_text(x, y + 12, value, vsize, INK, spacing=0.3)
    line(x, y + 12 + vsize + 5, x + 196, y + 12 + vsize + 5, FAINT, 0.8)


# ------------------------------------------------------------ pixel font (MRZ)

PIX = {
    'A': "01110 10001 10001 11111 10001 10001 10001",
    'B': "11110 10001 10001 11110 10001 10001 11110",
    'C': "01110 10001 10000 10000 10000 10001 01110",
    'D': "11100 10010 10001 10001 10001 10010 11100",
    'E': "11111 10000 10000 11110 10000 10000 11111",
    'F': "11111 10000 10000 11110 10000 10000 10000",
    'G': "01110 10001 10000 10111 10001 10001 01111",
    'H': "10001 10001 10001 11111 10001 10001 10001",
    'I': "01110 00100 00100 00100 00100 00100 01110",
    'J': "00111 00010 00010 00010 00010 10010 01100",
    'K': "10001 10010 10100 11000 10100 10010 10001",
    'L': "10000 10000 10000 10000 10000 10000 11111",
    'M': "10001 11011 10101 10101 10001 10001 10001",
    'N': "10001 11001 10101 10011 10001 10001 10001",
    'O': "01110 10001 10001 10001 10001 10001 01110",
    'P': "11110 10001 10001 11110 10000 10000 10000",
    'Q': "01110 10001 10001 10101 10101 10010 01101",
    'R': "11110 10001 10001 11110 10100 10010 10001",
    'S': "01111 10000 10000 01110 00001 00001 11110",
    'T': "11111 00100 00100 00100 00100 00100 00100",
    'U': "10001 10001 10001 10001 10001 10001 01110",
    'V': "10001 10001 10001 10001 10001 01010 00100",
    'W': "10001 10001 10001 10101 10101 10101 01010",
    'X': "10001 01010 00100 00100 01010 10001 10001",
    'Y': "10001 01010 00100 00100 00100 00100 00100",
    'Z': "11111 00001 00010 00100 01000 10000 11111",
    '0': "01110 10001 10011 10101 11001 10001 01110",
    '1': "00100 01100 00100 00100 00100 00100 01110",
    '2': "01110 10001 00001 00110 01000 10000 11111",
    '3': "11110 00001 00001 01110 00001 00001 11110",
    '4': "00010 00110 01010 10010 11111 00010 00010",
    '5': "11111 10000 11110 00001 00001 10001 01110",
    '6': "00110 01000 10000 11110 10001 10001 01110",
    '7': "11111 00001 00010 00100 01000 01000 01000",
    '8': "01110 10001 10001 01110 10001 10001 01110",
    '9': "01110 10001 10001 01111 00001 00010 01100",
    '<': "00010 00100 01000 10000 01000 00100 00010",
}


def mrz_text(x, y, s, cell=1.55, color=(30, 30, 34)):
    step = 5 * cell + 2.6
    for ch in s:
        rows = PIX[ch].split()
        for ry, row in enumerate(rows):
            for rx, bit in enumerate(row):
                if bit == '1':
                    rect(x + rx * cell, y + ry * cell, cell + 0.15, cell + 0.15, color)
        x += step


def check_digit(s):
    weights = (7, 3, 1)
    total = 0
    for i, ch in enumerate(s):
        if ch.isdigit():
            v = int(ch)
        elif ch == '<':
            v = 0
        else:
            v = ord(ch) - 55
        total += v * weights[i % 3]
    return str(total % 10)


def build_mrz():
    line1 = 'P<SRVVORAN<<MARTA<ELLIN'
    line1 = line1 + '<' * (44 - len(line1))
    doc = 'SV4820917'
    dob, exp, pers = '880314', '310603', '880314VORAN<<<'
    body = (doc + check_digit(doc) + 'SRV' + dob + check_digit(dob) + 'F'
            + exp + check_digit(exp) + pers + check_digit(pers))
    composite = check_digit(body[0:10] + body[13:20] + body[21:43])
    return line1, body + composite


# ---------------------------------------------------------------- emblem

def emblem(cx, cy, s, color):
    """Sorvena's arms: two peaks over waves, one star. s = half-width."""
    # shield
    pts = [(cx - s, cy - s), (cx + s, cy - s), (cx + s, cy + s * 0.25),
           (cx, cy + s), (cx - s, cy + s * 0.25)]
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        line(a[0], a[1], b[0], b[1], color, 1.5)
    # peaks
    line(cx - s * 0.68, cy + s * 0.18, cx - s * 0.18, cy - s * 0.52, color, 1.5)
    line(cx - s * 0.18, cy - s * 0.52, cx + s * 0.22, cy + s * 0.18, color, 1.5)
    line(cx + s * 0.05, cy + s * 0.18, cx + s * 0.48, cy - s * 0.34, color, 1.5)
    line(cx + s * 0.48, cy - s * 0.34, cx + s * 0.72, cy + s * 0.18, color, 1.5)
    # waves
    for k, yy in enumerate((0.38, 0.58)):
        pts2 = [(cx - s * 0.66 + i * s * 0.11,
                 cy + s * yy + math.sin(i * 1.4 + k) * s * 0.05) for i in range(13)]
        for i in range(12):
            line(pts2[i][0], pts2[i][1], pts2[i + 1][0], pts2[i + 1][1], color, 1.3)
    # star
    sx, sy, r = cx + s * 0.34, cy - s * 0.62, s * 0.16
    star = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        star.append((sx + rr * math.cos(ang), sy + rr * math.sin(ang)))
    poly(star, color)


# ---------------------------------------------------------------- portrait

def portrait(x, y, w, h):
    """Passport photo of Marta Ellin Voran, drawn flat like a photo booth
    portrait: dark hair, centre parting, teal blouse, plain backdrop."""
    # backdrop with soft vertical gradient
    for i in range(int(h)):
        rect(x, y + i, w, 1, blend((196, 208, 214), (168, 182, 192), i / h))
    cx = x + w / 2
    skin = (232, 186, 148)
    skin_d = (214, 164, 122)
    hair = (58, 40, 30)
    # shoulders / blouse
    poly([(x + w * 0.08, y + h), (x + w * 0.16, y + h * 0.80),
          (x + w * 0.34, y + h * 0.70), (x + w * 0.66, y + h * 0.70),
          (x + w * 0.84, y + h * 0.80), (x + w * 0.92, y + h)], TEAL)
    poly([(cx - 13, y + h * 0.70), (cx + 13, y + h * 0.70), (cx, y + h * 0.86)],
         blend(TEAL, (255, 255, 255), 0.25))
    # neck
    rect(cx - 11, y + h * 0.56, 22, h * 0.16, skin_d)
    # head
    ellipse(cx, y + h * 0.38, w * 0.235, h * 0.235, skin)
    # hair: cap + side falls
    ellipse(cx, y + h * 0.315, w * 0.25, h * 0.20, hair)
    ellipse(cx, y + h * 0.375, w * 0.225, h * 0.185, skin)
    rect(x + w * 0.245, y + h * 0.30, w * 0.075, h * 0.42, hair)
    rect(x + w * 0.68, y + h * 0.30, w * 0.075, h * 0.42, hair)
    line(cx, y + h * 0.155, cx, y + h * 0.30, hair, 2.2)  # centre parting
    # brows, eyes, nose, mouth
    eye_y = y + h * 0.40
    for sgn in (-1, 1):
        ex = cx + sgn * w * 0.088
        line(ex - 8, eye_y - 7, ex + 8, eye_y - 8, hair, 2.0)        # brow
        ellipse(ex, eye_y, 6.4, 3.4, (250, 250, 248))
        disc(ex, eye_y, 2.5, (40, 32, 28))
        line(cx + sgn * 1.5, eye_y + 12, cx + sgn * 3.5, eye_y + 26, skin_d, 1.6)
    line(cx - 9, y + h * 0.545, cx + 9, y + h * 0.545, (178, 92, 84), 2.6)
    line(cx - 9, y + h * 0.545, cx + 9, y + h * 0.545, (196, 110, 100), 1.4)
    # soft cheek shading
    ellipse(cx - w * 0.115, y + h * 0.485, 9, 5.5, blend(skin, (226, 150, 120), 0.35))
    ellipse(cx + w * 0.115, y + h * 0.485, 9, 5.5, blend(skin, (226, 150, 120), 0.35))


# ---------------------------------------------------------------- stamps

def stamp_box(x, y, w, h, color, lines_spec, lw=2.2):
    """A rectangular ink stamp; lines_spec = [(text, size), ...]."""
    rrect(x, y, w, h, color, lw=lw, rad=7)
    rrect(x + 4.5, y + 4.5, w - 9, h - 9, color, lw=0.9, rad=5)
    total = sum(sz * 1.32 for _, sz in lines_spec)
    cy = y + (h - total) / 2 + 1
    for txt, sz in lines_spec:
        draw_text(x + w / 2, cy, txt, sz, color, align='center', spacing=0.3)
        cy += sz * 1.32


def stamp_round(cx, cy, r, color, lines_spec):
    ring(cx, cy, r, color, 2.4)
    ring(cx, cy, r - 5, color, 0.9)
    total = sum(sz * 1.34 for _, sz in lines_spec)
    ty = cy - total / 2 + 1
    for txt, sz in lines_spec:
        draw_text(cx, ty, txt, sz, color, align='center', spacing=0.3)
        ty += sz * 1.34


# ---------------------------------------------------------------- pages

def guilloche(x0, x1, y0, y1, tint, seed_phase=0.0):
    """Pale wavy security lines across a page."""
    col = blend(PAPER, tint, 0.30)
    yy = y0 + 8
    k = 0
    while yy < y1 - 4:
        pts = []
        xx = x0 + 4
        while xx <= x1 - 4:
            pts.append((xx, yy + 3.2 * math.sin((xx - x0) / 46.0 + k * 0.9 + seed_phase)))
            xx += 8
        for i in range(len(pts) - 1):
            line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], col, 0.55)
        yy += 13
        k += 1
    # rosette
    rcx, rcy = (x0 + x1) / 2, (y0 + y1) / 2
    for rr in (26, 44, 62, 80):
        pts = []
        for i in range(49):
            a = i * 2 * math.pi / 48
            rad = rr + 5 * math.sin(a * 6 + seed_phase)
            pts.append((rcx + rad * math.cos(a), rcy + rad * math.sin(a) * 0.78))
        for i in range(48):
            line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], col, 0.55)


def left_page():
    x0, x1 = 24, 500
    # header
    draw_text(512 / 2 - 0, 34, 'VISAS · VISTI', 13, NAVY, align='center', spacing=1.2)
    draw_text(256, 52, 'REPUBBLICA DE SORVENA', 8, GREY, align='center', spacing=1.6)
    line(x0 + 14, 68, x1 - 14, 68, FAINT, 0.9)
    # printed treaty note
    note = [
        'BY THE TREATY OF VALDORA (1998) NO VISA IS REQUIRED',
        'FOR DREVANIA OR OSTRAVIA. LUMENPORT ADMITS SORVENIAN',
        'HOLDERS FOR 90 DAYS WITHOUT A VISA.',
    ]
    ny = 80
    for ln in note:
        draw_text(256, ny, ln, 8.6, blend(INK, TEAL, 0.25), align='center', spacing=0.2)
        ny += 12.5
    # Drevania visa sticker
    sx, sy, sw, sh = 40, 128, 288, 104
    rect(sx, sy, sw, sh, blend(PAPER, (206, 220, 205), 0.55))
    rrect(sx, sy, sw, sh, TEAL, lw=1.4, rad=4)
    rect(sx, sy, sw, 24, blend(TEAL, PAPER, 0.25))
    draw_text(sx + 12, sy + 6, 'DREVANIA - VISA', 12.5, NAVY, spacing=0.4)
    draw_text(sx + sw - 12, sy + 7, 'DV-2211-045', 10.5, DARKRED, align='right', spacing=0.3)
    draw_text(sx + 12, sy + 38, 'MULTIPLE ENTRY', 11, INK, spacing=0.3)
    draw_text(sx + 12, sy + 56, 'VALID 01 MAR 2022 — 01 MAR 2024', 10.5, INK, spacing=0.2)
    draw_text(sx + 12, sy + 74, 'HOLDER: VORAN, MARTA ELLIN', 10.5, INK, spacing=0.2)
    draw_text(sx + 12, sy + 90, 'ISSUED AT KESTREL CONSULATE', 8.6, GREY, spacing=0.2)
    # stamps
    stamp_box(344, 122, 142, 92, STAMP_BLUE,
              [('DREVANIA', 12.5), ('BRELIN PASS', 9.5), ('ARRIVAL', 10.5), ('17 AUG 2022', 12)])
    stamp_box(56, 262, 142, 92, STAMP_BLUE2,
              [('DREVANIA', 12.5), ('BRELIN PASS', 9.5), ('DEPARTURE', 10.5), ('29 AUG 2022', 12)])
    stamp_box(238, 268, 168, 92, STAMP_PURPLE,
              [('OSTRAVIA', 12.5), ('KESTREL INTL APT', 9.5), ('ARRIVAL', 10.5), ('04 FEB 2023', 12)])
    stamp_box(48, 402, 168, 92, STAMP_PURPLE,
              [('OSTRAVIA', 12.5), ('KESTREL INTL APT', 9.5), ('DEPARTURE', 10.5), ('11 FEB 2023', 12)])
    stamp_round(392, 442, 62, STAMP_RED,
                [('LUMENPORT', 12), ('FERRY TERMINAL', 8.6), ('22 SEP 2024', 11.5), ('ADMITTED 90 DAYS', 8.2)])
    # mountain toll fee stamp
    stamp_box(238, 540, 224, 54, STAMP_GREEN,
              [('MOUNTAIN TOLL - PAID', 11.5), ('40 SM · VALDORA OFFICE · 2024', 9.5)], lw=1.8)
    draw_text(x0 + 16, H - 34, '6', 11, GREY)


def right_page():
    x0, x1 = 540, 1004
    # header
    emblem(576, 58, 27, NAVY)
    draw_text(614, 34, 'REPUBBLICA DE SORVENA', 21.5, NAVY, spacing=0.6)
    draw_text(615, 62, 'REPUBLIC OF SORVENA', 9.5, GREY, spacing=2.2)
    draw_text(x1, 36, 'PASSAPORT', 13.5, TEAL, align='right', spacing=1.0)
    draw_text(x1, 54, 'PASSPORT', 9.5, GREY, align='right', spacing=1.6)
    line(x0, 92, x1, 92, NAVY, 1.5)
    line(x0, 96, x1, 96, FAINT, 0.8)
    # microprint security line under the header rule
    draw_text(x0 + 2, 99.5, 'SORVENA · SORVENA · SORVENA · SORVENA · SORVENA · '
              'SORVENA · SORVENA · SORVENA', 4.0, blend(TEAL, PAPER, 0.30), spacing=0.2)
    # type / code / number
    label(544, 108, 'TYPE', 'TIP')
    draw_text(544, 120, 'P', 15, INK)
    label(610, 108, 'CODE', 'CODI')
    draw_text(610, 120, 'SRV', 15, INK)
    label(700, 108, 'PASSPORT NO', 'NUMERO DE PASSAPORT')
    draw_text(700, 120, 'SV4820917', 16.5, DARKRED, spacing=0.4)
    # photo
    px, py, pw, ph = 544, 152, 148, 192
    portrait(px, py, pw, ph)
    rrect(px - 1.5, py - 1.5, pw + 3, ph + 3, NAVY, lw=1.6, rad=2)
    # seal overlapping photo corner
    ring(px + pw - 6, py + ph - 8, 27, blend(GOLD, PAPER, 0.15), 1.8)
    ring(px + pw - 6, py + ph - 8, 21.5, blend(GOLD, PAPER, 0.15), 0.8)
    emblem(px + pw - 6, py + ph - 8, 12.5, blend(GOLD, INK, 0.25))
    # fields beside photo
    fx = 716
    field(fx, 150, 'SURNAME', 'COGNOM', 'VORAN', 16.5)
    field(fx, 202, 'GIVEN NAMES', 'PRENOM', 'MARTA ELLIN', 15)
    field(fx, 254, 'NATIONALITY', 'NAZIONALITAT', 'SORVENIAN', 15)
    # rows below the photo: dob / sex, place of birth / issue, expiry / authority
    field(544, 392, 'DATE OF BIRTH', 'DATA DE NAIXENZA', '14 MAR 1988', 14.5)
    label(756, 392, 'SEX', 'SEXE')
    draw_text(756, 404, 'F', 14.5, INK)
    field(544, 444, 'PLACE OF BIRTH', 'LOC DE NAIXENZA', 'VALDORA', 14.5)
    field(756, 444, 'DATE OF ISSUE', "DATA D'EMISSIO", '03 JUN 2021', 14.5)
    field(544, 496, 'DATE OF EXPIRY', "DATA D'EXPIRAZIO", '03 JUN 2031', 14.5)
    field(756, 496, 'AUTHORITY', 'AUTORITAT', 'VALDORA', 14.5)
    # endorsement -- the telling detail
    ey = 536
    rect(544, ey, 460, 28, blend(PAPER, (222, 230, 214), 0.6))
    rrect(544, ey, 460, 28, TEAL, lw=0.9, rad=3)
    draw_text(552, ey + 4, 'ENDORSEMENT · ANNOTAZIO', 8, TEAL, spacing=0.5)
    draw_text(552, ey + 15.5, 'LICENSED GUIDE, HIGH SORVENIAN ALPS - MOUNTAIN TOLL EXEMPT',
              9.3, INK, spacing=0.1)
    # MRZ
    line1, line2 = build_mrz()
    rect(540, 568, 464, 56, blend(PAPER, (255, 255, 255), 0.35))
    mrz_text(552, 575, line1, cell=1.52)
    mrz_text(552, 599, line2, cell=1.52)
    draw_text(x1 - 4, H - 34, '7', 11, GREY, align='right')


def signature():
    """Holder's signature squiggle in the clear strip under the photo."""
    pts = []
    base_y = 360
    for i in range(41):
        t = i / 40
        xx = 548 + t * 100
        yy = base_y + 6 * math.sin(t * 9.0) * (1 - t * 0.3) - 5 * math.sin(t * 2.4)
        pts.append((xx, yy))
    for i in range(40):
        line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], (52, 48, 90), 1.5)
    line(548, 374, 652, 374, FAINT, 0.8)
    draw_text(548, 377, 'SIGNATURE OF HOLDER', 6.8, GREY, spacing=0.5)


def render():
    # paper base with a soft vertical falloff
    for i in range(CH):
        rect(0, i / SS, W, 1 / SS + 0.6, blend(PAPER, PAPER_D, i / CH * 0.8))
    guilloche(24, 500, 16, H - 16, TEAL, 0.0)
    guilloche(524, 1000, 16, H - 16, NAVY, 2.1)
    # outer frame
    rrect(10, 10, W - 20, H - 20, NAVY, lw=1.7, rad=8)
    rrect(15, 15, W - 30, H - 30, blend(NAVY, PAPER, 0.45), lw=0.7, rad=6)
    left_page()
    right_page()
    signature()
    # centre seam: shadow + stitch holes
    for i in range(46):
        yy = 18 + i * 13.4
        rect_blend(508, yy, 9, 5.5, (120, 112, 96), 0.35)
    for xx in range(500, 526):
        t = 1 - abs(xx - 512.5) / 13.0
        rect_blend(xx, 12, 1, H - 24, (110, 102, 88), 0.16 * t)


def downscale():
    out = bytearray(W * H * 3)
    for yy in range(H):
        for xx in range(W):
            r = g = b = 0
            for dy in range(SS):
                base = ((yy * SS + dy) * CW + xx * SS) * 3
                for dx in range(SS):
                    i = base + dx * 3
                    r += FB[i]
                    g += FB[i + 1]
                    b += FB[i + 2]
            j = (yy * W + xx) * 3
            n = SS * SS
            out[j] = r // n
            out[j + 1] = g // n
            out[j + 2] = b // n
    return bytes(out)


def png_bytes(rgb):
    def chunk(tag, data):
        c = struct.pack('>I', len(data)) + tag + data
        return c + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF)
    raw = bytearray()
    stride = W * 3
    for yy in range(H):
        raw.append(0)
        raw += rgb[yy * stride:(yy + 1) * stride]
    ihdr = struct.pack('>IIBBBBB', W, H, 8, 2, 0, 0, 0)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr)
            + chunk(b'IDAT', zlib.compress(bytes(raw), 9))
            + chunk(b'IEND', b''))


def main():
    render()
    data = png_bytes(downscale())
    assert len(data) <= 1_048_576, len(data)
    out_dir = Path(os.environ.get('MAKEFUN_OUTPUT_DIR', '/output'))
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'entry.png').write_bytes(data)
    print('entry.png', len(data), 'bytes')


if __name__ == '__main__':
    main()
