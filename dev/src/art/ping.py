"""Waypoint and map-selection art (pings.lua, overlay.lua): white, tinted by the addon (cream for my own marks).

Writes dev/src/textures/ping/:
  wp     the waypoint glyph: a thin diamond outline around a small solid diamond, with a dark edge (32 px; drawn
         16-30 px on screen)
  ring   the map selection's hover ring: one thin ring with a dark edge (64 px; the ring 26 px in radius)
Run: python -I dev/src/art/ping.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # python -I leaves the script's folder out
from lib import ROOT, Canvas, clear, contact_sheet, save  # noqa: E402

WP = 32
RING = 64
WHITE = (255, 255, 255, 255)


def wp():
    cv = Canvas(WP, WP)
    c = WP / 2
    o = 12.5                                   # outer diamond's half-diagonal
    cv.stroke([(c, c - o), (c + o, c), (c, c + o), (c - o, c)], 2.2, WHITE, closed=True)
    i = 4.6                                    # the solid center
    cv.poly([(c, c - i), (c + i, c), (c, c + i), (c - i, c)], WHITE)
    return cv.finish(edge=1.2, edge_alpha=160)


def ring():
    cv = Canvas(RING, RING)
    cv.ring(RING / 2, RING / 2, 26, 2.0, WHITE)
    return cv.finish(edge=1.2, edge_alpha=150)


def main():
    clear('ping')
    names = ['ping/wp', 'ping/ring']
    save(wp(), 'ping/wp')
    save(ring(), 'ping/ring')
    out = os.path.join(ROOT, '..', 'out', 'art')
    os.makedirs(out, exist_ok=True)
    sheet = contact_sheet(names, os.path.join(out, 'ping.png'), cell=64, cols=4)
    total = sum(os.path.getsize(os.path.join(ROOT, 'textures', *n.split('/')) + '.png') for n in names)
    print('%d textures, %d bytes; preview %s' % (len(names), total, os.path.normpath(sheet)))


if __name__ == '__main__':
    main()
