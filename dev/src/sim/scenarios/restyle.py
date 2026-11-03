"""The corner radar and the world markers (radar.lua, markers.lua), first restyled in 0.6; 0.8's look (the radar as a
mini map, ping-style pins) is in look.py. Fields as in base.py. Run: python -I dev/src/sim/sim.py <name>

Options list exactly what is on (with any options file only what it lists is on): world markers and every loot kind;
the compass and the overlay stay off so the frames show only these views (the legend shows with the map open only).
"""

KINDS = ('credit', 'medal', 'common', 'rare', 'super', 'requisition', 'ammo', 'grenade', 'stim')


def opts(**kw):
    o = {'markers': 50, 'kinds': {k: True for k in KINDS}}
    o.update(kw)
    return o


# loot all round me, near, mid and past the 150 m range (those are left off the radar)
LOOT = [
    ('medal', 5, 25, 0), ('medal', 5.6, 25.4, 0), ('medal', -40, -30, 0),
    ('common', -30, 60, 0), ('common', -29.5, 60.5, 0), ('common', 40, -20, 0), ('common', 62, 12, 0),
    ('rare', 80, 90, 3), ('rare', 210, -60, 0), ('super', -120, 40, 5), ('super', -110, 175, 0),
    ('requisition', 15, 12, 0.5), ('credit', -8, 18, 0.5), ('credit', 120, -170, 0),
    ('ammo', 3, 8, 0), ('ammo', 3.5, 8, 0), ('ammo', 30, -40, 0), ('stim', -4, 6, 0), ('grenade', -60, -70, 0),
]

# Stand-ins for objectives.lua's marks (its map/* art, white, tinted by the radar; its done_tex) and pings.lua.
# Done marks keep n = 0, as objectives.lua leaves them: a destroyed nest (cross) and a done side objective (check).
STANDINS_LUA = """
local function kind(id, cat, rgb, tex, label)
  return { id = id, cat = cat, rgb = rgb, icon = 'diamond', tex = tex, on = true, label = label }
end
local RGB = T.mod.config.RGB
local obj = kind('obj', 'objective', { 255, 136, 36 }, 'map/objective', 'OBJECTIVE')
local side = kind('side', 'side_objective', RGB.side or { 150, 140, 255 }, 'map/side', 'SIDE OBJECTIVE')
local nest = kind('nest', 'nest', { 255, 75, 62 }, 'map/nest', 'NEST')
local real = T.mod.objectives
T.mod.objectives = { marks = {
  { kind = obj, x = 60, y = 40, z = 0, n = 1, state = 'active' },
  { kind = side, x = -50, y = -60, z = 0, n = 0, state = 'done' },
  { kind = side, x = -90, y = 20, z = 0, n = 1, state = 'unknown' },
  { kind = nest, x = -320, y = 90, z = 0, n = 3, state = 'unknown', label = 'LARGE NEST' },
  { kind = nest, x = 95, y = -70, z = 0, n = 0, state = 'done', label = 'SMALL NEST' },
  { kind = obj, x = 35, y = -105, z = 0, n = 1, state = 'unknown' },
}, done_tex = real and real.done_tex }
T.mod.pings = {
  waypoints = { { x = 20, y = 75, z = 0, label = 'WAYPOINT' }, { x = 420, y = -260, z = 0 } },
  icon = function(cx, cy, size, alpha, layer)
    T.mod.draw.texc('ping/wp', cx, cy, size, size, chef.color(113, 245, 255, alpha), layer)
  end,
}
"""

# Cost of each of the three views: draw calls (chef.bitmap + chef.rect) and Lua time (os.clock, the sim's machine,
# so only a rough guide), logged as each view's peak grows and as averages every 100 frames.
COST_LUA = STANDINS_LUA + """
local names, n, t, peak, sum_n, sum_t = { 'radar', 'markers' }, 0, {}, {}, {}, {}
local bitmap, rect = chef.bitmap, chef.rect
chef.bitmap = function(...) n = n + 1; return bitmap(...) end
chef.rect = function(...) n = n + 1; return rect(...) end
local frames = 0
for _, name in ipairs(names) do
  local m = T.mod[name]
  local draw = m.draw
  peak[name], sum_n[name], sum_t[name] = 0, 0, 0
  m.draw = function(S)
    if name == 'radar' then
      frames = frames + 1
      if frames % 100 == 0 then
        local parts = {}
        for _, k in ipairs(names) do
          parts[#parts + 1] = string.format('%s %.1f draws %.3f ms', k, sum_n[k] / 100, sum_t[k] * 1000 / 100)
          sum_n[k], sum_t[k] = 0, 0
        end
        chef.log('cost, mean of 100 frames: %s', table.concat(parts, ', '))
      end
    end
    local n0, t0 = n, os.clock()
    draw(S)
    local dn, dt = n - n0, os.clock() - t0
    sum_n[name], sum_t[name] = sum_n[name] + dn, sum_t[name] + dt
    if dn > peak[name] then peak[name] = dn; chef.log('cost: %s peak %d draws', name, dn) end
  end
end
"""

