"""The open map's overlay art (overlay.lua, legend.lua, ui.lua): drawn at 2x the size they show at 1080p, so a
1080p draw is an exact 2:1 shrink and 1440p / 4K stay sharp.

Writes dev/src/textures/ov/:
  nest_m, nest_s   a nest on the map: a dark halo, a hostile ring and a centre dot, in color (drawn white-tinted,
                   20 px box at 1080p; the ring 6.2 / 4.8 px in radius, as in the 0.8 mock)
  disc             a white disc (40 px), tinted black and faint behind each loot icon
  rr/fill_<c>      a rounded panel's corner, filled inside its outline (c = tl tr bl br; 6 px for a 3 px radius)
  rr/line_<c>      the same corner's outline (a quarter annulus, a third of the radius thick)
  chev/01..16      the waypoint's off-map chevron, white with a dark edge, pointing up then turned 22.5 degrees
                   clockwise per frame (D.rot; 32 px, drawn 16 px)
Run: python -I dev/src/art/map_overlay.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # python -I leaves the script's folder out
from lib import RGB, ROOT, Canvas, clear, contact_sheet, save  # noqa: E402

X = 2                       # texture pixels per 1080p screen pixel
WHITE = (255, 255, 255, 255)
NEST = 20                   # the nest's box at 1080p
NEST_R = {'nest_m': 6.2, 'nest_s': 4.8}
RR = 3                      # the panels' corner radius at 1080p
CHEV, CHEV_N = 16, 16


def nest(r):
    n = NEST * X
    cv = Canvas(n, n)
    c = n / 2
    # Pillow draws an outline inward from the circle's edge, the mock's way: halo r-2.5..r+1.1, ring r-1.7..r
    cv.circle(c, c, (r + 1.1) * X, outline=RGB['dark'] + (200,), width=3.6 * X)
    cv.circle(c, c, r * X, outline=RGB['hostile'] + (255,), width=1.7 * X)
    cv.circle(c, c, 1.5 * X, fill=RGB['hostile'] + (255,))
    return cv.finish()


def disc():
    n = 20 * X
    cv = Canvas(n, n)
    cv.circle(n / 2, n / 2, n / 2, fill=WHITE)
    return cv.finish()


def corner(which, line):
    """The quarter disc (or annulus) whose centre is the panel's inner corner point."""
    n = RR * X
    cv = Canvas(n, n)
    # the arc's centre, in this texture: tl's is its bottom-right corner, and so on (y down)
    cx = n if which[1] == 'l' else 0
    cy = n if which[0] == 't' else 0
    if line:
        cv.circle(cx, cy, n, outline=WHITE, width=n / 3)
    else:
        cv.circle(cx, cy, n * 2 / 3, fill=WHITE)      # up to the outline's inner edge: the two never overlap
    return cv.finish()


def chevron(deg):
    n = CHEV * X
    cv = Canvas(n, n)
    c = n / 2
    pts = [(0, -11), (11, 8), (0, 2), (-11, 8)]     # a filled arrowhead pointing up, around the centre (texture px)
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    cv.poly([(c + x * ca - y * sa, c + x * sa + y * ca) for x, y in pts], WHITE)   # y down: +deg is clockwise
    return cv.finish(edge=1.6, edge_alpha=170)


def main():
    clear('ov')
    names = []

    def put(img, name):
        save(img, name)
        names.append(name)

    for name, r in NEST_R.items():
        put(nest(r), 'ov/' + name)
    put(disc(), 'ov/disc')
    for which in ('tl', 'tr', 'bl', 'br'):
        put(corner(which, False), 'ov/rr/fill_' + which)
        put(corner(which, True), 'ov/rr/line_' + which)
    for i in range(CHEV_N):
        put(chevron(i * 360 / CHEV_N), 'ov/chev/%02d' % (i + 1))
    out = os.path.join(ROOT, '..', 'out', 'art')
    os.makedirs(out, exist_ok=True)
    sheet = contact_sheet(names, os.path.join(out, 'map_overlay.png'), cell=48, cols=9)
    total = sum(os.path.getsize(os.path.join(ROOT, 'textures', *n.split('/')) + '.png') for n in names)
    print('%d textures, %d bytes; preview %s' % (len(names), total, os.path.normpath(sheet)))


if __name__ == '__main__':
    main()
