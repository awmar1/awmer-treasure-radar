"""0.8's look with the defaults: the corner radar as a mini game map (radar.lua), the nearest valuables on the compass
(compass.lua) and the ping-style world markers (markers.lua), with real objectives and structures (their units) and
three waypoints of my own (put in pings.waypoints, as Numpad 1 would). Fields as in base.py.

  python -I dev/src/sim/sim.py look          the three views at 1080p, then the map open (the radar hides, the compass stays)
  python -I dev/src/sim/sim.py look_turn     a full turn: the grid, the rings and the N go round me
  python -I dev/src/sim/sim.py look_north    Rotate With View off: north up, my cone turns
  python -I dev/src/sim/sim.py look_wp       close up: a pile on my waypoint (cyan pin, the glyph over it), the far one
  look_small, look_large                     the radar's sizes at 1080p
  look_1440, look_2160, look_uw              2560x1440, 3840x2160 and 3440x1440 (Edge Offset 0: the HUD at the edges)
  look_hud125                                HUD Scale 1.25: the radar moves up with the game's chat

Every rendered frame is checked (checks.txt): the radar clear of the game's chat (CHAT, also dev/harness/chat_check.py)
and gone while the map is open, at most four compass pips with valuables 40 px apart (at 1080p), pins on my waypoint
in ping cyan.
"""

PING = (113, 245, 255)

# loot all round me at (0, 0), as base.py's, and a pile ahead for the close-up
LOOT = [
    ('medal', 5, 25, 0), ('medal', 5.6, 25.4, 0), ('medal', 1, 10, 0, 2.5),
    ('common', -30, 60, 0), ('common', -29.5, 60.5, 0), ('common', 40, -20, 0),
    ('rare', 80, 90, 3), ('super', -120, 40, 5), ('rare', 30, 130, 0),
    ('requisition', 15, 12, 0.5), ('credit', -8, 18, 0.5), ('credit', 120, -110, 0),
    ('ammo', 3, 8, 0), ('ammo', 3.5, 8, 0), ('stim', -4, 6, 0), ('grenade', -60, -70, 0),
]
# nests and structures (rings on the radar), an outpost and extraction past the range (held inside the rim)
MARKS = [
    ('bug_hole_small', 20, 30, 0), ('bug_hole_small', 26, 34, 0), ('bug_hole_medium', 28, 42, 0),
    ('bug_hole_small', -70, 95, 0), ('bug_hole_small', -76, 101, 0),
    ('fabricator', -60, 40, 0), ('fabricator', -75, 50, 0), ('stratagem_jammer', 120, 60, 0),
    ('detector_tower', -100, -80, 0), ('bunker_cache', 15, 55, 0), ('icbm_silo', 80, -150, 0),
    ('extraction', -300, -300, 0),
]

# my waypoints: the medal pile ahead (a loot waypoint: relinked to the pile by pings), one far ahead and one behind
# me past the range. They go in at 0.3 s, once the loot list holds the pile (pings drops a loot waypoint with no pile
# under it), and again after pings.reset (a mission starts)
WAYPOINTS_LUA = r'''
local P, K = T.mod.pings, T.mod.kinds
local function kind(id) for _, k in ipairs(K.loot) do if k.id == id then return k end end end
local WP = {
  { x = 5.3, y = 25.2, z = 0, label = 'MEDALS', kind = kind('medal') },
  { x = 110, y = 300, z = 0, label = 'WAYPOINT' },
  { x = -200, y = -350, z = 0, label = 'WAYPOINT' },
}
local function add()
  for _, w in ipairs(WP) do
    local c = {}
    for k, v in pairs(w) do c[k] = v end
    P.waypoints[#P.waypoints + 1] = c
  end
end
if type(P) == 'table' and type(P.waypoints) == 'table' then
  local reset, update, added = P.reset, P.update, false
  P.reset = function(S) added = false; if reset then return reset(S) end end
  P.update = function(S)
    if not added and S.t and S.t >= 0.3 then added = true; add() end
    if update then return update(S) end
  end
end
'''

# The game's chat (its lines and the OPEN CHAT box) in screen heights from the HUD's bottom-right corner, measured on a
# 1080p screenshot at HUD Scale 0.9 (three messages: box 84-117 px up, lines up to 240 px; x 1531-1883) with room for
# about seven two-row messages; a larger HUD Scale scales it, as radar.lua assumes.
CHAT = {'left': 0.37, 'right': 0.02, 'bottom': 0.07, 'top': 0.375}


def chat_box(sim):
    """(x0, y0, x1, y1) of the chat keep-out, screen pixels, bottom-left origin."""
    H = sim.G.T.mod.hud
    w, h = sim.w, sim.h
    right = H.sides(w, h)[1]
    k = max(1, H.scale() / 0.9)
    return (right - CHAT['left'] * k * h, CHAT['bottom'] * k * h, right - CHAT['right'] * k * h, CHAT['top'] * k * h)


def box(d):
    """A draw's screen box (x0, y0, x1, y1), bottom-left origin; None for ops with no extent."""
    if d.op in ('rect', 'bitmap'):
        return (d.x, d.y, d.x + d.w, d.y + d.h)
    if d.op == 'text':
        px = d.px or 1
        return (d.x, d.y, d.x + 6 * px * len(str(d.s)), d.y + 8 * px)
    return None


