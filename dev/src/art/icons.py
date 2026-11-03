"""Loot icons in the game's shapes, flat and in color, each with a thin dark outline so it reads on any ground.

Writes dev/src/textures/icons/<kind id>.png (32 px, colored: the addon draws them with a white tint, see kinds.lua's
k.tex), dev/src/textures/ui/check.png (white, tinted by the ledger for a cleared kind) and
dev/src/textures/ui/label/<kind id>.png: the ledger's labels (CREDITS ...) baked from the 12 px glyph set
(glyphs/12/*, addon/glyphs.lua) into one white texture each, LABEL_W x 16 px, the text right-aligned LABEL_PAD px in
from the right and its baseline LABEL_PAD px up from the bottom: one draw per label instead of one per letter (rerun
this after glyphs.py changes the font).
The shapes follow the approved mockup (dev/docs/plan.txt, figures 1, 5 and 6), drawn on a 16-unit grid centered on
the texture (2 px a unit): the shape fits in +-7.2 units and its outline is 0.75 units outside it.
Run: python -I dev/src/art/icons.py
"""
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # python -I leaves the script's folder out
from lib import ADDON, ROOT, Canvas, Image, clear, contact_sheet, save

SIZE = 32                  # texture size in pixels
U = SIZE / 16.0            # pixels per grid unit
EDGE = 0.75 * U            # dark outline width (the mockup's 1.5-unit stroke drawn under the fill)
EDGE_ALPHA = 235
DARK = (11, 13, 14, 255)

KINDS = {
    'credit': (115, 233, 242), 'medal': (255, 221, 31), 'common': (69, 255, 141), 'rare': (255, 129, 41),
    'super': (255, 114, 211), 'requisition': (255, 233, 0), 'ammo': (255, 234, 128), 'grenade': (135, 170, 45),
    'stim': (60, 140, 255),
}


class Grid:
    """Drawing on the 16-unit grid: (0, 0) is the texture's center, y down."""

    def __init__(self):
        self.cv = Canvas(SIZE, SIZE)

    def p(self, x, y):
        return (SIZE / 2 + x * U, SIZE / 2 + y * U)

    def poly(self, pts, fill):
        self.cv.poly([self.p(x, y) for x, y in pts], fill)

    def rect(self, x0, y0, x1, y1, fill):
        self.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], fill)

    def circle(self, x, y, r, fill):
        cx, cy = self.p(x, y)
        self.cv.circle(cx, cy, r * U, fill=fill)

    def ellipse(self, x, y, rx, ry, fill):
        cx, cy = self.p(x, y)
        s = self.cv.ss
        self.cv.d.ellipse([(cx - rx * U) * s, (cy - ry * U) * s, (cx + rx * U) * s, (cy + ry * U) * s], fill=fill)

    def stroke(self, pts, width, fill, cap='butt'):
        self.cv.stroke([self.p(x, y) for x, y in pts], width * U, fill, cap=cap)

    def finish(self):
        return self.cv.finish(edge=EDGE, edge_alpha=EDGE_ALPHA)


def arc(cx, cy, r, a0, a1, n=24):
    """Points on a circle from angle a0 to a1 (degrees, 0 = +x, y down so positive angles turn clockwise)."""
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def qcurve(p0, c, p1, n=8):
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * c[0] + t * t * p1[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * c[1] + t * t * p1[1]) for t in (i / n for i in range(n + 1))]


def rounded_rect(x0, y0, x1, y1, r):
    pts = []
    pts += arc(x1 - r, y0 + r, r, -90, 0, 6)
    pts += arc(x1 - r, y1 - r, r, 0, 90, 6)
    pts += arc(x0 + r, y1 - r, r, 90, 180, 6)
    pts += arc(x0 + r, y0 + r, r, 180, 270, 6)
    return pts


def icon(kind):
    rgb = KINDS[kind] + (255,)
    g = Grid()
    if kind == 'medal':
        # the medal: a hexagon with a skull (a dark disc and two eyes)
        g.poly([(0, -7.2), (6.2, -3.6), (6.2, 3.6), (0, 7.2), (-6.2, 3.6), (-6.2, -3.6)], rgb)
        g.circle(0, 0, 3.3, DARK)
        g.rect(-1.7, -0.9, -0.4, 0.4, rgb)
        g.rect(0.4, -0.9, 1.7, 0.4, rgb)
    elif kind == 'common':
        # a disc split down the middle
        g.poly(arc(-0.9, 0, 6.5, 90, 270), rgb)
        g.poly(arc(0.9, 0, 6.5, -90, 90), rgb)
    elif kind == 'rare':
        # a square with its bottom-left corner cut off, and the corner beside it
        g.poly([(-6, -6), (6, -6), (6, 6), (-1, 6), (-6, 1)], rgb)
        g.poly([(-6, 3.2), (-3.2, 6), (-6, 6)], rgb)
    elif kind == 'super':
        # four squares
        for x, y in ((-5.7, -5.7), (0.7, -5.7), (-5.7, 0.7), (0.7, 0.7)):
            g.rect(x, y, x + 5, y + 5, rgb)
    elif kind == 'credit':
        # a tile with an S on it
        g.poly(rounded_rect(-6.3, -6.3, 6.3, 6.3, 1.6), rgb)
        g.stroke([(2.7, -3.3), (-1.4, -3.3), (-2.7, -2.0), (-2.7, -1.2), (-1.5, 0), (1.5, 0), (2.7, 1.2), (2.7, 2.0),
                  (1.4, 3.3), (-2.7, 3.3)], 1.7, DARK)
    elif kind == 'requisition':
        # a slip with a folded corner and three lines
        g.poly([(-5, -7), (3, -7), (5.5, -4.5), (5.5, 7), (-5, 7)], rgb)
        for y, x1 in ((-2.5, 3), (0.5, 3), (3.5, 1)):
            g.stroke([(-2.8, y), (x1, y)], 1.2, DARK)
    elif kind == 'ammo':
        # three bullets
        for x0 in (-5.75, -1.25, 3.25):
            g.poly([(x0, 6)] + qcurve((x0, -1.5), (x0 + 1.25, -6.5), (x0 + 2.5, -1.5)) + [(x0 + 2.5, 6)], rgb)
    elif kind == 'grenade':
        # a frag grenade: a round body and its cap
        g.ellipse(0, 1.6, 5, 5.4, rgb)
        g.rect(-1.8, -6.6, 1.8, -3.6, rgb)
        g.rect(-1.8, -3.9, 1.8, -3.2, DARK)
    elif kind == 'stim':
        # a cross
        g.poly([(-2, -6.5), (2, -6.5), (2, -2), (6.5, -2), (6.5, 2), (2, 2), (2, 6.5), (-2, 6.5), (-2, 2), (-6.5, 2),
                (-6.5, -2), (-2, -2)], rgb)
    return g.finish()


