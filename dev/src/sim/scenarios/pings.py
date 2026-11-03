"""Pings (pings.lua): the ping assist and waypoints set by key; the waypoints on the map's rim (bezel.lua).

  python -I dev/src/sim/sim.py pings_assist     aim at a medal (bracket + "Q PING"), a Q tap (the hint goes quiet),
                                                NUM 1 sets a waypoint on it, another on a rare 92 m out, the aim on a
                                                common sample, walk to the medal: picked up at 6.6 s (toast, the
                                                waypoint clears), NUM 3 clears the rest, NUM 1 at the sky
  python -I dev/src/sim/sim.py pings_spam       three pings in 3 s: every ping hint goes quiet for 8 s
  python -I dev/src/sim/sim.py pings_map        NUM 1 on a medal and a common sample (map closed), then the map: the
                                                quiet rim with both waypoints (their distances, and the nearest
                                                mark's); NUM 1 on the open map says to close it and aim
  python -I dev/src/sim/sim.py pings_1440       pings_assist at 2560x1440
  python -I dev/src/sim/sim.py pings_map_1440   pings_map at 2560x1440
  python -I dev/src/sim/sim.py pings_perf       cost check: pings, mapview and overlay timed (os.clock) and their
                                                allocations counted (GC stopped), over the world and the map
                                                with the overlay on and 60 loot items; logged as 'perf:'
  python -I dev/src/sim/sim.py pings_far        world markers to 50 m: a waypoint on the rare 92 m out (past them: its
                                                own pin, my glyph over the pin's top) and one on the medal 15 m out
                                                (my glyph over the markers' pin)

A plain install (options {}): everything on but the overlay.
"""
import math


def aim(tx, ty, tz, ex=0.0, ey=0.0, ez=1.6):
    """yaw, pitch (degrees) from the eye at ex, ey, ez to a point."""
    dx, dy, dz = tx - ex, ty - ey, tz - ez
    return math.degrees(math.atan2(dx, dy)), math.degrees(math.atan2(dz, math.hypot(dx, dy)))


def cam(t, x, y, target):
    yaw, pitch = aim(*target, ex=x, ey=y)
    return (t, x, y, 1.6, yaw, pitch)


MEDAL, RARE, COMMON = (0, 15, 0.3), (-20, 90, 0.3), (6, 30, 0.3)
ASSIST_UNITS = [
    ('medal', 0, 15, 0, 6.6), ('common', 6, 30, 0), ('rare', -20, 90, 0), ('ammo', 3, 8, 0), ('stim', -6, 20, 0),
    ('grenade', 25, -10, 0), ('credit', -40, 60, 0),
]

STRUCTURES = [('bunker_cache', 15, 55, 0), ('fabricator', -60, 40, 0), ('stratagem_jammer', 120, 60, 0)]
MAP_UNITS = [
    ('medal', 5, 25, 0), ('medal', 5.6, 25.4, 0), ('common', -30, 60, 0), ('common', 40, -20, 0),
    ('rare', 80, 90, 3), ('super', -120, 40, 5), ('requisition', 15, 12, 0.5), ('credit', -8, 18, 0.5),
    ('ammo', 3, 8, 0), ('stim', -4, 6, 0), ('grenade', -60, -70, 0),
] + STRUCTURES

SCENARIOS = {
    'pings_assist': {
        'about': 'ping assist and waypoints by key: aim, Q tap, NUM 1 twice, walk to the medal (picked up), NUM 3',
        'frames': 480, 'render': [50, 90, 115, 190, 260, 405, 440, 470],
        'options': {},
        'camera': [
            cam(0, 0, 0, MEDAL), cam(2.0, 0, 0, MEDAL),
            cam(2.6, 0, 0, RARE), cam(3.4, 0, 0, RARE),
            cam(4.0, 0, 0, COMMON), cam(4.6, 0, 0, COMMON),
            (6.0, 0, 12.5, 1.6, 0, -25), (7.3, 0, 12.5, 1.6, 0, -25), (7.4, 0, 12.5, 1.6, 0, 25),
        ],
        'units': ASSIST_UNITS,
        'press': [(1.2, 'q'), (1.7, 'numpad 1'), (3.0, 'numpad 1'), (7.0, 'numpad 3'), (7.5, 'numpad 1')],
    },
    'pings_spam': {
        'about': 'three pings in 3 s quiet every ping hint for 8 s (the bracket stays)',
        'frames': 330, 'render': [40, 300],
        'options': {},
        'camera': [
            cam(0, 0, 0, MEDAL), cam(1.0, 0, 0, MEDAL), cam(1.3, 0, 0, COMMON), cam(2.0, 0, 0, COMMON),
            cam(2.3, 0, 0, RARE), cam(3.0, 0, 0, RARE), cam(3.5, 0, 0, (-6, 20, 0.3)),
        ],
        'units': ASSIST_UNITS,
        'press': [(0.8, 'q'), (1.8, 'q'), (2.8, 'q')],
    },
    'pings_map': {
        'about': 'NUM 1 on two items (map closed), then the map: the quiet rim with both waypoints; NUM 1 there says how',
        'frames': 300, 'render': [70, 160, 230, 290],
        'options': {},
        'camera': [cam(0, 0, 0, (5, 25, 0.3)), cam(1.0, 0, 0, (5, 25, 0.3)),
                   cam(1.4, 0, 0, (-30, 60, 0.3)), cam(2.2, 0, 0, (-30, 60, 0.3))],
        'units': MAP_UNITS,
        'map_open': [(2.5, 99)],
        'press': [(0.8, 'numpad 1'), (2.0, 'numpad 1'), (3.4, 'numpad 1')],
    },
}
SCENARIOS['pings_1440'] = dict(SCENARIOS['pings_assist'], about='pings_assist at 2560x1440', size=(2560, 1440),
                               render=[50, 190, 405])
