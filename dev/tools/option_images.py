"""option_images: the Arsenal option images (dev/src/images/<option>.png, 256x256 RGB; 0.6.0 and on).

    python -I -B dev/tools/option_images.py              all of them
    python -I -B dev/tools/option_images.py core rotate  only these
    python -I -B dev/tools/option_images.py --sheet      also a contact sheet: dev/out/option_images_sheet.png

How each is made:
  sim crops   the mod's own draws from the simulator (dev/src/sim/sim.py runs dev/src/addon on a fake chef), each
              option's real chef.options, cropped tight on what the option draws: core, radar_off, rotate, range*,
              size*, opacity*, ledger, compass, bezel, pings, overlay, markers*, tester. Only the mod's own draws are
              taken from the sim: the ground under them is mine (dark, a checkerboard for opacity, a perspective grid
              for markers and pings), as are the stand-ins for the game's compass (ticks and N E S W) and open map (no
              text), and the marks drawn over some (arrows, the slash, dashed rims, the markers' ring on the ground).
              The ledger picture masks out the radar beside it. 0.9.3: legend* (the legend beside the open map, and
              left of the radar with the map closed) are sim crops too.
  0.9.3 mode* the "Outside the Map" pictures: the radar, compass and pins pictures as tiles (struck through when
              the pick leaves them out), mode_map_only the overlay picture; composed from the sim crops above.
  composed    loot and map kinds: the game's icons (art/game_icons.py) large and tinted
              by the kind's color. Captions use the mod's own font (art/glyphs.py), heavier.
Every image has the 0.5.1 frame: a dark ground and a 3 px gray border.

Deterministic: the scenes are fixed and the sim has no randomness. Scratch output (each scene's sim folder: its fake
APPDATA) goes to dev/out/option_images/.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEV = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(HERE, '_pylib'))
sys.path.insert(0, os.path.join(DEV, 'src', 'sim'))
sys.path.insert(0, os.path.join(DEV, 'src', 'art'))

from PIL import Image, ImageChops, ImageDraw, ImageFilter  # noqa: E402
import sim  # noqa: E402
import glyphs  # noqa: E402
import icons  # noqa: E402
import map_icons  # noqa: E402
import game_icons  # noqa: E402

OUT = os.path.join(DEV, 'src', 'images')
WORK = os.path.join(DEV, 'out', 'option_images')
SHEET = os.path.join(DEV, 'out', 'option_images_sheet.png')

N = 256                          # the image size
BG = (14, 16, 18)                # 0.5.1's ground and frame
FRAME = (60, 62, 64)
INNER = 6                        # the frame: 3 px of ground, 3 px of border
YELLOW = (255, 233, 0)           # C.RGB.me: the captions
CREAM = (255, 255, 237)          # C.RGB.text
RIM = (201, 197, 170)            # C.RGB.rim
HOSTILE = (255, 75, 62)
DARK = (11, 14, 16)

KINDS = ('credit', 'medal', 'common', 'rare', 'super', 'requisition', 'ammo', 'grenade', 'stim')
ALL_KINDS = {k: True for k in KINDS}
MAPS = {'nest': True, 'structure': True, 'objective': True, 'side_objective': True, 'poi': True, 'extract': True}

# ---------------------------------------------------------------------------------------------- scenes (sim input)
# %LOCALAPPDATA% (zoom, calibration and overlay files) moved under the sim's own fake APPDATA, the zoom file removed:
# the player's own files are never read, and the Arsenal range is what the radar starts at
LOCAL_LUA = r"""
local g = os.getenv
os.getenv = function(k) if k == 'LOCALAPPDATA' then return g('APPDATA') end return g(k) end
os.remove(g('APPDATA') .. '\\treasure_radar_zoom.txt')
"""
# track's unit list exported as track.watch when track.lua doesn't (objectives.lua shares its walks)
SYNC_LUA = r"""
local watch0 = chef.watch
chef.watch = function(kinds, every)
  local w = watch0(kinds, every)
  if every == 3 and T.mod.track and not T.mod.track.watch then T.mod.track.watch = w end
  return w