SCENARIOS = {
    'restyle_zoom': {
        'about': 'radar zoom: numpad - twice (200, 250 m), then numpad + four times (down to 75 m: the far loot drops off)',
        'frames': 330, 'render': [20, 60, 120, 318],
        'options': opts(),
        'camera': [(0, 0, 0, 1.6, 30, -6)],
        'units': LOOT,
        'press': [(0.5, 'numpad -'), (1.5, 'numpad -'), (3.5, 'numpad +'), (4.0, 'numpad +'), (4.5, 'numpad +'),
                  (5.0, 'numpad +')],
    },
    'restyle_rotate': {
        'about': 'Rotate With View, size large: turn a full circle in 6 s (the grid, the rings and the N go round me)',
        'frames': 360, 'render': [0, 40, 95, 200, 300],
        'options': opts(rotate=True, size='large'),
        'camera': [(0, 0, 0, 1.6, 0, -6), (6, 0, 0, 1.6, 360, -6)],
        'units': LOOT,
    },
    'restyle_cleared': {
        'about': 'every medal and the requisition picked up: their radar icons and pins go',
        'frames': 240, 'render': [30, 230],
        'options': opts(),
        'camera': [(0, 0, 0, 1.6, 0, -6), (3, 0, 20, 1.6, 0, -6)],
        'units': [('medal', 5, 25, 0, 2.0), ('medal', 5.6, 25.4, 0, 2.2), ('medal', 1, 10, 0, 1.0),
                  ('requisition', 2, 14, 0.5, 1.5)] + LOOT[3:11] + LOOT[12:],
    },
    'restyle_markers': {
        'about': 'world markers close up: piles, supplies, mid and far (fading) pins; a rare picked up at 2.5 s',
        'frames': 200, 'render': [30, 190],
        'options': opts(),
        'camera': [(0, 0, 0, 1.6, 0, -7), (3, 0, 3, 1.6, 4, -7)],
        'units': [('rare', 2, 9, 0, 2.5), ('common', -3, 15, 0), ('common', -2.6, 15.3, 0), ('ammo', 1.5, 6, 0),
                  ('ammo', 1.8, 6.2, 0), ('stim', -1.5, 7, 0), ('grenade', 4, 12, 0), ('medal', 8, 30, 1),
                  ('credit', -10, 38, 0.5), ('super', 5, 46, 2), ('requisition', -14, 47, 0),
                  ('medal', 0, 70, 0), ('common', 40, -20, 0)],
    },
    'restyle_1440': {
        'about': '2560x1440: radar with objective and waypoint stand-ins, markers',
        'size': (2560, 1440),
        'frames': 120, 'render': [110],
        'options': opts(),
        'camera': [(0, 0, 0, 1.6, 20, -7)],
        'units': LOOT,
        'lua': STANDINS_LUA,
    },
    'restyle_small': {
        'about': 'size small at 1080p with the stand-ins (the smallest radar)',
        'frames': 120, 'render': [110],
        'options': opts(size='small'),
        'camera': [(0, 0, 0, 1.6, 20, -7)],
        'units': LOOT,
        'lua': STANDINS_LUA,
    },
    'restyle_cost': {
        'about': 'draw calls and Lua time of the radar and the markers (log.txt), with the stand-ins and all loot',
        'frames': 310, 'render': [300],
        'options': opts(),
        'camera': [(0, 0, 0, 1.6, 0, -7), (5, 0, 30, 1.6, 90, -7)],
        'units': LOOT,
        'lua': COST_LUA,
    },
    'restyle_counts': {
        'about': 'size small with two-digit counts: the radar piles, then the map open from 0.5 s (the legend falls '
                 'back to short labels, GREN, COMM, where needed)',
        'frames': 60, 'render': [20, 50],
        'map_open': [(0.5, 99)],
        'options': opts(size='small'),
        'camera': [(0, 0, 0, 1.6, 0, -7)],
        'units': ([('grenade', 30 + 9 * i, -40 + 7 * i, 0) for i in range(12)]
                  + [('common', -60 - 8 * i, 30 + 11 * i, 0) for i in range(14)]
                  + [('credit', 20 - 6 * i, 70 + 5 * i, 0) for i in range(10)]
                  + [('medal', -10, -20, 0), ('stim', 4, 6, 0)]),
    },
}
