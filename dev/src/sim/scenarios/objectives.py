"""Objectives and structures (objectives.lua): nests, an outpost, side objectives, a silo, caches, extraction.

  objectives         a plain install: a near bug nest whose holes go one by one (done at 9 s), a far nest that goes
                     between two lists (done by the list), a large nest, a fabricator outpost losing one fabricator,
                     a jammer and a detector tower, an ICBM silo in two parts, two caches, an extraction (a guess:
                     no mark here). F9 at 10.5 s aimed at the cache, F9 at 12.5 s aimed at nothing; the map open
                     14-16 s (the list pauses, the marks stay), the HUD hidden 16.5-17 s, a new mission at 18 s.
                     track's list is exported as track.watch (the proposed core change): mine shares its walks.
  objectives_tester  Tester options (structures_all): guesses on, an attack ship whose wreck turns up at 4 s (swap),
                     45 factory chimneys (over the cap: dropped), a colony spawner with holes, the extraction.
"""

MAPS = {'nest': True, 'structure': True, 'objective': True, 'side_objective': True, 'poi': True, 'extract': True}

NEAR_NEST = [
    ('bug_hole_small', 20, 30, 0, 3.0), ('bug_hole_small', 26, 34, 0, 5.0), ('bug_hole_small', 32, 28, 0, 7.0),
    ('bug_hole_medium', 28, 42, 0, 9.0), ('3b3327050e8c2c23', 28.5, 42.3, 0, 9.0),     # a medium hole and its ceiling
]
FAR_NEST = [('bug_hole_small', -150, 200, 0, 11.0), ('bug_hole_small', -160, 210, 0, 11.0)]
LARGE_NEST = [(k, 300 + dx, -100 + dy, 0) for (k, dx, dy) in [
    ('bug_hole_large', 0, 0), ('bug_hole_large', 12, 5), ('bug_hole_medium', -10, 8), ('bug_hole_medium', 5, -14),
    ('bug_hole_small', -15, -6), ('bug_hole_small', 18, -10), ('bug_hole_small', -4, 18), ('bug_hole_small', 10, 16)]]
OUTPOST = [('fabricator', -60, 40, 0), ('fabricator', -75, 50, 0, 6.5)]
SIDE = [('stratagem_jammer', 120, 60, 0), ('detector_tower', -200, -80, 0)]
SILO = [('icbm_silo', 80, -150, 0), ('df657367d712cd8e', 90, -145, 0)]                  # the silo's two parts
CACHES = [('bunker_cache', 15, 55, 0), ('super_earth_cache', 400, 300, 0)]
EXTRACT = [('extraction', -300, -300, 0)]

# track's list (every 3 s) exported as track.watch (the proposed track.lua change), and every list start logged
SYNC_LUA = r"""
local mine = {}
local watch0 = chef.watch
chef.watch = function(kinds, every)
  local w = watch0(kinds, every)
  mine[#mine + 1] = w
  if every == 3 and T.mod.track and not T.mod.track.watch then T.mod.track.watch = w end
  return w
end
local scan0 = SIM.scan
SIM.scan = function()
  local was = {}
  for i, w in ipairs(mine) do was[i] = w.pending end
  scan0()
  local started = {}
  for i, w in ipairs(mine) do
    if w.pending and w.pending ~= was[i] then started[#started + 1] = 'every ' .. w.every end
  end
  if #started > 0 then chef.log('sim: unit lists started: %s', table.concat(started, ' + ')) end
end
"""
# Tester: the attack ship's wreck (its done = swap:f68a989386118dd3) turns up next to it at 4 s, the ship staying
WRECK_LUA = r"""
local scan1, injected = SIM.scan, false
SIM.scan = function()
  if not injected and SIM.t >= 4 then
    injected = true
    local e = { unit = 'wreck1', kind = 'f68a989386118dd3', x = 41, y = 42, z = 0, alive = true }
    SIM.units[#SIM.units + 1] = e
    SIM.by_unit[e.unit] = e
    chef.log('sim: the attack ship wreck appears')
  end
  scan1()
end
"""

CHIMNEYS = [('factory_chimney', -250 + 6 * (i % 9), 150 + 6 * (i // 9), 0) for i in range(45)]

SCENARIOS = {
    'objectives': {
        'about': 'nests, outpost, side objectives, silo, caches; holes destroyed one by one; F9; map open; new mission',
        'frames': 1260, 'render': [150, 600, 690, 900, 1000, 1250],
        'options': {},
        'camera': [(0, 0, 0, 1.6, 0, -6), (10, 0, 0, 1.6, 15, -6), (12, 0, 0, 1.6, 15, -6), (12.4, 0, 0, 1.6, 180, -6),
                   (13.5, 0, 0, 1.6, 180, -6), (14, 0, 0, 1.6, 360, -6)],
        'units': NEAR_NEST + FAR_NEST + LARGE_NEST + OUTPOST + SIDE + SILO + CACHES + EXTRACT,
        'press': [(10.5, 'f9'), (12.5, 'f9'), (16.5, 'f7'), (17.0, 'f7')],
        'map_open': [(14.0, 16.0)],
        'new_world': [18.0],
        'lua': SYNC_LUA,
    },
    'objectives_tester': {
        'about': 'Tester build: guesses on, a swap (attack ship wreck), 45 chimneys over the cap, extraction',
        'frames': 600, 'render': [200, 590],
        'options': {'structures_all': True, 'map_kinds': MAPS, 'kinds': {'medal': True}},
        'camera': [(0, 0, 0, 1.6, 0, -6)],
        'units': [('illuminate_attack_ship', 40, 40, 0), ('bug_colony_spawner', -40, 70, 0),
                  ('bug_hole_small', -30, 75, 0), ('bug_hole_medium', -50, 62, 0), ('medal', 5, 12, 0)]
                 + CHIMNEYS + EXTRACT + [('extraction', -20, -45, 0)] + SIDE + CACHES,
        'lua': SYNC_LUA + WRECK_LUA,
    },
}