def layer_box(draws, lo, hi):
    """The bounding box of the main world's draws in layers lo..hi, and how many there are."""
    bb, n = None, 0
    for i in range(1, len(draws) + 1):
        d = draws[i]
        if d.top or not (lo <= (d.layer or 900) <= hi):
            continue
        b = box(d)
        if b is None:
            continue
        n += 1
        bb = b if bb is None else (min(bb[0], b[0]), min(bb[1], b[1]), max(bb[2], b[2]), max(bb[3], b[3]))
    return bb, n


def overlaps(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def fmt_box(b):
    return '(%d, %d)-(%d, %d)' % tuple(int(round(v)) for v in b)


def radar_checks(sim):
    draws = sim.SIM.draws
    map_open = sim.SIM.worlds >= 2
    bb, n = layer_box(draws, 900, 949)
    if map_open:
        return [(n == 0, 'map open: %d radar draws (want none)' % n)]
    if not bb:
        return [(False, 'map closed: no radar draws')]
    chat = chat_box(sim)
    return [
        (not overlaps(bb, chat), 'radar %s clear of the chat %s' % (fmt_box(bb), fmt_box(chat))),
        (bb[0] >= 0 and bb[1] >= 0 and bb[2] <= sim.w and bb[3] <= sim.h, 'radar on screen %s' % fmt_box(bb)),
    ]


def compass_checks(sim):
    draws = sim.SIM.draws
    ticks = []
    for i in range(1, len(draws) + 1):
        d = draws[i]
        if not d.top and d.op == 'rect' and d.layer in (951, 955):
            ticks.append((d.x + d.w / 2, d.layer == 955))
    S = sim.G.T.mod.main.S
    g = sim.G.T.mod.compass.geometry(S)
    s = sim.h / 1080 * g.k
    out = [(len(ticks) <= 4, 'compass: %d pips (at most 4)' % len(ticks))]
    close = [(a, b) for i, (a, wa) in enumerate(ticks) for (b, wb) in ticks[i + 1:]
             if not (wa and wb) and abs(a - b) < 40 * s - 0.5]
    out.append((not close, 'compass: valuables 40 px apart (%s)' % (
        ', '.join('%d-%d' % (a, b) for a, b in close) or 'ok')))
    out.append((all(g.cx - g.half - 1 <= x <= g.cx + g.half + 1 for x, _ in ticks), 'compass: pips on the strip'))
    return out


def pin_checks(sim):
    """Pins on my waypoints (the far one by pings, the medal pile by markers) are ping cyan, the others cream."""
    draws = sim.SIM.draws
    cyan = cream = 0
    for i in range(1, len(draws) + 1):
        d = draws[i]
        if d.op == 'bitmap' and d.tex == 'pin/disc':
            c = (d.c[1], d.c[2], d.c[3])
            if c == PING:
                cyan += 1
            else:
                cream += 1
    if sim.SIM.worlds >= 2:
        return []
    return [(cyan >= 1, 'pins: %d cyan (my waypoints), %d cream' % (cyan, cream))]


def checks(sim, frame):
    return radar_checks(sim) + compass_checks(sim)


def checks_wp(sim, frame):
    return checks(sim, frame) + pin_checks(sim)


def scenario(**kw):
    s = {
        'defaults': True,
        'frames': 150, 'render': [140],
        'camera': [(0, 0, 0, 1.6, 20, -7)],
        'units': LOOT + MARKS,
        'lua': WAYPOINTS_LUA,
        'checks': checks,
    }
    s.update(kw)
    return s


SCENARIOS = {
    'look': scenario(about='0.8 look at 1080p: radar, compass and pins with waypoints, then the map open from 3 s',
                     frames=240, render=[150, 230], map_open=[(3.0, 99)], checks=checks_wp),
    'look_turn': scenario(about='0.8 look: a full turn in 6 s (the radar turns round me, the compass pips go by)',
                          frames=330, render=[30, 105, 180, 255, 320],
                          camera=[(0, 0, 0, 1.6, 0, -7), (5.5, 0, 0, 1.6, 360, -7)]),
    'look_north': scenario(about='0.8 look with Rotate With View off: north up, my cone turns',
                           options={'rotate': False}, camera=[(0, 0, 0, 1.6, 60, -7)]),
    'look_wp': scenario(about='0.8 pins close up: my medal waypoint in cyan, the far waypoint, the loot round it',
                        camera=[(0, 2, 12, 1.6, 12, -9)], checks=checks_wp),
    'look_small': scenario(about='0.8 radar, size small, at 1080p', options={'radar': 'small'}),
    'look_large': scenario(about='0.8 radar, size large, at 1080p', options={'radar': 'large'}),
    'look_1440': scenario(about='0.8 look at 2560x1440', size=(2560, 1440)),
    'look_2160': scenario(about='0.8 look at 3840x2160', size=(3840, 2160), frames=60, render=[55]),
    'look_uw': scenario(about='0.8 look at 3440x1440 (HUD Edge Offset 0: the HUD at the screen edges)',
                        size=(3440, 1440)),
    'look_hud125': scenario(about='0.8 look at HUD Scale 1.25: the radar moves up with the chat',
                            hud={'hud_scale': 1.25}),
}