end
"""
# my waypoints, drawn by the real pings.icon (pings.lua sets waypoints from keys; a fixed list is simpler here)
WAYPOINTS_LUA = r"""
local real = T.mod.pings
T.mod.pings = { waypoints = { %s }, icon = real and real.icon }
"""


def waypoints(*pts):
    return WAYPOINTS_LUA % ', '.join('{ x = %g, y = %g, z = 0 }' % p for p in pts)


# the radar's scene: loot spread all round me out to 150 m (the default range) and past it (wedges on the rim; the
# ranges pull them in or push more out), a nest, an outpost, a jammer, a main objective, a cache, two waypoints;
# I face 20 degrees (north-north-east)
def polar(kind, bearing, dist, z=0, *rest):
    """a unit `dist` m from me at a compass bearing (degrees)"""
    a = math.radians(bearing)
    return (kind, round(dist * math.sin(a), 2), round(dist * math.cos(a), 2), z) + tuple(rest)


RADAR_UNITS = [
    polar('medal', 20, 45), polar('medal', 21, 46), polar('common', 300, 70), polar('common', 75, 60),
    polar('rare', 40, 118, 3), polar('super', 250, 95, 2), polar('requisition', 140, 42, 0.5),
    polar('credit', 200, 58, 0.5), polar('ammo', 100, 26), polar('stim', 330, 32), polar('grenade', 228, 112),
    polar('medal', 165, 100),
    polar('rare', 105, 220), polar('super', 335, 210), polar('stim', 55, 260), polar('grenade', 262, 235),
    polar('credit', 150, 205),
    polar('bug_hole_small', 285, 86), polar('bug_hole_small', 288, 90), polar('bug_hole_medium', 283, 92),
    polar('fabricator', 128, 132), polar('fabricator', 131, 136), polar('stratagem_jammer', 205, 125),
    polar('command_bunker', 15, 128), polar('bunker_cache', 350, 80),
]
RADAR_WAYPOINTS = waypoints(polar('', 352, 104)[1:3], polar('', 60, 400)[1:3])
RADAR_CAM = [(0, 0, 0, 1.6, 20, -6)]


def radar_scene(**opts):
    o = {'kinds': ALL_KINDS, 'map_kinds': MAPS}
    o.update(opts)
    return {'options': o, 'camera': RADAR_CAM, 'units': RADAR_UNITS, 'lua': LOCAL_LUA + SYNC_LUA + RADAR_WAYPOINTS}


# the ledger: five kinds seen, the requisition picked up (cleared: gray with a check)
LEDGER_SCENE = {
    'options': {'kinds': ALL_KINDS, 'ledger': True},
    'camera': RADAR_CAM,
    'units': [('medal', 6, 26, 0), ('medal', 6.6, 26.4, 0), ('medal', -48, -36, 0), ('medal', 70, 40, 0),
              ('common', -34, 64, 0), ('common', 44, -22, 0), ('common', 66, 14, 0),
              ('rare', 84, 92, 3), ('super', -118, 40, 5), ('super', -110, 140, 0),
              ('requisition', 2, 3, 0.5, 1.0)],
    'lua': LOCAL_LUA,
}

# the compass: I face north, loot within 22 degrees of it, 9 degrees apart (pips that fit the picture), more behind
# me (the chevrons at the ends), a waypoint far out
COMPASS_SCENE = {
    'options': {'kinds': ALL_KINDS, 'compass': True},
    'camera': [(0, 0, 0, 1.6, 0, -6)],
    'units': [polar('stim', -22, 12), polar('rare', -13, 92, 2), polar('medal', 4.5, 25), polar('medal', 5, 25.6),
              polar('common', 13.5, 51), polar('requisition', 22, 30, 0.5),
              polar('super', 150, 60), polar('ammo', -120, 20), polar('grenade', 110, 40)],
    'lua': LOCAL_LUA + waypoints((-12.4, 158)),
}

# the bezel: the map open, loot and marks all round (the north-east quarter is what's shown)
BEZEL_SCENE = {
    'options': {'kinds': ALL_KINDS, 'map_kinds': MAPS, 'bezel': True},
    'camera': [(0, 0, 0, 1.6, 20, -6)],
    'units': [polar('medal', 8, 25), polar('medal', 9, 26), polar('rare', 22, 92, 2), polar('common', 34, 51),
              polar('super', 47, 140), polar('credit', 58, 33), polar('ammo', 66, 12), polar('stim', 76, 18),
              polar('grenade', 84, 60), polar('requisition', 15, 70), polar('common', 52, 220),
              polar('bug_hole_small', 28, 160), polar('bug_hole_small', 28.5, 164), polar('command_bunker', 71, 260)]
             + [polar(KINDS[i % 9], 100 + i * 23, 20 + 9 * i) for i in range(12)],
    'map_open': [(0.5, 99)],
    'lua': LOCAL_LUA + SYNC_LUA + waypoints((60, 250)),
}

# the overlay: the map open with the overlay on (loot, marks and a waypoint at their places), north up, at the whole
# map (-1)
OVERLAY_SCENE = {
    'options': {'kinds': ALL_KINDS, 'map_kinds': MAPS, 'overlay': True},
    'camera': [(0, 0, 0, 1.6, 20, -6)],
    'units': [('medal', 10, 32, 0), ('medal', 10.6, 32.4, 0), ('common', -38, 60, 0), ('common', 46, -24, 0),
              ('rare', 70, 66, 3), ('super', -70, 18, 5), ('requisition', 26, 6, 0.5), ('credit', -18, -38, 0.5),
              ('ammo', 16, -60, 0), ('stim', -46, -60, 0), ('grenade', 64, -70, 0),
              ('bug_hole_small', -80, -20, 0), ('bug_hole_small', -84, -16, 0), ('fabricator', 88, 20, 0),
              ('stratagem_jammer', -20, 90, 0), ('bunker_cache', 40, 92, 0)],
    'map_open': [(0.5, 99)],
    'wheel': [(1.0, -1)],          # 0.9: the map opens at 0; one notch out to -1, the whole map, exact without a companion
    'lua': LOCAL_LUA + SYNC_LUA + waypoints((-60, 80)),
}

def aim(tx, ty, tz, ex=0.0, ey=0.0, ez=1.6):
    """yaw, pitch (degrees) from my eye to a point"""
    dx, dy, dz = tx - ex, ty - ey, tz - ez
    return math.degrees(math.atan2(dx, dy)), math.degrees(math.atan2(dz, math.hypot(dx, dy)))


def cam(t, target):
    yaw, pitch = aim(*target)
    return (t, 0, 0, 1.6, yaw, pitch)


# pings: NUM 1 sets a waypoint on the rare I aim at, then I aim at a medal: its bracket and the "Q PING" keycap
PING_MEDAL, PING_RARE = (1.5, 14, 0.3), (-1.5, 44, 0.3)
PINGS_SCENE = {
    'options': {'kinds': ALL_KINDS, 'pings': True, 'markers': 50},
    'camera': [cam(0, PING_RARE), cam(0.6, PING_RARE), cam(1.0, PING_MEDAL)],
    'units': [('medal', 1.5, 14, 0), ('rare', -1.5, 44, 0), ('common', 7, 30, 0), ('ammo', 4, 9, 0),
              ('stim', -4, 21, 0)],
    'press': [(0.3, 'numpad 1')],
    'lua': LOCAL_LUA,
}

# world markers: piles from 7 to 90 m ahead of me, in a narrow cone (25 m, 50 m and 100 m each pin a different set);
# bearings picked so no two pins overlap on screen
MARKER_UNITS = [polar('ammo', -1, 7), polar('ammo', -0.5, 7.3), polar('stim', 4.2, 11), polar('medal', -5.3, 17),
                polar('common', 8.3, 23), polar('rare', -8.3, 36, 1), polar('credit', 1.7, 46, 0.5),
                polar('super', 5.6, 68), polar('medal', -2.2, 90)]
MARKER_CAM = [(0, 0, 0, 1.6, 0, -6)]


def markers_scene(markers):
    return {'options': {'kinds': ALL_KINDS, 'markers': markers}, 'camera': MARKER_CAM, 'units': MARKER_UNITS,
            'lua': LOCAL_LUA}


# ---------------------------------------------------------------------------------------------- the sim
class Shot:
    """One frame of a scene through the sim: the mod's main-layer draws and top-layer draws, each on a clear canvas
    (no background, no stand-ins), and the frame's state (S)."""

    def __init__(self, key, scn, frame, size=(2560, 1440)):
        scn = dict(scn, name='option_images_' + key, size=size, frames=frame + 1)
        s = sim.Sim(scn, out=os.path.join(WORK, key))
        for f in range(frame + 1):
            draws = s.step(f)
        self.s, self.w, self.h = s, s.w, s.h
        main, top = [], []
        for i in range(1, len(draws) + 1):
            d = draws[i]
            (top if d.top else main).append((d.layer or 900, i, d))
        main.sort(key=lambda e: (e[0], e[1]))
        top.sort(key=lambda e: (e[0], e[1]))
        self.main = Image.new('RGBA', (s.w, s.h), (0, 0, 0, 0))
        for _, _, d in main:
            s.draw_op(self.main, d)
        self.top = Image.new('RGBA', (s.w, s.h), (0, 0, 0, 0))
        for _, _, d in top:
            s.draw_op(self.top, d)
        self.S = s.G.T.mod.main.S
        m = self.S.map
        self.map = None if m.cx is None else (m.cx, s.h - m.cy, m.r)
        self.corner = None
        cfg, radar = s.G.T.mod.config, s.G.T.mod.radar
        if cfg.RADAR and not self.S.map_open:   # the radar has its own place in the corner, not the map's
            cx, cy, r = radar.place(self.S)
            self.map = (cx, s.h - cy, r)
            self.corner = r
        self.heading = self.S.heading or 0
        warns = [s.G.SIM.warnings[i] for i in range(1, len(s.G.SIM.warnings) + 1)] + s.py_warnings
        for w in warns:
            print('  sim warning (%s): %s' % (key, w))

    def radius(self, scale=None):
        """the radar's radius in pixels (hud.lua MY_RADIUS * h * size)"""
        if self.corner and not scale:
            return self.corner
        return 0.19 * self.h * (scale or self.s.G.T.mod.config.MAP_SCALE)

    def layers(self, ground, between=None):
        """ground, then the main draws, then `between` (the open map's stand-in), then the top draws"""
        im = ground.copy()
        im.alpha_composite(self.main)
        if between is not None:
            im.alpha_composite(between)
        im.alpha_composite(self.top)
        return im