def check():
    """The ledger's check for a cleared kind: white (tinted green), a thin dark outline."""
    g = Grid()
    g.stroke([(-5.0, 0.2), (-1.6, 3.6), (5.0, -3.6)], 2.0, (255, 255, 255, 255), cap='square')
    return g.cv.finish(edge=0.6 * U, edge_alpha=200)


# the ledger's labels (ledger.lua LABELS: keep the two the same) and their textures' size (ledger.lua LABEL_W, _H, _PAD)
LABELS = {'credit': 'CREDITS', 'medal': 'MEDALS', 'common': 'COMMON', 'rare': 'RARE', 'super': 'SUPER',
          'requisition': 'REQ', 'ammo': 'AMMO', 'grenade': 'GRENADES', 'stim': 'STIMS'}
LABEL_CAP, LABEL_W, LABEL_H, LABEL_PAD = 12, 96, 16, 2


def glyph_set(cap):
    """(gap, space, pad, {byte: (advance in caps, texture w, texture h)}) of one glyph set, from addon/glyphs.lua"""
    src = open(os.path.join(ADDON, 'glyphs.lua'), encoding='utf-8').read()
    gap = float(re.search('gap = ([0-9.]+)', src).group(1))
    space = float(re.search('space = ([0-9.]+)', src).group(1))
    m = re.search('[{] cap = %d, pad = ([0-9]+), chars = [{]' % cap, src)
    end = src.find('cap =', m.end())
    chunk = src[m.end():end if end > 0 else len(src)]
    chars = {int(b): (float(a), int(w), int(h)) for b, a, w, h in
             re.findall('([0-9]+)] = [{] ([0-9.]+), ([0-9]+), ([0-9]+) [}]', chunk)}
    return gap, space, int(m.group(1)), chars


def label(text, gs):
    """one label laid out the way draw.lua's D.text does it at cap LABEL_CAP, right-aligned (white glyphs)"""
    gap, space, pad, chars = gs
    cap = LABEL_CAP
    xs, x = [], 0.0
    for i, ch in enumerate(text):
        b = ord(ch)
        if b == 32:
            x += space * cap + gap * cap
            continue
        xs.append((x, b))
        x += chars[b][0] * cap + gap * cap
    width = x - gap * cap
    x0 = LABEL_W - LABEL_PAD - width                  # the text's origin: right-aligned
    assert x0 >= LABEL_PAD, text + ' does not fit in LABEL_W'
    img = Image.new('RGBA', (LABEL_W, LABEL_H), (255, 255, 255, 0))
    for x, b in xs:
        g = Image.open(os.path.join(ROOT, 'textures', 'glyphs', str(cap), '%d.png' % b)).convert('RGBA')
        # the glyph's cap box bottom-left sits pad px in from its texture's bottom-left; mine sits LABEL_PAD px up
        top = LABEL_H - LABEL_PAD + pad - g.height
        img.alpha_composite(g, (int(round(x0 + x - pad)), top))
    return img


def main():
    clear('icons')
    clear('ui')
    names = []
    for kind in KINDS:
        save(icon(kind), 'icons/' + kind)
        names.append('icons/' + kind)
    save(check(), 'ui/check')
    names.append('ui/check')
    gs = glyph_set(LABEL_CAP)
    assert len(gs[3]) > 40, 'glyphs.lua: the %d px set not found' % LABEL_CAP
    for kind, text in LABELS.items():
        save(label(text, gs), 'ui/label/' + kind)
        names.append('ui/label/' + kind)
    out = os.path.join(ROOT, '..', 'out', 'art')
    os.makedirs(out, exist_ok=True)
    sheet = contact_sheet(names, os.path.join(out, 'icons.png'), cell=40, cols=10)
    total = sum(os.path.getsize(os.path.join(ROOT, 'textures', *n.split('/')) + '.png') for n in names)
    print('%d textures, %d bytes; preview %s' % (len(names), total, os.path.normpath(sheet)))
    import game_icons
    game_icons.main()   # the game's own icons replace the drawn ones


if __name__ == '__main__':
    main()
