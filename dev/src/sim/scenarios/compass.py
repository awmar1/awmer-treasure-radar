"""Compass pips (compass.lua; 0.8: the nearest valuables as icons above the strip, my waypoints first in ping cyan).

  python -I dev/src/sim/sim.py compass_turn          a full turn with loot all around (at most 4 pips, 40 px apart)
  python -I dev/src/sim/sim.py compass_behind        loot behind and beside me: nothing at the strip's ends (0.8 has
                                                     no chevrons or edge dots)
  python -I dev/src/sim/sim.py compass_far           walk toward piles past 100 m: the nearest stay, no dimming
  python -I dev/src/sim/sim.py compass_map           the map open over many piles and three waypoints (the compass stays)
  python -I dev/src/sim/sim.py compass_measured      the measured strip at 1920x1080 (HUD Scale 0.9) with the
                                                     defaults: icons above the strip, the distance to their right
  python -I dev/src/sim/sim.py compass_scaled        HUD Scale 1.0, Compass Width 2, Angle Range 0 at 2560x1440: the
                                                     strip scales and the unmeasured settings are logged once
  python -I dev/src/sim/sim.py compass_1440          a turn and the open map at 2560x1440
  python -I dev/src/sim/sim.py compass_marks         objectives and structures stay off the compass (0.8): only the
                                                     valuables and my waypoint, a nest destroyed at 9 s

Waypoints are stand-ins (the scenario's lua): T.mod.pings = { waypoints, icon }, the real pings.icon when there is one.
With any options at all only what they list is on (0.6's meaning; sim.py fills the rest in as off), so each
scenario lists the loot kinds and the views it shows; 'defaults': True runs with 0.7's (everything on).
"""
import math
import random

KINDS = ['credit', 'medal', 'common', 'rare', 'super', 'requisition', 'ammo', 'grenade', 'stim']
OPTS = {'kinds': {k: True for k in KINDS}, 'compass': True}

# all around me at (0, 0): piles (two medals, two ammo), supplies (never on the compass), far piles (100-170 m)
TURN_LOOT = [
    ('medal', 6, 24, 0), ('medal', 6.6, 24.4, 0), ('common', -25, 45, 0), ('rare', 60, 70, 2),
    ('super', -110, 60, 4), ('requisition', 30, 5, 0), ('credit', 18, -30, 0),
    ('ammo', -12, -6, 0), ('ammo', -12.4, -6.2, 0), ('grenade', -40, -40, 0), ('stim', 4, 9, 0),
    ('common', 90, -60, 1), ('medal', 140, 10, 0), ('rare', -5, 170, 0),
]

# facing north: two piles ahead, the rest behind or beside me past the compass's 90 degrees
BEHIND_LOOT = [
    ('medal', 4, 30, 0), ('ammo', -6, 12, 0),
    ('rare', 30, -40, 2), ('super', -50, -20, 3), ('medal', 10, -15, 0), ('stim', -5, -8, 0),
    ('common', 40, -2, 0), ('requisition', -35, -1, 0), ('grenade', 20, -60, 0), ('credit', -70, -45, 0),
]

# ahead of me past 100 m (dimmed) and near; walking 50 m north brings the far ones under 100 m
FAR_LOOT = [
    ('rare', -20, 125, 0), ('super', 15, 135, 0), ('medal', 40, 118, 0), ('common', -45, 110, 0),
    ('ammo', 3, 15, 0), ('stim', -8, 30, 0), ('credit', 12, 45, 0),
]


