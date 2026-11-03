"""Map icons for objectives, structures, nests, points of interest and extraction: WHITE, flat, thin, tinted at draw
time with the kind's color (D.icon(kind, cx, cy, size, alpha, layer, tint)). A thin dark edge keeps them readable on
any ground (it stays dark under every tint). Built to read at 12 to 20 px.

Writes dev/src/textures/map/<name>.png (32 px) and a preview, dev/out/art_map_icons.png.
Which kind uses which icon: dev/tools/gen_structures.py (tex_for). Shared, few textures: each costs the loader a GUI.
Run: python -I dev/src/art/map_icons.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # python -I leaves the script's folder out
from lib import ROOT, Canvas, clear, contact_sheet, save  # noqa: E402

SIZE = 32                  # texture size in pixels (drawn at 12-20 px)
U = SIZE / 16.0            # pixels per grid unit: shapes live on a 16-unit grid, (0, 0) at the center, y down
EDGE = 0.55 * U            # dark outline width
EDGE_ALPHA = 210
W = (255, 255, 255, 255)
CUT = (0, 0, 0, 0)
LINE = 1.7                 # stroke width in grid units (3.4 px at 32, about 1.5 px at 14)
OUT = os.path.normpath(os.path.join(ROOT, '..', 'out'))


class Grid:
    def __init__(self):
        self.cv = Canvas(SIZE, SIZE)

    def p(self, x, y):
        return (SIZE / 2 + x * U, SIZE / 2 + y * U)

    def poly(self, pts, fill=W):
        self.cv.poly([self.p(x, y) for x, y in pts], fill)

    def circle(self, x, y, r, fill=W):
        cx, cy = self.p(x, y)
        self.cv.circle(cx, cy, r * U, fill=fill)

    def stroke(self, pts, width=LINE, fill=W, closed=False, cap='butt'):
        self.cv.stroke([self.p(x, y) for x, y in pts], width * U, fill, closed=closed, cap=cap)

    def finish(self):
        return self.cv.finish(edge=EDGE, edge_alpha=EDGE_ALPHA)


def arc(cx, cy, r, a0, a1, n=20):
    """points on a circle, angles in degrees, 0 = +x (east), clockwise on screen (y down)"""
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def regular(cx, cy, r, n, rot=0.0):
    return [(cx + r * math.cos(math.radians(rot + 360.0 * i / n)), cy + r * math.sin(math.radians(rot + 360.0 * i / n)))
            for i in range(n)]


# ---------------------------------------------------------------------------------------------- the icons
def objective(g):
    """main objective: a diamond frame around a solid diamond"""
    r = 6.6
    g.stroke([(0, -r), (r, 0), (0, r), (-r, 0)], closed=True)
    s = 2.7
    g.poly([(0, -s), (s, 0), (0, s), (-s, 0)])


def side(g):
    """side (tactical) objective: a chamfered square frame around a solid square"""
    r, c = 5.6, 1.8
    g.stroke([(-r + c, -r), (r - c, -r), (r, -r + c), (r, r - c), (r - c, r), (-r + c, r), (-r, r - c), (-r, -r + c)],
             closed=True)
    s = 2.0
    g.poly([(-s, -s), (s, -s), (s, s), (-s, s)])


def nest(g):
    """bug nest: a burrow ring with six claws"""
    g.stroke(arc(0, 0, 3.6, 0, 360, 36), width=1.9, closed=True)
    for i in range(6):
        a = math.radians(i * 60 + 30)
        ca, sa = math.cos(a), math.sin(a)
        tx, ty = -sa, ca
        r0, r1, w = 4.3, 7.4, 1.05
        g.poly([(ca * r0 + tx * w, sa * r0 + ty * w), (ca * r1, sa * r1), (ca * r0 - tx * w, sa * r0 - ty * w)])


def outpost(g):
    """Automaton outpost / fabricator: a factory with a saw-tooth roof and a chimney"""
    g.poly([(-7, 6.4), (-7, -0.6), (-4, -3.6), (-4, -0.6), (-1, -3.6), (-1, -0.6), (2, -3.6), (2, -0.6),
            (3.4, -0.6), (3.4, -7), (6.6, -7), (6.6, 6.4)])
    g.poly([(-1.4, 6.5), (-1.4, 2.6), (1.4, 2.6), (1.4, 6.5)], fill=CUT)


def illuminate(g):
    """Illuminate structure: a triangle frame with an eye"""
    g.stroke(regular(0, 1.0, 7.0, 3, -90), closed=True, width=1.6)
    g.circle(0, 1.6, 1.9)


def tower(g):
    """jammer / detector / antenna tower: a pylon with a head and radio arcs"""
    g.stroke([(-3.6, 7.2), (0, -2.2), (3.6, 7.2)], width=1.6)
    g.stroke([(-2.1, 3.4), (2.1, 3.4)], width=1.4)
    g.circle(0, -3.6, 1.7)
    for r in (3.6, 6.2):
        g.stroke(arc(0, -3.6, r, -40, 40, 10), width=1.4)
        g.stroke(arc(0, -3.6, r, 140, 220, 10), width=1.4)


def silo(g):
    """ICBM silo: a missile on its pad"""
    g.poly([(-1.9, -3.0), (0, -7.4), (1.9, -3.0), (1.9, 3.6), (-1.9, 3.6)])
    g.poly([(-1.9, 0.6), (-4.6, 4.4), (-4.6, 5.6), (-1.9, 3.6)])
    g.poly([(1.9, 0.6), (4.6, 4.4), (4.6, 5.6), (1.9, 3.6)])
    g.stroke([(-6.4, 6.9), (6.4, 6.9)], width=1.4)


def poi(g):
    """point of interest / cache: a question mark"""
    pts = arc(0, -2.6, 3.4, 180, 360, 16) + arc(0, -2.6, 3.4, 0, 60, 6)[1:]
    pts += [(0.2, 0.9), (0.2, 2.6)]
    g.stroke(pts, width=2.1)
    g.circle(0.2, 5.6, 1.35)


def extract(g):
    """extraction: two chevrons up"""
    g.stroke([(-5.6, 0.2), (0, -5.4), (5.6, 0.2)], width=2.0)
    g.stroke([(-5.6, 6.2), (0, 0.6), (5.6, 6.2)], width=2.0)


def done(g):
    """done overlay: a check"""
    g.stroke([(-5.6, 0.4), (-1.8, 4.4), (5.8, -4.6)], width=2.4)


def cross(g):
    """destroyed overlay (nests, outposts): a cross"""
    g.stroke([(-4.8, -4.8), (4.8, 4.8)], width=2.4)
    g.stroke([(-4.8, 4.8), (4.8, -4.8)], width=2.4)


ICONS = [('objective', objective), ('side', side), ('nest', nest), ('outpost', outpost), ('illuminate', illuminate),
         ('tower', tower), ('silo', silo), ('poi', poi), ('extract', extract), ('done', done), ('cross', cross)]
TINTS = {'objective': (255, 136, 36), 'side': (150, 140, 255), 'nest': (255, 75, 62), 'outpost': (255, 75, 62),
         'illuminate': (255, 75, 62), 'tower': (150, 140, 255), 'silo': (255, 136, 36), 'poi': (255, 255, 237),
         'extract': (255, 136, 36), 'done': (140, 230, 140), 'cross': (140, 230, 140)}


def tinted(name, rgb, size):
    """the texture drawn at `size` px with a tint, the way the sim does it"""
    from PIL import Image, ImageChops
    im = Image.open(os.path.join(ROOT, 'textures', 'map', name + '.png')).convert('RGBA')
    im = im.resize((size, size), Image.LANCZOS)
    return ImageChops.multiply(im, Image.new('RGBA', im.size, rgb + (255,)))


def preview(out):
    """row 1: every icon white at 32 px (contact_sheet); rows 2-4: tinted at 20, 16 and 12 px on a map-like ground;
    row 5: the done look (dimmed icon with the check or cross over its lower right)"""
    from PIL import Image
    names = [n for n, _ in ICONS]
    tmp = os.path.join(OUT, 'art_map_icons_white.png')
    contact_sheet(['map/' + n for n in names], tmp, cell=40, cols=len(names))
    white = Image.open(tmp).convert('RGBA')
    cell = 40
    sheet = Image.new('RGBA', (cell * len(names), white.height + 4 * 28 + 8), (34, 40, 34, 255))
    sheet.alpha_composite(white, (0, 0))
    y = white.height + 4
    for size in (20, 16, 12):
        for i, n in enumerate(names):
            sheet.alpha_composite(tinted(n, TINTS[n], size), (i * cell + (cell - size) // 2, y + (24 - size) // 2))
        y += 28
    for i, n in enumerate(names[:9]):
        size = 16
        x0 = i * cell + (cell - size) // 2
        sheet.alpha_composite(tinted(n, (120, 118, 104), size), (x0, y + 4))
        ov = tinted('cross' if n in ('nest', 'outpost', 'illuminate') else 'done', (140, 230, 140), 10)
        sheet.alpha_composite(ov, (x0 + size - 6, y + 4 + size - 8))
    sheet = sheet.resize((sheet.width * 2, sheet.height * 2), Image.NEAREST)
    sheet.save(out)
    os.remove(tmp)
    return out


def main():
    clear('map')
    for name, fn in ICONS:
        g = Grid()
        fn(g)
        save(g.finish(), 'map/' + name)
    out = preview(os.path.join(OUT, 'art_map_icons.png'))
    print('wrote %d map icons (%d px, white) to %s; preview %s' % (len(ICONS), SIZE,
                                                                   os.path.join(ROOT, 'textures', 'map'), out))
    import game_icons
    game_icons.main()   # the game's own icons replace the drawn ones


if __name__ == '__main__':
    main()