SCENARIOS['pings_map_1440'] = dict(SCENARIOS['pings_map'], about='pings_map at 2560x1440', size=(2560, 1440),
                                   render=[160, 230])

# pings_perf: time and allocation of my three modules. os.clock is 1 ms ticks on Windows, so only the averages over
# many frames mean anything; the draw stand-ins are Python, so the times are an upper bound.
PERF_LUA = r"""
collectgarbage('stop')
local clock, gc = os.clock, collectgarbage
-- what the sim's own stand-ins allocate (a table per color and per draw; engine temporaries in game) is left out
local excl, ndraw = 0, 0
local function ex(f, is_draw)
  return function(...)
    local k0 = gc('count')
    local a, b = f(...)
    excl = excl + (gc('count') - k0)
    if is_draw then ndraw = ndraw + 1 end
    return a, b
  end
end
for _, n in ipairs({ 'rect', 'text', 'sprite', 'bitmap', 'line' }) do chef[n] = ex(chef[n], true) end
chef.color = ex(chef.color)
local D = T.mod.draw
D.color = chef.color
for i = 1, 60 do                                   -- draw.lua's own local `color` (shared by its functions)
  local name = debug.getupvalue(D.icon, i)
  if not name then break end
  if name == 'color' then debug.setupvalue(D.icon, i, chef.color) break end
end
local names = { 'pings', 'mapview', 'overlay' }
local acc = {}
local frames, t_world, t_map = 0, 0, 0
for _, n in ipairs(names) do
  local m = T.mod[n]
  acc[n] = { t = 0, kb = 0, tm = 0, kbm = 0, d = 0, dm = 0 }
  for _, hook in ipairs({ 'update', 'draw' }) do
    local f = m and m[hook]
    if f then
      local a = acc[n]
      m[hook] = function(S)
        local c0, k0, e0, n0 = clock(), gc('count'), excl, ndraw
        local r1, r2 = f(S)
        local dt, dk, dd = clock() - c0, gc('count') - k0 - (excl - e0), ndraw - n0
        if S.map_open then a.tm, a.kbm, a.dm = a.tm + dt, a.kbm + dk, a.dm + dd
        else a.t, a.kb, a.d = a.t + dt, a.kb + dk, a.d + dd end
        if n == 'pings' and hook == 'draw' then
          frames = frames + 1
          if S.map_open then t_map = t_map + 1 else t_world = t_world + 1 end
          if frames % 240 == 0 then
            for _, nn in ipairs(names) do
              local b = acc[nn]
              local w, m = math.max(1, t_world), math.max(1, t_map)
              chef.log('perf: %-8s world %.3f ms %.0f B %.0f draws, map %.3f ms %.0f B %.0f draws per frame (%d + %d frames)',
                nn, b.t * 1000 / w, b.kb * 1024 / w, b.d / w, b.tm * 1000 / m, b.kbm * 1024 / m, b.dm / m, t_world, t_map)
            end
          end
        end
        return r1, r2
      end
    end
  end
end
"""
PERF_UNITS = list(ASSIST_UNITS) + MAP_UNITS + [
    (('common', 'ammo', 'medal', 'stim', 'grenade', 'rare')[i % 6],
     math.cos(i * 0.7) * (10 + i * 2.5), math.sin(i * 0.7) * (10 + i * 2.5), 0) for i in range(60)]
_PK = ['credit', 'medal', 'common', 'rare', 'super', 'requisition', 'ammo', 'grenade', 'stim']
SCENARIOS['pings_perf'] = {
    'about': 'cost of pings, mapview and overlay per frame (world, then the map with the overlay on); see the log',
    'frames': 480, 'render': [200, 400],
    'options': {'kinds': {k: True for k in _PK},
                'map_kinds': {'nest': True, 'structure': True, 'objective': True, 'side_objective': True,
                              'poi': True, 'extract': True},
                'overlay': True, 'pings': True, 'bezel': True, 'radar': True, 'compass': True, 'ledger': True,
                'markers': 50},   # 0.9: the map opens at 0 (no companion: only the legend there)
    'camera': [cam(0, 0, 0, MEDAL), cam(2.0, 0, 0, MEDAL), cam(3.0, 0, 0, RARE)],
    'units': PERF_UNITS,
    'map_open': [(4.0, 99)],
    'press': [(1.0, 'numpad 1'), (2.5, 'numpad 1'), (5.0, 'numpad 1')],
    'lua': PERF_LUA,
}

# pings_far: both waypoint pins in one view, the far one drawn by pings (markers.pin) and the near one by markers
SCENARIOS['pings_far'] = {
    'about': 'markers to 50 m: waypoints on the rare 92 m out (its own pin, glyph over its top) and the medal 15 m out',
    'frames': 240, 'render': [100, 230],
    'options': {'kinds': {k: True for k in _PK}, 'pings': True, 'radar': True, 'markers': 50},
    'camera': [cam(0, 0, 0, RARE), cam(1.5, 0, 0, RARE), cam(2.0, 0, 0, MEDAL), cam(3.0, 0, 0, MEDAL),
               cam(3.4, 0, 0, (-10, 50, 0.3))],
    'units': ASSIST_UNITS,
    'press': [(1.0, 'numpad 1'), (2.5, 'numpad 1')],
}