def _many():
    """36 piles spread around (8 to 170 m), a cluster of medals a few degrees apart (one pip with a count), and
    different kinds on one bearing (stepped out and in across the band)."""
    rnd = random.Random(1098)
    out = []
    for i in range(36):
        a = rnd.uniform(0, 2 * math.pi)
        d = rnd.uniform(8, 170)
        out.append((KINDS[i % 9], round(d * math.sin(a), 1), round(d * math.cos(a), 1), 0))
    for i, d in enumerate([42, 48, 55, 61]):            # medals at 38-41 degrees
        a = math.radians(38 + i)
        out.append(('medal', round(d * math.sin(a), 1), round(d * math.cos(a), 1), 0))
    for i, k in enumerate(['rare', 'common', 'super', 'stim']):     # four kinds at 200-206 degrees
        a = math.radians(200 + 2 * i)
        d = 30 + 12 * i
        out.append((k, round(d * math.sin(a), 1), round(d * math.cos(a), 1), 0))
    return out


MANY_LOOT = _many()

WAYPOINTS_LUA = r'''
local D, RGB = T.mod.draw, T.mod.config.RGB
local real = T.mod.pings
local function icon(cx, cy, size, alpha, layer)        -- stand-in glyph: a thin cream square with a dot
  local c = D.rgb(RGB.text, alpha)
  local s = size * 0.7
  local t = math.max(1, math.floor(size / 10 + 0.5))
  D.rect(cx - s / 2, cy - s / 2, s, t, c, layer)
  D.rect(cx - s / 2, cy + s / 2 - t, s, t, c, layer)
  D.rect(cx - s / 2, cy - s / 2, t, s, c, layer)
  D.rect(cx + s / 2 - t, cy - s / 2, t, s, c, layer)
  D.dot(cx, cy, t * 2, c, layer)
end
T.mod.pings = { waypoints = { %s },
  icon = (type(real) == 'table' and type(real.icon) == 'function') and real.icon or icon }
'''


def waypoints(*pts):
    return WAYPOINTS_LUA % ', '.join('{ x = %g, y = %g, z = 0, label = "WP%d" }' % (x, y, i + 1)
                                     for i, (x, y) in enumerate(pts))


# objectives.lua's marks (the objectives scenario's set): nests whose holes go one by one (the near one done at 9 s), an
# outpost, a jammer and a detector tower, a silo, two caches, an extraction
MAPS = {'nest': True, 'structure': True, 'objective': True, 'side_objective': True, 'poi': True, 'extract': True}
OPTS_MARKS = dict(OPTS, map_kinds=MAPS)
NEAR_NEST = [
    ('bug_hole_small', 20, 30, 0, 3.0), ('bug_hole_small', 26, 34, 0, 5.0), ('bug_hole_small', 32, 28, 0, 7.0),
    ('bug_hole_medium', 28, 42, 0, 9.0), ('3b3327050e8c2c23', 28.5, 42.3, 0, 9.0),
]
FAR_NEST = [('bug_hole_small', -150, 200, 0), ('bug_hole_small', -160, 210, 0)]
LARGE_NEST = [(k, 300 + dx, -100 + dy, 0) for (k, dx, dy) in [
    ('bug_hole_large', 0, 0), ('bug_hole_large', 12, 5), ('bug_hole_medium', -10, 8), ('bug_hole_medium', 5, -14),
    ('bug_hole_small', -15, -6), ('bug_hole_small', 18, -10)]]
STRUCTURES = [('fabricator', -60, 40, 0), ('fabricator', -75, 50, 0, 6.5),
              ('stratagem_jammer', 120, 60, 0), ('detector_tower', -200, -80, 0),
              ('icbm_silo', 80, -150, 0), ('df657367d712cd8e', 90, -145, 0),
              ('bunker_cache', 15, 55, 0), ('super_earth_cache', 400, 300, 0), ('extraction', -300, -300, 0)]

# from the objectives scenario: track's list exported as track.watch (the proposed core change), so the structure
# list shares its walks
SYNC_LUA = r"""
local watch0 = chef.watch
chef.watch = function(kinds, every)
  local w = watch0(kinds, every)
  if every == 3 and T.mod.track and not T.mod.track.watch then T.mod.track.watch = w end
  return w
end
"""

