"""Shared helpers for the texture generators (dev/src/art/*.py).

Every generator draws supersampled with Pillow and saves RGBA PNGs under dev/src/textures/<name>.png; bundle.py turns
each PNG into a texture resource named <name> (T.TEX[name] in the addon). Run with `python -I`.

Conventions (see dev/src/addon/CONTRACT.md, "Game style"):
- Anything the addon tints (glyphs, rings, pins drawn in a kind's color) is drawn WHITE; the draw color multiplies it.
  A dark edge stays dark under any tint.
- Icons that carry their own colors are drawn in color and drawn by the addon with a white tint.
- Thin lines, flat fills, no glow, no gradients beyond antialiasing. Square-ish, chamfered corners.
- Sizes: power of two isn't required. Keep each texture small (most under 64 px): every distinct texture costs the
  loader one screen GUI per world.
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools', '_pylib'))
from PIL import Image, ImageChops, ImageDraw, ImageFilter  # noqa: E402

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
TEXTURES = os.path.join(ROOT, 'textures')
ADDON = os.path.join(ROOT, 'addon')

# The game's HUD colors (config.lua C.RGB holds the same)
RGB = {
    'text': (255, 255, 237), 'rim': (201, 197, 170), 'me': (255, 233, 0), 'ping': (113, 245, 255),
    'objective': (255, 136, 36), 'label': (255, 156, 68), 'hostile': (255, 75, 62), 'dark': (10, 11, 12),
    'done': (140, 230, 140), 'dim': (120, 118, 104), 'white': (255, 255, 255),
    'common': (69, 255, 141), 'rare': (255, 129, 41), 'super': (255, 114, 211), 'credit': (115, 233, 242),
    'medal': (255, 221, 31), 'requisition': (255, 233, 0),
}

SS = 8  # supersampling factor


class Canvas:
    """A w x h texture drawn at SS times the size; coordinates are in final pixels, y DOWN (Pillow's way)."""

    def __init__(self, w, h, ss=SS):
        self.w, self.h, self.ss = w, h, ss
        self.img = Image.new('RGBA', (w * ss, h * ss), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)

    def P(self, x, y):
        return (x * self.ss, y * self.ss)

    def poly(self, pts, fill):
        self.d.polygon([self.P(x, y) for x, y in pts], fill=fill)

    def rect(self, x0, y0, x1, y1, fill):
        self.d.rectangle([self.P(x0, y0), self.P(x1, y1)], fill=fill)

    def circle(self, cx, cy, r, fill=None, outline=None, width=0):
        s = self.ss
        self.d.ellipse([(cx - r) * s, (cy - r) * s, (cx + r) * s, (cy + r) * s], fill=fill, outline=outline,
                       width=int(round(width * s)) if width else 0)

    def ring(self, cx, cy, r, width, fill):
        """A ring centered on radius r, `width` pixels thick."""
        self.circle(cx, cy, r + width / 2, outline=fill, width=width)

    def stroke(self, pts, width, fill, closed=False, cap='square'):
        """A polyline with mitered joints (bevel past a 4x miter) and square (or 'butt') caps."""
        stroke_polyline(self, pts, width, fill, closed, cap)

    def finish(self, edge=0.0, edge_alpha=150):
        """Downsampled image; edge > 0 adds a dark outline that many pixels wide around the ink (for legibility)."""
        img = self.img.resize((self.w, self.h), Image.LANCZOS)
        if edge > 0:
            img = add_edge(img, edge, edge_alpha)
        return img


def _norm(dx, dy):
    l = math.hypot(dx, dy)
    return (dx / l, dy / l) if l > 1e-9 else (0.0, 0.0)


def stroke_polyline(cv, pts, width, fill, closed=False, cap='square'):
    h = width / 2
    pts = [tuple(p) for p in pts]
    if len(pts) == 1:
        x, y = pts[0]
        cv.rect(x - h, y - h, x + h, y + h, fill)
        return
    if closed and pts[0] != pts[-1]:
        pts = pts + [pts[0]]
    n = len(pts)
    segs = []
    for i in range(n - 1):
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        dx, dy = _norm(x1 - x0, y1 - y0)
        segs.append((dx, dy))
        ex0 = ex1 = 0.0
        if cap == 'square' and not closed:
            if i == 0:
                ex0 = h
            if i == n - 2:
                ex1 = h
        ax, ay = x0 - dx * ex0, y0 - dy * ex0
        bx, by = x1 + dx * ex1, y1 + dy * ex1
        nx, ny = -dy * h, dx * h
        cv.poly([(ax + nx, ay + ny), (bx + nx, by + ny), (bx - nx, by - ny), (ax - nx, ay - ny)], fill)
    # joints
    joints = list(range(1, n - 1))
    if closed:
        joints.append(0)
    for j in joints:
        d1 = segs[j - 1] if j > 0 else segs[-1]
        d2 = segs[j] if j < len(segs) else segs[0]
        vx, vy = pts[j]
        for sgn in (1, -1):
            n1 = (-d1[1] * sgn, d1[0] * sgn)
            n2 = (-d2[1] * sgn, d2[0] * sgn)
            mx, my = n1[0] + n2[0], n1[1] + n2[1]
            ml = math.hypot(mx, my)
            if ml < 1e-6:
                continue
            cos_half = ml / 2
            k = h / cos_half
            if k > 4 * h:  # too sharp: bevel
                cv.poly([(vx, vy), (vx + n1[0] * h, vy + n1[1] * h), (vx + n2[0] * h, vy + n2[1] * h)], fill)
                continue
            mpx, mpy = vx + mx / ml * k, vy + my / ml * k
            cv.poly([(vx, vy), (vx + n1[0] * h, vy + n1[1] * h), (mpx, mpy), (vx + n2[0] * h, vy + n2[1] * h)], fill)


def add_edge(img, edge, alpha=150, rgb=RGB['dark']):
    """A dark outline `edge` pixels wide (fractional ok) behind the ink."""
    a = img.getchannel('A')
    up = 4
    big = a.resize((a.width * up, a.height * up), Image.LANCZOS)
    r = max(1, int(round(edge * up)))
    grown = big.filter(ImageFilter.MaxFilter(2 * r + 1)).resize(a.size, Image.LANCZOS)
    grown = grown.point(lambda v: v * alpha // 255)
    under = Image.new('RGBA', img.size, rgb + (0,))
    under.putalpha(grown)
    return Image.alpha_composite(under, img)


def save(img, name):
    """Write dev/src/textures/<name>.png (name like 'icons/medal'); returns the path."""
    path = os.path.join(TEXTURES, *name.split('/')) + '.png'
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)
    return path


def clear(prefix):
    """Delete every PNG under dev/src/textures/<prefix>/ (a generator owns its folder and rewrites it whole)."""
    base = os.path.join(TEXTURES, *prefix.split('/'))
    if not os.path.isdir(base):
        return
    for dp, _, files in os.walk(base):
        for f in files:
            if f.endswith('.png'):
                os.remove(os.path.join(dp, f))


def contact_sheet(names, out, cell=64, bg=(48, 52, 46, 255), cols=12):
    """A preview of textures on a terrain-ish background (for eyeballing)."""
    imgs = [Image.open(os.path.join(TEXTURES, *n.split('/')) + '.png') for n in names]
    rows = (len(imgs) + cols - 1) // cols
    sheet = Image.new('RGBA', (cols * cell, max(1, rows) * cell), bg)
    for i, im in enumerate(imgs):
        s = min(1.0, (cell - 4) / max(im.width, im.height))
        if s < 1:
            im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
        x = (i % cols) * cell + (cell - im.width) // 2
        y = (i // cols) * cell + (cell - im.height) // 2
        sheet.alpha_composite(im, (x, y))
    sheet.save(out)
    return out