SHOTS = {}


def shot(key, scn, frame, size=(2560, 1440)):
    """a Shot, run once per key"""
    if key not in SHOTS:
        SHOTS[key] = Shot(key, scn, frame, size)
    return SHOTS[key]


def hud(sh):
    """the shot's main and top draws on one clear canvas (no stand-in between them)"""
    if not hasattr(sh, 'hud'):
        im = sh.main.copy()
        im.alpha_composite(sh.top)
        sh.hud = im
    return sh.hud


# ---------------------------------------------------------------------------------------------- picture helpers
C = N - 2 * INNER                # 244: the picture inside the frame
HUD_GROUND = (40, 44, 42)        # under the HUD crops: flat, a little lighter than BG so the dark discs show
CHECK = ((30, 33, 36), (86, 90, 94))   # the opacity pictures' checkerboard
OUTLINE = (6, 7, 8)


def rgba(rgb, a=255):
    return tuple(rgb) + (a,)


def flat(rgb, size=(C, C)):
    return Image.new('RGBA', size, rgba(rgb))


def checker(size=(C, C), cell=16):
    im = flat(CHECK[0], size)
    d = ImageDraw.Draw(im)
    for j in range(size[1] // cell + 1):
        for i in range(size[0] // cell + 1):
            if (i + j) % 2:
                d.rectangle([i * cell, j * cell, i * cell + cell - 1, j * cell + cell - 1], fill=rgba(CHECK[1]))
    return im


def cut(layer, box, size=(C, C)):
    """the part of a full-screen layer inside box (x0, y0, x1, y1: floats, may run off the screen), resized"""
    x0, y0, x1, y1 = box
    ix0, iy0, ix1, iy1 = math.floor(x0) - 2, math.floor(y0) - 2, math.ceil(x1) + 2, math.ceil(y1) + 2
    part = layer.crop((ix0, iy0, ix1, iy1))
    return part.resize(size, Image.LANCZOS, box=(x0 - ix0, y0 - iy0, x1 - ix0, y1 - iy0))


def square(cx, cy, half):
    return (cx - half, cy - half, cx + half, cy + half)


def bbox(layer, region, alpha=24):
    """the box round what's drawn (alpha over a threshold) inside region"""
    x0, y0, x1, y1 = [int(round(v)) for v in region]
    a = layer.getchannel('A').crop((x0, y0, x1, y1)).point(lambda v: 255 if v > alpha else 0)
    b = a.getbbox()
    return None if b is None else (x0 + b[0], y0 + b[1], x0 + b[2], y0 + b[3])


def union(a, b):
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def squared(box, margin=0.0, up=0.0):
    """the square round a box, `margin` (a fraction of its side) all round, moved up by `up` of its side"""
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    half = max(box[2] - box[0], box[3] - box[1]) / 2 * (1 + 2 * margin)
    return square(cx, cy - up * 2 * half, half)


def outline(img, width, alpha=225, rgb=OUTLINE):
    """a dark outline `width` px round the ink, under it (legibility over the pictures)"""
    if width <= 0:
        return img
    a = img.getchannel('A')
    big = a.resize((a.width * 2, a.height * 2), Image.BILINEAR)
    for _ in range(max(1, int(round(width * 2)))):
        big = big.filter(ImageFilter.MaxFilter(3))
    grown = big.resize(a.size, Image.BOX).point(lambda v: v * alpha // 255)
    under = Image.new('RGBA', img.size, rgba(rgb, 0))
    under.putalpha(grown)
    return Image.alpha_composite(under, img)


def text(s, cap, rgb=YELLOW, weight=0.2, edge=None):
    """s in the mod's own font (art/glyphs.py) drawn heavier, tinted, with a dark outline. Returns (image, margin):
    the ink starts `margin` px in from the image's left and top edges."""
    old = glyphs.WEIGHT
    glyphs.WEIGHT = weight
    try:
        parts, x = [], 0.0
        for ch in s:
            if ch == ' ':
                x += glyphs.SPACE * cap
                continue
            img, adv, _tw, _th, pad = glyphs.render(ch, cap)
            parts.append((img, x, pad))
            x += (adv + glyphs.GAP) * cap
        width = x - glyphs.GAP * cap
    finally:
        glyphs.WEIGHT = old
    edge = cap * 0.1 if edge is None else edge
    m = int(math.ceil(edge)) + 6
    im = Image.new('RGBA', (int(math.ceil(width)) + 2 * m, cap + 2 * m), (0, 0, 0, 0))
    for img, gx, pad in parts:
        im.alpha_composite(img, (int(round(m + gx - pad)), m - pad))
    im = ImageChops.multiply(im, Image.new('RGBA', im.size, rgba(rgb)))
    return outline(im, edge), m


def caption(pic, s, y, cap=36, rgb=YELLOW, cx=C / 2):
    """a caption centered on cx, its capitals' top at y (shrunk to fit the picture)"""
    im, m = text(s, cap, rgb)
    while im.width - 2 * m > C - 20 and cap > 16:
        cap -= 2
        im, m = text(s, cap, rgb)
    pic.alpha_composite(im, (int(round(cx - im.width / 2)), int(round(y - m))))


class Vec:
    """my own marks (arrows, rings) drawn 4x and scaled down"""

    def __init__(self, size=(C, C), ss=4):
        self.size, self.ss = size, ss
        self.im = Image.new('RGBA', (size[0] * ss, size[1] * ss), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im)

    def P(self, pts):
        return [(x * self.ss, y * self.ss) for x, y in pts]

    def line(self, pts, rgb, width, a=255):
        self.d.line(self.P(pts), fill=rgba(rgb, a), width=max(1, int(round(width * self.ss))), joint='curve')

    def poly(self, pts, rgb, a=255):
        self.d.polygon(self.P(pts), fill=rgba(rgb, a))

    def arc(self, cx, cy, r, a0, a1, rgb, width, a=255):
        """a ring piece; angles in degrees, Pillow's (0 = east, clockwise)"""
        s = self.ss
        self.d.arc([(cx - r) * s, (cy - r) * s, (cx + r) * s, (cy + r) * s], a0, a1, fill=rgba(rgb, a),
                   width=max(1, int(round(width * s))))

    def arrow(self, x0, y0, x1, y1, rgb=YELLOW, width=5, head=15):
        ang = math.atan2(y1 - y0, x1 - x0)
        ux, uy = math.cos(ang), math.sin(ang)
        bx, by = x1 - ux * head, y1 - uy * head
        self.line([(x0, y0), (bx + ux, by + uy)], rgb, width)
        px, py = -uy * head * 0.6, ux * head * 0.6
        self.poly([(x1, y1), (bx + px, by + py), (bx - px, by - py)], rgb)

    def done(self, edge=0.0):
        im = self.im.resize(self.size, Image.LANCZOS)
        return outline(im, edge)


def framed(pic):
    """the 0.5.1 frame round a C x C picture: 3 px of ground, a 3 px gray border, then the picture"""
    base = flat(BG)
    base.alpha_composite(pic)
    im = Image.new('RGB', (N, N), BG)
    ImageDraw.Draw(im).rectangle([3, 3, N - 4, N - 4], outline=FRAME, width=3)
    im.paste(base.convert('RGB'), (INNER, INNER))
    return im


# ---------------------------------------------------------------------------------------------- stand-ins
def map_standin(sh):
    """the game's open map (my stand-in, not the game's look): a dark terrain disc with a faint grid and a cream
    rim, the game's yellow player arrow at the center, north up; no text"""
    cx, cy, r = sh.map
    layer = Image.new('RGBA', (sh.w, sh.h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(36, 42, 37, 255))
    grid = Image.new('RGBA', layer.size, (0, 0, 0, 0))
    g = ImageDraw.Draw(grid)
    lw = max(1, round(sh.h / 720))
    for k in range(-4, 5):
        g.line([(cx + k * r / 4, cy - r), (cx + k * r / 4, cy + r)], fill=(70, 80, 68, 255), width=lw)
        g.line([(cx - r, cy + k * r / 4), (cx + r, cy + k * r / 4)], fill=(70, 80, 68, 255), width=lw)
    mask = Image.new('L', layer.size, 0)
    ImageDraw.Draw(mask).ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    grid.putalpha(ImageChops.multiply(grid.getchannel('A'), mask))
    layer.alpha_composite(grid)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=rgba(RIM), width=max(2, round(sh.h / 540)))
    s = sh.h / 108
    d.polygon([(cx, cy - s * 1.4), (cx + s, cy + s), (cx, cy + s * 0.4), (cx - s, cy + s)], fill=rgba(YELLOW))
    return layer


def compass_standin(sh):
    """the game's compass (my stand-in): ticks every 15 degrees where compass.lua's measured geometry puts the game's compass
    (compass.geometry(S)), longer every 45, N E S W over them; no headings"""
    g = sh.s.G.T.mod.compass.geometry(sh.S)
    cx, y, half, span = g.cx, sh.h - g.line, g.half, float(g.span)
    layer = Image.new('RGBA', (sh.w, sh.h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    hd = math.degrees(sh.heading)
    for a in range(0, 360, 15):
        rel = (a - hd + 540) % 360 - 180
        if abs(rel) > span:
            continue
        x = cx + rel / span * half
        d.line([(x, y), (x, y + sh.h * (0.012 if a % 45 == 0 else 0.006))], fill=rgba(CREAM, 170),
               width=max(1, round(sh.h / 720)))
        if a % 90 == 0:
            t, m = text('NESW'[a // 90], max(8, round(sh.h * 0.011)), CREAM, weight=0.15, edge=0)
            layer.alpha_composite(t, (int(round(x - t.width / 2)), int(round(y - sh.h * 0.006 - t.height + m))))
    return layer


def ground_standin(sh, ring):
    """the ground for the world markers (my stand-in): dark sky, dark ground, a 10 m grid on the ground seen through
    the sim's camera, and a yellow ring `ring` m round me (how far the pins reach; None: no ring)"""
    w, h = sh.w, sh.h
    layer = Image.new('RGBA', (w, h), rgba((24, 27, 30)))
    d = ImageDraw.Draw(layer)
    hz = sh.s.project(0, 100000, 0)
    hy = h - hz[1] if hz else 0
    d.rectangle([0, hy, w, h], fill=rgba((40, 44, 40)))
    lw = max(2, round(h / 480))

    def poly(pts, fill, width):
        seg = []
        for p in pts:
            q = sh.s.project(*p)
            if q is None:
                if len(seg) > 1:
                    d.line(seg, fill=fill, width=width)
                seg = []
            else:
                seg.append((q[0], h - q[1]))
        if len(seg) > 1:
            d.line(seg, fill=fill, width=width)

    for yy in range(10, 160, 10):
        poly([(x, yy, 0) for x in range(-80, 81, 4)], (66, 72, 66, 255), lw)
    for xx in range(-60, 61, 10):
        poly([(xx, yy, 0) for yy in range(2, 161, 2)], (66, 72, 66, 255), lw)
    if ring:
        poly([(ring * math.sin(math.radians(a)), ring * math.cos(math.radians(a)), 0) for a in range(-80, 81, 2)],
             rgba(YELLOW, 190), lw + 1)
    return layer


# ---------------------------------------------------------------------------------------------- the pictures
RADAR_FRAME = 240


def radar_shot(key, cam=None, screen=(2560, 1440), **opts):
    scn = radar_scene(**opts)
    if cam:
        scn['camera'] = cam
    return shot(key, scn, RADAR_FRAME, screen)


def radar_pic(sh, half=1.1, ground=None, center=None, r=None):
    """the radar cut round its center, `half` radii (of r, default its own) from the center to the picture's edge,
    its center at `center` in the picture; returns the picture and the radar's center and radius in it"""
    cx, cy, _ = sh.map
    R = r or sh.radius()
    px, py = center or (C / 2, C / 2)
    k = C / (2 * half * R)                       # picture px per screen px
    box = (cx - px / k, cy - py / k, cx + (C - px) / k, cy + (C - py) / k)
    pic = ground.copy() if ground is not None else flat(HUD_GROUND)
    pic.alpha_composite(cut(hud(sh), box))
    return pic, (px, py), sh.radius() * k


def core():
    pic, _, _ = radar_pic(radar_shot('radar'))
    return pic


def radar_off():
    """the core radar, dimmed and gray, struck through: Radar Off leaves it out"""
    sh = radar_shot('radar')
    cx, cy, _ = sh.map
    R = sh.radius()
    k = C / (2 * 1.1 * R)
    layer = cut(hud(sh), square(cx, cy, 1.1 * R))
    r, g, b, a = layer.split()
    lum = Image.merge('RGB', (r, g, b)).convert('L')
    dim = Image.merge('RGBA', (lum, lum, lum, a.point(lambda v: v * 40 // 100)))
    pic = flat(HUD_GROUND)
    pic.alpha_composite(dim)
    v = Vec()
    o = R * k * 0.8 / math.sqrt(2)
    v.line([(C / 2 - o, C / 2 - o), (C / 2 + o, C / 2 + o)], HOSTILE, 13)
    v.arc(C / 2, C / 2, R * k, 0, 360, HOSTILE, 6)
    pic.alpha_composite(v.done(2.5))
    caption(pic, 'OFF', 182, 38)
    return pic


def rotate():
    """Rotate With View: I face 35 degrees, the radar turns so that's up; N sits off the top"""
    sh = radar_shot('rotate', cam=[(0, 0, 0, 1.6, 35, -6)], rotate=True)
    pic, (px, py), rr = radar_pic(sh, half=1.24)
    v = Vec()
    ra = rr + 9

    def pt(a):
        return (px + ra * math.sin(math.radians(a)), py - ra * math.cos(math.radians(a)))
    v.line([pt(a) for a in range(52, -34, -2)], YELLOW, 5)
    end, before = pt(-46), pt(-34)
    v.arrow(before[0], before[1], end[0], end[1], YELLOW, 5, 15)
    pic.alpha_composite(v.done(2))
    return pic


def north():
    """North Up: I face 35 degrees, the radar stays put (N at the top, an arrow over it) and the cone turns"""
    sh = radar_shot('north', cam=[(0, 0, 0, 1.6, 35, -6)], rotate=False)
    pic, (px, py), rr = radar_pic(sh, half=1.34)
    v = Vec()
    v.arrow(px, py - rr - 4, px, 3, YELLOW, 5, 13)
    pic.alpha_composite(v.done(2))
    return pic


def range_pic(n, label=None):
    sh = radar_shot('range_%d' % n, range=n)
    pic, (px, py), rr = radar_pic(sh)
    v = Vec()
    v.arrow(px + 9, py, px + rr - 3, py, YELLOW, 5, 16)
    pic.alpha_composite(v.done(2))
    caption(pic, label or '%d M' % n, py + 24, 36)
    return pic


SIZES = ('small', 'medium', 'large')


def size_pic(name):
    """the radar at that size on one scale (the large one fills the picture)"""
    sh = radar_shot('size_' + name, size=name)
    pic, _, _ = radar_pic(sh, half=1.12, center=(C / 2, 130), r=sh.radius(1.0))
    caption(pic, name.upper(), 10, 32)
    return pic


def size_header(label='SIZE'):
    """the small radar with the medium and large rims dashed round it, on one scale"""
    sh = radar_shot('size_small', size='small')
    pic, (px, py), _ = radar_pic(sh, half=1.12, center=(C / 2, 130), r=sh.radius(1.0))
    big = C / (2 * 1.12)
    v = Vec()
    for f in (0.75, 1.0):
        for a in range(0, 360, 10):
            v.arc(px, py, big * f, a, a + 6, RIM, 2.5, 230)
    pic.alpha_composite(v.done(0))
    caption(pic, label, 10, 34)
    return pic


def opacity_box():
    """one box for every opacity picture: the radar and the ledger left of it"""
    sh = radar_shot('opacity_100', ledger=True, opacity=1.0)
    cx, cy, _ = sh.map
    R = sh.radius()
    radar = square(cx, cy, 1.03 * R)
    led = bbox(hud(sh), (sh.w / 2, sh.h / 2, cx - 1.04 * R, sh.h))
    return squared(union(radar, led) if led else radar, 0.02)


def opacity_layer(n):
    sh = radar_shot('opacity_%d' % n, ledger=True, opacity=n / 100)
    return cut(hud(sh), opacity_box())


def opacity_pic(n):
    pic = checker()
    pic.alpha_composite(opacity_layer(n))
    caption(pic, '%d%%' % n, 184, 38)
    return pic


def map_opacity_pic(n, label=None):
    """the open map's icons at n% (the map_opacity dropdown)"""
    scn = dict(OVERLAY_SCENE, options=dict(OVERLAY_SCENE['options'], map_opacity=n / 100))
    sh = shot('map_opacity_%d' % n, scn, 180)
    cx, cy, r = sh.map
    b = bbox(sh.top, square(cx, cy, 0.9 * r))
    half = max(cx - b[0], b[2] - cx, cy - b[1], b[3] - cy) + 0.05 * r
    pic = on_map(sh, square(cx, cy, half))
    caption(pic, label or '%d%%' % n, 184, 38)
    return pic


def marker_opacity_pic(n, label=None):
    """the pins over loot at n% (the marker_opacity dropdown)"""
    scn = markers_scene(50)
    scn = dict(scn, options=dict(scn['options'], marker_opacity=n / 100))
    sh = shot('marker_opacity_%d' % n, scn, 60)
    box = markers_box()
    pic = cut(ground_standin(sh, 50), box)
    pic.alpha_composite(cut(hud(sh), box))
    caption(pic, label or '%d%%' % n, 10, 36)
    return pic


def helper_pic(label, off=False):
    """the closer zooms' helper: the map's icons with it, struck out without it"""
    if off:
        return struck(overlay(), label)
    pic = overlay()
    caption(pic, label, 196, 30)
    return pic


def opacity_header():
    """100% over the top left, 0% over the bottom right"""
    pic = checker()
    full, none = opacity_layer(100), opacity_layer(0)
    mask = Image.new('L', (C, C), 0)
    ImageDraw.Draw(mask).polygon([(0, 0), (C, 0), (0, C)], fill=255)
    pic.alpha_composite(Image.composite(full, none, mask))
    v = Vec()
    v.line([(C, 0), (0, C)], CREAM, 2, 200)
    pic.alpha_composite(v.done(0))
    caption(pic, 'OPACITY', 184, 34)
    return pic


def ledger():
    """the ledger alone: the radar to its right is masked out (it has its own pictures)"""
    sh = shot('ledger', LEDGER_SCENE, 180, size=(3840, 2160))
    cx, cy, _ = sh.map
    # below the radar's W (it sits on the radar's middle line, at the ledger's top right)
    b = bbox(hud(sh), (sh.w / 2, cy + 0.05 * sh.radius(), cx - 1.04 * sh.radius(), sh.h))
    layer = hud(sh).copy()
    layer.paste((0, 0, 0, 0), (b[2] + 2, 0, sh.w, sh.h))
    pic = flat(HUD_GROUND)
    pic.alpha_composite(cut(layer, squared(b, 0.07)))
    return pic


def compass():
    sh = shot('compass', COMPASS_SCENE, 180)
    g = sh.s.G.T.mod.compass.geometry(sh.S)
    half = 0.055 * sh.w
    b = bbox(hud(sh), (g.cx - half, 0, g.cx + half, 0.25 * sh.h))
    box = square(g.cx, (b[1] + b[3]) / 2, half)
    pic = flat(HUD_GROUND)
    pic.alpha_composite(cut(compass_standin(sh), box))
    pic.alpha_composite(cut(hud(sh), box))
    return pic


def on_map(sh, box):
    """main draws, my map stand-in, top draws (what's drawn over the open map)"""
    pic = flat(BG)
    pic.alpha_composite(cut(sh.main, box))
    pic.alpha_composite(cut(map_standin(sh), box))
    pic.alpha_composite(cut(sh.top, box))
    return pic


def bezel():
    """the band inside the open map's rim: its north-east quarter"""
    sh = shot('bezel', BEZEL_SCENE, 180)
    cx, cy, r = sh.map
    return on_map(sh, (cx - 0.2 * r, cy - 1.08 * r, cx + 1.08 * r, cy + 0.2 * r))


def overlay():
    """loot and marks at their places on the open map: the middle of it"""
    sh = shot('overlay', OVERLAY_SCENE, 180)
    cx, cy, r = sh.map
    b = bbox(sh.top, square(cx, cy, 0.9 * r))
    half = max(cx - b[0], b[2] - cx, cy - b[1], b[3] - cy) + 0.05 * r
    return on_map(sh, square(cx, cy, half))


def tester():
    """the measurement build: the compass with its measured strip, captioned MEASURE"""
    pic = compass()
    caption(pic, 'MEASURE', 196, 34)
    return pic


def pings():
    """the bracket and ping keycap on the medal I aim at (the middle of the screen), my waypoint over the rare
    behind it; the ground is my stand-in"""
    sh = shot('pings', PINGS_SCENE, 110)
    b = bbox(hud(sh), square(sh.w / 2, sh.h / 2, 0.13 * sh.h))
    box = squared(b, 0.06)
    pic = cut(ground_standin(sh, None), box)
    pic.alpha_composite(cut(hud(sh), box))
    return pic


def markers_box():
    """one box for every markers picture: round the pins at 100 m, room for the caption over them"""
    sh = shot('markers_100', markers_scene(100), 60)
    b = bbox(hud(sh), (0.3 * sh.w, 0.1 * sh.h, 0.7 * sh.w, 0.7 * sh.h))
    return squared(b, 0.06, 0.07)


def markers_pic(n, label=None):
    sh = shot('markers_%d' % n, markers_scene(n), 60)
    box = markers_box()
    pic = cut(ground_standin(sh, n), box)
    pic.alpha_composite(cut(hud(sh), box))
    caption(pic, label or '%d M' % n, 10, 36)
    return pic


def game_icon(folder, name, size, rgb=None):
    """the game's icon (art/game_icons.py) at size px, in its colors or tinted rgb; a map id without one is drawn"""
    path = os.path.join(game_icons.SRC, folder, name + '.png')
    if not os.path.exists(path):
        keep = map_icons.SIZE, map_icons.U, map_icons.EDGE
        map_icons.SIZE, map_icons.U, map_icons.EDGE = size, size / 16.0, 0
        try:
            g = map_icons.Grid()
            dict(map_icons.ICONS)[name](g)
            im = g.finish()
        finally:
            map_icons.SIZE, map_icons.U, map_icons.EDGE = keep
    else:
        im = game_icons.load(folder, name + '.png')
        im = im.crop(im.getchannel('A').getbbox())
        k = size * 0.9 / max(im.size)
        im = game_icons.premultiplied_resize(im, (max(1, round(im.width * k)), max(1, round(im.height * k))))
        out = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        out.paste(im, ((size - im.width) // 2, (size - im.height) // 2))
        im = out
    return game_icons.tint(im, rgb) if rgb else im


def kind_pic(kind):
    """the loot kind's game icon at 192 px"""
    im = kind_icon(kind, 192)
    pic = flat(BG)
    pic.alpha_composite(im, ((C - im.width) // 2, (C - im.height) // 2))
    return pic


MAP_PICS = {'map_objective': ('objective', (255, 136, 36)), 'map_side': ('tower', (150, 140, 255)),
            'map_nest': ('nest', HOSTILE), 'map_structure': ('outpost', HOSTILE), 'map_poi': ('poi', CREAM)}


def map_pic(name):
    """the map kind's game icon at 192 px, tinted with the kind's color"""
    im = map_icon(name, 192)
    pic = flat(BG)
    pic.alpha_composite(im, ((C - im.width) // 2, (C - im.height) // 2))
    return pic


def kind_icon(kind, size):
    """the loot kind's game icon at size px, tinted as its texture is"""
    return game_icon('icons', kind, size, game_icons.TINT.get(kind))


def map_icon(name, size):
    """the map kind's game icon at size px, tinted with the kind's color"""
    icon, rgb = MAP_PICS[name]
    return game_icon('map', icon, size, tuple(rgb[:3]))


def grid_pic(images, label, cols=3, cell=56, gap=8, area=196):
    """icons in rows of `cols`, centered in the top `area` px, a caption under them"""
    pic = flat(BG)
    rows = (len(images) + cols - 1) // cols
    y0 = (area - (rows * cell + (rows - 1) * gap)) / 2
    for i, im in enumerate(images):
        r, c = divmod(i, cols)
        n = min(cols, len(images) - r * cols)
        x0 = (C - (n * cell + (n - 1) * gap)) / 2
        x, y = x0 + c * (cell + gap), y0 + r * (cell + gap)
        pic.alpha_composite(im, (int(round(x + (cell - im.width) / 2)), int(round(y + (cell - im.height) / 2))))
    caption(pic, label, area + 6, 30)
    return pic


def struck(pic, label='OFF'):
    """a picture grayed and struck through, with a caption (none when label is empty): the option leaves it out"""
    r, g, b, a = pic.split()
    lum = Image.merge('RGB', (r, g, b)).convert('L').point(lambda v: v * 55 // 100)
    out = Image.merge('RGBA', (lum, lum, lum, a))
    v = Vec()
    o = C * 0.3
    v.line([(C / 2 - o, C / 2 - o - 14), (C / 2 + o, C / 2 + o - 14)], HOSTILE, 11)
    out.alpha_composite(v.done(2.5))
    if label:
        caption(out, label, 198, 34)
    return out


LOOT_SETS = {'loot': (KINDS, 'LOOT'), 'loot_all': (KINDS, 'EVERYTHING'),
             'loot_valuables': (('credit', 'medal', 'requisition', 'common', 'rare', 'super'), 'VALUABLES'),
             'loot_samples': (('common', 'rare', 'super'), 'SAMPLES')}
EXTRAS = ('map_objective', 'map_side', 'map_nest', 'map_structure', 'map_poi')
EXTRA_SETS = {'extras': (EXTRAS, 'MAP'), 'extras_all': (EXTRAS, 'ALL'),
              'extras_objectives': (('map_objective', 'map_side'), 'OBJECTIVES')}


def loot_pic(name):
    kinds, label = LOOT_SETS[name]
    return grid_pic([kind_icon(k, 52) for k in kinds], label)


def extras_pic(name):
    names, label = EXTRA_SETS[name]
    return grid_pic([map_icon(m, 60) for m in names], label, cell=64)


def extras_off():
    pic = grid_pic([map_icon(m, 60) for m in EXTRAS], '', cell=64)
    return struck(pic)


def markers_off():
    sh = shot('markers_50', markers_scene(50), 60)
    box = markers_box()
    pic = cut(ground_standin(sh, 50), box)
    pic.alpha_composite(cut(hud(sh), box))
    return struck(pic)


def radar_header():
    return size_header('RADAR')


# ---------------------------------------------------------------------------------------------- 0.9.3: legend, mode
# the legend's scene: the ledger's loot (five kinds seen, the requisition picked up) and a nest
LEGEND_UNITS = LEDGER_SCENE['units'] + [('bug_hole_small', -60, 90, 0), ('bug_hole_small', -63, 93, 0)]


def legend_shot(legend, map_open):
    scn = {'options': {'kinds': ALL_KINDS, 'map_kinds': MAPS, 'legend': legend}, 'camera': RADAR_CAM,
           'units': LEGEND_UNITS, 'lua': LOCAL_LUA + SYNC_LUA}
    if map_open:
        scn['map_open'] = [(0.5, 99)]
    return shot('legend_%s_%s' % (legend, 'open' if map_open else 'closed'), scn, 180)


def radar_spot(sh):
    """the corner radar's centre (top-down y) and radius, from radar.place"""
    rx, ry, rr = sh.s.G.T.mod.radar.place(sh.S)
    return rx, sh.h - ry, rr


def legend_panel(sh, layer):
    """the legend panel's box: what is drawn left of the open map's rim (map open), or of the radar (map closed)"""
    if sh.S.map_open:
        cx, cy, r = sh.map
        edge = cx - r
    else:
        rx, ry, rr = radar_spot(sh)
        edge = rx - rr - 8 * sh.h / 1080          # half legend.lua's GAP: clear of the radar's rim
    return bbox(layer, (0.25 * sh.w, 0, edge, sh.h))


def legend_header():
    """the legend panel alone (the map closed, 'always'), the radar masked out"""
    sh = legend_shot('always', False)
    b = legend_panel(sh, hud(sh))
    layer = hud(sh).copy()
    layer.paste((0, 0, 0, 0), (b[2] + 2, 0, sh.w, sh.h))
    pic = flat(HUD_GROUND)
    pic.alpha_composite(cut(layer, squared(b, 0.14, 0.1)))
    caption(pic, 'LEGEND', 10, 34)
    return pic


def legend_map():
    """beside the open map: the panel and the map's left edge"""
    sh = legend_shot('map', True)
    cx, cy, r = sh.map
    b = legend_panel(sh, sh.top)
    box = squared(union(b, (cx - r, cy - 0.2 * r, cx - 0.55 * r, cy + 0.2 * r)), 0.14, 0.1)
    pic = on_map(sh, box)
    caption(pic, 'MAP OPEN', 10, 32)
    return pic


def legend_always():
    """the map closed: the panel left of the corner radar"""
    sh = legend_shot('always', False)
    cx, cy, R = radar_spot(sh)
    b = legend_panel(sh, hud(sh))
    box = squared(union(b, square(cx, cy, 1.03 * R)), 0.1, 0.08)
    pic = flat(HUD_GROUND)
    pic.alpha_composite(cut(hud(sh), box))
    caption(pic, 'ALWAYS', 10, 32)
    return pic


def legend_off():
    sh = legend_shot('map', True)
    cx, cy, r = sh.map
    b = legend_panel(sh, sh.top)
    box = squared(union(b, (cx - r, cy - 0.2 * r, cx - 0.55 * r, cy + 0.2 * r)), 0.14, -0.1)
    return struck(on_map(sh, box))


def markers_plain():
    sh = shot('markers_50', markers_scene(50), 60)
    box = markers_box()
    pic = cut(ground_standin(sh, 50), box)
    pic.alpha_composite(cut(hud(sh), box))
    return pic


def radar_crop():
    """the corner radar alone (radar.place's spot)"""
    sh = radar_shot('radar')
    cx, cy, R = radar_spot(sh)
    pic = flat(HUD_GROUND)
    pic.alpha_composite(cut(hud(sh), square(cx, cy, 1.1 * R)))
    return pic


TILE, TILE_GAP = 74, 6


def mode_tiles(out, label):
    """the radar, the compass and the pins, a tile each in a row (out: the ones the pick leaves out, struck)"""
    pic = flat(BG)
    parts = (('radar', radar_crop), ('compass', compass), ('pins', markers_plain))
    x0 = (C - (3 * TILE + 2 * TILE_GAP)) // 2
    for i, (name, make) in enumerate(parts):
        t = make()
        if name in out:
            t = struck(t, '')
        t = t.resize((TILE, TILE), Image.LANCZOS)
        pic.alpha_composite(t, (x0 + i * (TILE + TILE_GAP), 62))
    caption(pic, label, 160, 30)
    return pic


def mode_map_only():
    """the open map with its icons, and nothing else"""
    pic = overlay()
    caption(pic, 'MAP ONLY', 196, 32)
    return pic


BUILD = {
    'core': core, 'radar_off': radar_off, 'rotate': rotate, 'north': north,
    'radar': radar_header, 'extras_off': extras_off, 'markers_off': markers_off,
    'ledger': ledger, 'compass': compass, 'bezel': bezel, 'overlay': overlay, 'pings': pings, 'tester': tester,
    'range': lambda: range_pic(150, 'RANGE'),
    'size': size_header, 'opacity': opacity_header,
    'markers': lambda: markers_pic(50, 'MARKERS'),
    'legend': legend_header, 'legend_map': legend_map, 'legend_always': legend_always, 'legend_off': legend_off,
    'mode': lambda: mode_tiles((), 'OUTSIDE THE MAP'), 'mode_all': lambda: mode_tiles((), 'ALL'),
    'mode_no_radar': lambda: mode_tiles(('radar',), 'NO RADAR'), 'mode_map_only': mode_map_only,
}
for _n in (75, 100, 150, 200, 250, 300):
    BUILD['range_%d' % _n] = (lambda n: lambda: range_pic(n))(_n)
for _s in SIZES:
    BUILD['size_' + _s] = (lambda s: lambda: size_pic(s))(_s)
    BUILD['radar_' + _s] = (lambda s: lambda: size_pic(s))(_s)
for _n in LOOT_SETS:
    BUILD[_n] = (lambda n: lambda: loot_pic(n))(_n)
for _n in EXTRA_SETS:
    BUILD[_n] = (lambda n: lambda: extras_pic(n))(_n)
for _n in (0, 25, 50, 75, 100):
    BUILD['opacity_%d' % _n] = (lambda n: lambda: opacity_pic(n))(_n)
BUILD['map_opacity'] = lambda: map_opacity_pic(50, 'MAP ICONS')
BUILD['marker_opacity'] = lambda: marker_opacity_pic(50, 'WORLD PINS')
BUILD['helper'] = lambda: helper_pic('CLOSER ZOOMS')
BUILD['helper_auto'] = lambda: helper_pic('WITH THE GAME')
BUILD['helper_off'] = lambda: helper_pic('WHOLE MAP ONLY', True)
for _n in (25, 50, 75, 100):
    BUILD['map_opacity_%d' % _n] = (lambda n: lambda: map_opacity_pic(n))(_n)
    BUILD['marker_opacity_%d' % _n] = (lambda n: lambda: marker_opacity_pic(n))(_n)
for _n in (25, 50, 100):
    BUILD['markers_%d' % _n] = (lambda n: lambda: markers_pic(n))(_n)
for _k in KINDS:
    BUILD[_k] = (lambda k: lambda: kind_pic(k))(_k)
for _m in MAP_PICS:
    BUILD[_m] = (lambda m: lambda: map_pic(m))(_m)


# ---------------------------------------------------------------------------------------------- output
def contact_sheet(names, path, cell=128, cols=8):
    """every image at 128 px (half size: the legibility check) with its name under it"""
    from PIL import ImageFont
    font = ImageFont.load_default()
    lab = 14
    rows = (len(names) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * (cell + 8) + 8, rows * (cell + lab + 8) + 8), (48, 52, 46))
    d = ImageDraw.Draw(sheet)
    for i, name in enumerate(names):
        x, y = 8 + (i % cols) * (cell + 8), 8 + (i // cols) * (cell + lab + 8)
        im = Image.open(os.path.join(OUT, name + '.png')).convert('RGB').resize((cell, cell), Image.LANCZOS)
        sheet.paste(im, (x, y))
        d.text((x, y + cell + 2), name, fill=(220, 220, 210), font=font)
    sheet.save(path)


def main(argv):
    sheet = '--sheet' in argv
    names = [a for a in argv if not a.startswith('--')]
    bad = [n for n in names if n not in BUILD]
    if bad:
        print('unknown image(s): %s\nknown: %s' % (' '.join(bad), ' '.join(sorted(BUILD))))
        return 2
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(WORK, exist_ok=True)
    for name in names or sorted(BUILD):
        im = framed(BUILD[name]())
        assert im.size == (N, N) and im.mode == 'RGB', name
        path = os.path.join(OUT, name + '.png')
        im.save(path)
        print('wrote', os.path.relpath(path, os.path.join(DEV, '..')).replace(os.sep, '/'))
    if sheet:
        done = sorted(n[:-4] for n in os.listdir(OUT) if n.endswith('.png') and n[:-4] in BUILD)
        os.makedirs(os.path.dirname(SHEET), exist_ok=True)
        contact_sheet(done, SHEET)
        print('wrote', os.path.relpath(SHEET, os.path.join(DEV, '..')).replace(os.sep, '/'))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
