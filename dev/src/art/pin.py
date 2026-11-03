"""World marker pins (markers.lua): in the game's ping style, a thin diamond holding the icon on a thin stem to a ground dot.

Writes dev/src/textures/pin/:
  disc   the diamond (the old name stays): a thin white outline round a dark, see-through fill, with a dark edge;
         white so markers.lua tints it (cream, or ping cyan for my waypoint). 64 px, the diamond 26 px from its
         center to each corner (DIAMOND_PX)
  dot    the ground dot, white with a dark edge (tinted cream); the white disc is 10 px across in a 16 px texture
Run: python -I dev/src/art/pin.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # python -I leaves the script's folder out
from lib import ROOT, Canvas, clear, contact_sheet, save  # noqa: E402

DISC = 64
DIAMOND_PX = 26            # the outline's center line, from the texture's center to a corner
LINE = 2.6                 # the outline's width
DOT = 16
WHITE = (255, 255, 255, 255)


def disc():
    cv = Canvas(DISC, DISC)
    c, o = DISC / 2, DIAMOND_PX
    cv.poly([(c, c - o), (c + o, c), (c, c + o), (c - o, c)], (12, 13, 14, 150))
    cv.stroke([(c, c - o), (c + o, c), (c, c + o), (c - o, c)], LINE, WHITE, closed=True)
    return cv.finish(edge=1.1, edge_alpha=150)


def dot():
    cv = Canvas(DOT, DOT)
    cv.circle(DOT / 2, DOT / 2, 5, fill=(255, 255, 255, 255))
    return cv.finish(edge=1.5, edge_alpha=170)


def main():
    clear('pin')
    names = ['pin/disc', 'pin/dot']
    save(disc(), 'pin/disc')
    save(dot(), 'pin/dot')
    out = os.path.join(ROOT, '..', 'out', 'art')
    os.makedirs(out, exist_ok=True)
    sheet = contact_sheet(names, os.path.join(out, 'pin.png'), cell=64, cols=4)
    total = sum(os.path.getsize(os.path.join(ROOT, 'textures', *n.split('/')) + '.png') for n in names)
    print('%d textures, %d bytes; preview %s' % (len(names), total, os.path.normpath(sheet)))


if __name__ == '__main__':
    main()