SCENARIOS = {
    'compass_turn': {
        'about': 'compass pips: a full turn in 6 s with loot all around and a waypoint 600 m out (at most 4 pips)',
        'frames': 360, 'render': [30, 90, 180, 270, 345],
        'options': OPTS,
        'camera': [(0, 0, 0, 1.6, 0, -6), (6, 0, 0, 1.6, 360, -6)],
        'units': TURN_LOOT,
        'lua': waypoints((40, 30), (-420, -430)),
    },
    'compass_behind': {
        'about': 'loot behind and beside me: no chevrons or dots at the strip ends, a waypoint behind me clamped',
        'frames': 120, 'render': [100],
        'options': OPTS,
        'camera': [(0, 0, 0, 1.6, 0, -6)],
        'units': BEHIND_LOOT,
        'lua': waypoints((5, -200)),
    },
    'compass_far': {
        'about': 'walk 50 m toward piles past 100 m: the nearest valuables stay on the strip, the distances count down',
        'frames': 330, 'render': [40, 320],
        'options': OPTS,
        'camera': [(0, 0, 0, 1.6, 0, -6), (5, 0, 50, 1.6, 0, -6)],
        'units': FAR_LOOT,
    },
    'compass_map': {
        'about': 'the map open over 44 piles and three waypoints: the compass keeps its pips',
        'frames': 180, 'render': [40, 170],
        'options': OPTS,
        'camera': [(0, 0, 0, 1.6, 20, -6), (3, 0, 6, 1.6, 30, -6)],
        'units': MANY_LOOT,
        'map_open': [(0.0, 99)],
        'lua': waypoints((60, 20), (-300, -500), (-10, 80)),
    },
    'compass_measured': {
        'about': 'the measured strip at 1920x1080, HUD Scale 0.9, with the defaults: a turn, icons above the strip',
        'defaults': True,
        'frames': 240, 'render': [30, 120, 230],
        'camera': [(0, 0, 0, 1.6, 0, -6), (4, 0, 0, 1.6, 180, -6)],
        'units': TURN_LOOT,
    },
    'compass_scaled': {
        'about': 'HUD Scale 1.0, Compass Width 2 (wide), Angle Range 0 at 2560x1440: the strip scales, a log line',
        'size': (2560, 1440),
        'hud': {'hud_scale': 1.0, 'hud_compass_width': 2, 'hud_compass_angle_range': 0},
        'frames': 120, 'render': [100],
        'options': OPTS,
        'camera': [(0, 0, 0, 1.6, 0, -6)],
        'units': TURN_LOOT,
    },
    'compass_1440': {
        'about': 'compass at 2560x1440: a turn, the map open from 4.5 s',
        'size': (2560, 1440),
        'frames': 360, 'render': [90, 320],
        'options': OPTS,
        'camera': [(0, 0, 0, 1.6, 0, -6), (6, 0, 0, 1.6, 360, -6)],
        'units': TURN_LOOT + MANY_LOOT[:20],
        'map_open': [(4.5, 99)],
        'lua': waypoints((40, 30), (-420, -430)),
    },
    'compass_marks': {
        'about': 'objectives and structures stay off the compass (0.8): the near nest destroyed at 9 s, the map open '
                 '11-13 s',
        'frames': 780, 'render': [120, 270, 600, 720],
        'options': OPTS_MARKS,
        'camera': [(0, 0, 0, 1.6, 30, -6), (2.5, 0, 0, 1.6, 30, -6), (3.5, 0, 0, 1.6, 150, -6), (5.5, 0, 0, 1.6, 150, -6),
                   (7.0, 0, 0, 1.6, 15, -6)],
        'units': NEAR_NEST + FAR_NEST + LARGE_NEST + STRUCTURES + TURN_LOOT,
        'map_open': [(11.0, 13.0)],
        'lua': SYNC_LUA + waypoints((-40, 90)),
    },
}
