"""The corner radar's textures (radar.lua): a miniature of the game's map, flat, thin, cream-white.

Writes dev/src/textures/radar/ (about 0.49 MB of GPU data, half of it the rim, the one large texture):
  rim           256 px: the rim, one thin ring (#C9C5AA), in color, drawn with a white tint. Nothing else is baked in:
                the grid, the north tick and the N are drawn over it so they can turn with the view
  disc          128 px: the panel, a white disc (tinted dark at the panel opacity), its edge under the rim's line
  cone/01..32   my view cone, white (tinted the player's yellow, faint). The texture is centered CONE_OFF units out
                along the cone's axis (not on its apex), so it only has to hold the cone; pre-rotated clockwise
                (i-1)*360/32 degrees from screen-up, and radar.lua moves its center out along that frame's bearing
  me            my dot and ring, white with a dark edge (tinted the player's yellow)
  cross/01..08  a crossing of the game's 65 m grid: a thin "+", white (tinted cream, faint), 16 px, its arms 6 px from
                the center; pre-rotated clockwise (i-1)*90/8 degrees (a "+" repeats every 90 degrees)
  ring          a structure or nest: a thin white ring around a small dot, over a dark outline (tinted kind.rgb);
                32 px, the ring 12 px in radius (the 0.8 mock's hollow ring)
  north/01..32  the north tick: a small triangle pointing out of the rim (up when turn = 0), white with a dark edge
                (tinted cream), centered, pre-rotated like the cone
Geometry is in the mockup's units: the rim radius is 100 units (radar.lua scales by R/100).
Run: python -I dev/src/art/radar.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # python -I leaves the script's folder out
from lib import RGB, ROOT, Canvas, Image, clear, contact_sheet, save  # noqa: E402

RIM, RIM_PX = 256, 124     # the rim texture's size and the rim's radius in it (pixels); drawn 2 * R * RIM / (2 * RIM_PX)
DISC, DISC_PX = 128, 62    # the same for the disc
CONE, CONE_FRAMES = 24, 32
CONE_SPAN, CONE_OFF = 28.0, 13.0               # the cone texture spans 28 units, centered 13 units from the apex
NORTH, NORTH_FRAMES = 24, 32
ME = 32
CROSS, CROSS_FRAMES, CROSS_ARM = 16, 8, 6.0
RING, RING_PX = 32, 12.0


def rot(x, y, deg):
    """Turn a point (y down) clockwise by deg degrees about the origin."""
    a = math.radians(deg)
    return x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)


def disc():
    cv = Canvas(DISC, DISC)
    c = DISC / 2
    cv.circle(c, c, DISC_PX, fill=(255, 255, 255, 255))
    return cv.finish()


def rim():
    """The rim alone: a ring 1.1 units wide on the rim's radius."""
    c, u = RIM / 2, RIM_PX / 100.0
    edge_rgb = RGB['rim']
    cv = Canvas(RIM, RIM)
    cv.ring(c, c, RIM_PX, 1.1 * u, (edge_rgb[0], edge_rgb[1], edge_rgb[2], 205))
    return cv.finish()


def cone(turn):
    """The view cone: a sector 24 units long, 22 degrees each side; its apex CONE_OFF units below the center."""
    cv = Canvas(CONE, CONE)
    c, u = CONE / 2, CONE / CONE_SPAN
    pts = [(0, CONE_OFF)]
    for i in range(17):
        a = -22.2 + 44.4 * i / 16
        x, y = rot(0, -24, a)
        pts.append((x, y + CONE_OFF))
    cv.poly([(c + x * u, c + y * u) for x, y in (rot(px, py, turn) for px, py in pts)], (255, 255, 255, 255))
    return cv.finish()


def me():
    """My dot (radius 3.2 units, dark stroke) and a ring (radius 6, 1.2 wide); 2 px a unit."""
    cv = Canvas(ME, ME)
    c, u = ME / 2, 2.0
    cv.ring(c, c, 6.0 * u, 1.3 * u, (255, 255, 255, 255))
    cv.circle(c, c, 4.1 * u, fill=(10, 11, 12, 255))
    cv.circle(c, c, 3.2 * u, fill=(255, 255, 255, 255))
    return cv.finish(edge=0.9, edge_alpha=130)


def cross(turn):
    """A grid crossing: a "+" with arms CROSS_ARM px long, 1.3 px wide, turned clockwise by turn degrees."""
    cv = Canvas(CROSS, CROSS)
    c = CROSS / 2
    for a in (0, 90):
        x0, y0 = rot(0, -CROSS_ARM, turn + a)
        cv.stroke([(c + x0, c + y0), (c - x0, c - y0)], 1.3, (255, 255, 255, 255), cap='butt')
    return cv.finish()


def ring():
    """A hollow ring (radius RING_PX, 2.4 px wide) and a small center dot, both over a dark outline."""
    cv = Canvas(RING, RING)
    c = RING / 2
    dark = RGB['dark']
    cv.ring(c, c, RING_PX, 5.4, (dark[0], dark[1], dark[2], 200))
    cv.circle(c, c, 3.1, fill=(dark[0], dark[1], dark[2], 200))
    cv.ring(c, c, RING_PX, 2.4, (255, 255, 255, 255))
    cv.circle(c, c, 1.9, fill=(255, 255, 255, 255))
    return cv.finish()


def north(turn):
    """A triangle pointing out of the rim (up when turn = 0), centered: 8 units wide, 6.6 tall (NORTH px = 12 units)."""
    cv = Canvas(NORTH, NORTH)
    c, u = NORTH / 2, NORTH / 12.0
    pts = [(0, -3.3), (4.0, 3.3), (-4.0, 3.3)]
    cv.poly([(c + x * u, c + y * u) for x, y in (rot(px, py, turn) for px, py in pts)], (255, 255, 255, 255))
    return cv.finish(edge=1.0, edge_alpha=225)


def main():
    clear('radar')
    names = []

    def put(img, n):
        save(img, n)
        names.append(n)

    put(rim(), 'radar/rim')
    put(disc(), 'radar/disc')
    for i in range(CONE_FRAMES):
        put(cone(i * 360.0 / CONE_FRAMES), 'radar/cone/%02d' % (i + 1))
    put(me(), 'radar/me')
    for i in range(CROSS_FRAMES):
        put(cross(i * 90.0 / CROSS_FRAMES), 'radar/cross/%02d' % (i + 1))
    put(ring(), 'radar/ring')
    for i in range(NORTH_FRAMES):
        put(north(i * 360.0 / NORTH_FRAMES), 'radar/north/%02d' % (i + 1))
    out = os.path.join(ROOT, '..', 'out', 'art')
    os.makedirs(out, exist_ok=True)
    sheet = contact_sheet(names, os.path.join(out, 'radar.png'), cell=64, cols=16)
    total, gpu = 0, 0
    for n in names:
        path = os.path.join(ROOT, 'textures', *n.split('/')) + '.png'
        total += os.path.getsize(path)
        with Image.open(path) as im:
            gpu += im.size[0] * im.size[1] * 4
    print('%d textures, %d bytes of PNG, %d bytes as RGBA8; preview %s' % (len(names), total, gpu,
                                                                          os.path.normpath(sheet)))


if __name__ == '__main__':
    main()
