r"""1.0: the icons that never appeared until the wheel was played with (census, rapid notches, an unsure level), the two
opacity dropdowns, the companion's start with the game. map09's key mode and world; frames at f / 60 s.

  python -I dev/src/sim/sim.py map10_census_huge     25868 units (the field's unmeasured mission): a big map, -1 placed
  python -I dev/src/sim/sim.py map10_census_grows    7000, then 14000 mid-mission: small, then big, one line each
  python -I dev/src/sim/sim.py map10_census_low      3000 (nothing at -1), then 6000: small, placed
  python -I dev/src/sim/sim.py map10_extent          census 7000, two piles 340-350 m out: big
  python -I dev/src/sim/sim.py map10_extent_one      census 7000, one pile 350 m out: stays small
  python -I dev/src/sim/sim.py map10_unsure          a notch right after Tab: -1..0, nothing for UNSURE_GRACE, then the
                                                     icons at -1's scale (level still ?); a notch makes it exact
  python -I dev/src/sim/sim.py map10_rapid           +1, then 3 notches 33 ms apart: the game takes one, known 0, not -1;
                                                     one more 0.77 s later: -1, placed; a notch 0.42 s after a step counts
  python -I dev/src/sim/sim.py map10_second_fix      mission 2 with the game at -1: starts known 0, a companion fix -1 is
                                                     adopted, placed
  python -I dev/src/sim/sim.py map10_second_notch    mission 2 with the game at -1, no companion: one notch out, placed
  python -I dev/src/sim/sim.py map10_map_opacity     map_opacity 0.5: world icons at half, the legend as it was
  python -I dev/src/sim/sim.py map10_map_opacity_full   no pick: world icons at full alpha
  python -I dev/src/sim/sim.py map10_pin_opacity     marker_opacity 0.5: loot pins and a waypoint pin at half
  python -I dev/src/sim/sim.py map10_pin_opacity_full   no pick: full alpha
  python -I dev/src/sim/sim.py map10_helper_started  the exe there: one start "" "<path>", logged
  python -I dev/src/sim/sim.py map10_helper_off      helper off: nothing looked for, nothing run
  python -I dev/src/sim/sim.py map10_helper_no_exe   no exe: logged, nothing run
  python -I dev/src/sim/sim.py map10_helper_no_exec  os.execute hidden: logged, nothing run
  python -I dev/src/sim/sim.py map10_helper_error    os.execute raises: logged, the mod carries on
"""
import importlib.util
import os
import re

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location('map09_helpers', os.path.join(_here, 'map09.py'))
m9 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m9)
m8 = m9.m8

key_scn, by_frame, level_is, nothing, placed_k, logged, vw = (m9.key_scn, m9.by_frame, m9.level_is, m9.nothing,
                                                              m9.placed_k, m9.logged, m9.vw)
UNITS, companion = m9.UNITS, m8.companion
WORLD_LAYERS, LEGEND_LAYERS = m9.WORLD_LAYERS, m9.LEGEND_LAYERS
BIG_UNITS, BIG_LOOT = m9.BIG_UNITS, m9.BIG_LOOT


def class_is(sim, want):
    c = vw(sim)['class']
    return [(c == want, 'VW.class %s (want %s)' % (c, want))]


def said(sim, pattern, want=None):
    return [logged(sim, pattern, want)]


def census_at(frame, a, b):
    """the unit count a until `frame`, b from then on (SIM.num_units read through a metatable)"""
    return ('SIM.num_units = nil; setmetatable(SIM, { __index = function(_, k) if k == "num_units" then '
            'return SIM.frame < %d and %d or %d end end })' % (frame, a, b))


CENSUS_HUGE = key_scn('1.0: census 25868, the field\'s unmeasured mission: a big map, -1 placed at 0.554 px/m',
                      220, [160], by_frame({
                          160: lambda sim: placed_k(sim, -1, 0.554, loot=BIG_LOOT) + class_is(sim, 'big') + said(
                              sim, r'map: world \d+, 25868 units: a big map \(levels -1, 0, \+1; the whole map at '
                                   r'0\.5540 px/m at 1080p, R 401\.0 m\)$', 1) + said(sim, 'not measured', 0),
                      }),
                      press=[90], units=BIG_UNITS, census=25868, wheel=[(130, -1)])

CENSUS_GROWS = key_scn('1.0: census 7000, then 14000 at frame 150: small, then big (one line each), placed at big\'s k',
                       260, [140, 200], by_frame({
                           140: lambda sim: class_is(sim, 'small') + said(sim, 'a small map', 1),
                           200: lambda sim: placed_k(sim, -1, 0.554, loot=BIG_LOOT) + class_is(sim, 'big') + said(
                               sim, r'14000 units: a big map', 1) + said(sim, 'a small map', 1),
                       }),
                       press=[90], units=BIG_UNITS, lua=census_at(150, 7000, 14000), wheel=[(115, -1)])

CENSUS_LOW = key_scn('1.0: census 3000 (nothing at -1), then 6000 at frame 150: small, placed',
                     260, [140, 200], by_frame({
                         140: lambda sim: nothing(sim) + class_is(sim, None) + [level_is(sim, -1)],
                         200: lambda sim: placed_k(sim, -1, 0.7805, loot=m8.LOOT) + class_is(sim, 'small') + said(
                             sim, r'6000 units: a small map', 1),
                     }),
                     press=[90], lua=census_at(150, 3000, 6000), wheel=[(115, -1)])

FAR_TWO = [('medal', 350, 10, 1), ('rare', -340, 60, 1)]
FAR_ONE = [('medal', 350, 10, 1)]


def _u(far):
    return UNITS + [(k, x, y, 0) for (k, x, y, _) in far]


EXTENT = key_scn('1.0: census 7000, two piles beyond 300 m: big (one line), whatever the count said',
                 260, [240], by_frame({
                     240: lambda sim: placed_k(sim, -1, 0.554, loot=m8.LOOT + FAR_TWO) + class_is(sim, 'big') + said(
                         sim, r'map: world \d+: piles beyond 300 m: a big map', 1),
                 }),
                 press=[90], units=_u(FAR_TWO), census=7000, wheel=[(130, -1)])

EXTENT_ONE = key_scn('1.0: census 7000, one pile beyond 300 m: stays small (one outlier decides nothing)',
                     260, [240], by_frame({
                         240: lambda sim: class_is(sim, 'small') + said(sim, 'piles beyond', 0),
                     }),
                     press=[90], units=_u(FAR_ONE), census=7000, wheel=[(130, -1)])


# ------------------------------------------------------------------ an unsure level draws at -1
def _drawn_at(sim, k1080):
    VW = vw(sim)
    k = k1080 * sim.h / 1080
    return [(bool(VW.trusted), 'trusted %s' % VW.trusted),
            (abs(VW.k - k) < 1e-3, 'k %.4f (want %.4f)' % (VW.k, k)),
            (abs(VW.vx) < 1e-6 and abs(VW.vy) < 1e-6, 'V %.2f, %.2f (want the origin)' % (VW.vx, VW.vy)),
            (m9.world_draws(sim) > 0, 'world-anchored draws: %d' % m9.world_draws(sim))]


UNSURE = key_scn('1.0: a notch right after Tab: -1..0; after the grace the icons at -1\'s scale, level ?; one more: -1',
                 300, [120, 170, 240], by_frame({
                     120: lambda sim: nothing(sim) + [level_is(sim, None, -1, 0)],
                     170: lambda sim: _drawn_at(sim, 0.7805) + [level_is(sim, None, -1, 0)] + m9.line_is(
                         sim, {'open': '1', 'level': '?', 'kz': '0'}),
                     240: lambda sim: placed_k(sim, -1, 0.7805, loot=m8.LOOT) + [level_is(sim, -1)],
                 }),
                 press=[90], wheel=[(92, -1), (210, -1)])

RAPID = key_scn('1.0: +1, 3 notches 33 ms apart: the game takes one (measured), so known 0; 0.77 s later -1, placed; '
                'a notch 0.42 s after a step counts (the field has real ones at 0.48 and 0.54 s)',
                360, [175, 230, 340], by_frame({
                    175: lambda sim: nothing(sim) + [level_is(sim, 0)],
                    230: lambda sim: placed_k(sim, -1, 0.7805, loot=m8.LOOT) + [level_is(sim, -1)],
                    340: lambda sim: [level_is(sim, 1)],
                }),
                press=[90], wheel=[(110, 1), (150, -1), (152, -1), (154, -1), (196, -1), (270, 1), (295, 1)])

# ------------------------------------------------------------------ mission 2 with the game at -1
# Tab 90, -1 at 130, Tab 200; mission 2 at frame 300; Tab 360. The mod starts it known 0 (the field's only measure says
# the game does too: view.lua's header); if the game did carry -1, the companion or one notch out finds it.
SECOND_COMP = companion(game_level=lambda f: -1 if f >= 130 else 0)
SECOND_FIX = key_scn('1.0: mission 2, the game at -1: known 0, the companion measures -1: adopted, placed',
                     460, [370, 440], by_frame({
                         370: lambda sim: [level_is(sim, 0)],
                         440: lambda sim: placed_k(sim, -1, 0.7805, loot=m8.LOOT) + [level_is(sim, -1)] + said(
                             sim, r'level -1 from the fix'),
                     }),
                     press=[90, 200, 360], wheel=[(130, -1)], new_world=[m8.at(300)], companion=SECOND_COMP)
SECOND_NOTCH = key_scn('1.0: mission 2, the game at -1, no companion: known 0 and nothing, one notch out: -1, placed',
                       460, [410, 450], by_frame({
                           410: lambda sim: nothing(sim) + [level_is(sim, 0)],
                           450: lambda sim: placed_k(sim, -1, 0.7805, loot=m8.LOOT) + [level_is(sim, -1)] + said(
                               sim, r'a small map', 2),
                       }),
                       press=[90, 200, 360], wheel=[(130, -1), (420, -1)], new_world=[m8.at(300)])


# ------------------------------------------------------------------ the opacity dropdowns
def max_alpha(sim, spans):
    d = sim.SIM.draws
    top = -1
    for i in range(1, len(d) + 1):
        layer = d[i].layer
        if layer is not None and any(a <= layer <= b for (a, b) in spans):
            top = max(top, d[i].c[4])
    return top


def alpha_in(sim, spans, lo, hi, what):
    a = max_alpha(sim, spans)
    return (lo <= a <= hi, '%s: top alpha %s (want %s..%s)' % (what, a, lo, hi))


def disc_alpha_in(sim, spans, lo, hi, what):     # pins only: the aim's bracket and "Q PING" share these layers
    d = sim.SIM.draws
    a = -1
    for i in range(1, len(d) + 1):
        if d[i].tex and 'pin/disc' in str(d[i].tex) and any(x <= d[i].layer <= y for (x, y) in spans):
            a = max(a, d[i].c[4])
    return (lo <= a <= hi, '%s: top alpha %s (want %s..%s)' % (what, a, lo, hi))


def map_opacity(opts, lo, hi):
    return key_scn('1.0: map_opacity %s: the world icons\' alpha, the legend untouched' % opts, 220, [160], by_frame({
        160: lambda sim: [alpha_in(sim, WORLD_LAYERS, lo, hi, 'world icons'),
                          alpha_in(sim, [LEGEND_LAYERS], 200, 255, 'legend')],
    }), press=[90], wheel=[(130, -1)], options=opts)


PIN_LOOT_LAYERS = [(860, 893)]
PIN_WP_LAYERS = [(894, 898)]
PIN_NEAR = [('medal', 36, 7, 0), ('rare', 33, 13, 0)]    # 10-17 m ahead of map08's camera


def pin_opacity(opts, lo, hi):
    scn = {
        'about': '1.0: marker_opacity %s: the alpha of loot pins and of a waypoint pin (its glyph too)' % opts,
        'frames': 200, 'render': [180],
        'defaults': True, 'options': opts,
        'camera': m8.CAMERA,
        'units': m8.UNITS + PIN_NEAR,
        'press': [(1.0, 'numpad 1')],
        'checks': lambda sim, f: [disc_alpha_in(sim, PIN_LOOT_LAYERS, lo, hi, 'loot pins'),
                                  alpha_in(sim, PIN_WP_LAYERS, lo, hi, 'waypoint pin')],
    }
    return scn


# ------------------------------------------------------------------ the companion's start
FOLDER = 'Awmer Treasure Radar 1.0.0'
EXE = '\\\\Helldivers2ModManager\\\\Mods\\\\Awmer Treasure Radar 1.0.0\\\\companion\\\\TreasureRadarCompanion.exe'


def helper_lua(exe=True, execute='return 0'):
    if execute is None:
        ex = 'os.execute = nil'
    else:
        ex = 'os.execute = function(c) SIM.helper_n = (SIM.helper_n or 0) + 1; SIM.helper_cmd = c; %s end' % execute
    return r'''
local real = io.open
io.open = function(p, m)
  if type(p) == 'string' and p:find('TreasureRadarCompanion', 1, true) then
    SIM.helper_looked = (SIM.helper_looked or 0) + 1
    SIM.helper_path = p
    return %s
  end
  return real(p, m)
end
%s
''' % ('{ close = function() end }' if exe else 'nil', ex)


def helper_scn(about, options, lua, check):
    return {
        'about': about, 'frames': 120, 'render': [110],
        'defaults': True, 'options': dict(options, mod_folder=FOLDER),
        'camera': m8.CAMERA, 'units': UNITS, 'lua': lua,
        'checks': lambda sim, f: check(sim),
    }


def _n(sim, key):
    return getattr(sim.G.SIM, key) or 0


def _started(sim):
    S = sim.G.SIM
    cmd = S.helper_cmd or ''
    want = re.compile(r'^start "" ".*' + EXE + '"$')
    return [(_n(sim, 'helper_n') == 1, 'os.execute called %d times (want 1)' % _n(sim, 'helper_n')),
            (_n(sim, 'helper_looked') == 1, 'looked %d times (want 1)' % _n(sim, 'helper_looked')),
            (bool(want.match(cmd)), 'command %r' % cmd)] + said(sim, r'companion start: started .*returned 0', 1)


SCENARIOS = {
    'map10_census_huge': CENSUS_HUGE,
    'map10_census_grows': CENSUS_GROWS,
    'map10_census_low': CENSUS_LOW,
    'map10_extent': EXTENT,
    'map10_extent_one': EXTENT_ONE,
    'map10_unsure': UNSURE,
    'map10_rapid': RAPID,
    'map10_second_fix': SECOND_FIX,
    'map10_second_notch': SECOND_NOTCH,
    'map10_map_opacity': map_opacity({'map_opacity': 0.5}, 1, 128),
    'map10_map_opacity_full': map_opacity({}, 200, 255),
    'map10_pin_opacity': pin_opacity({'marker_opacity': 0.5}, 1, 128),
    'map10_pin_opacity_full': pin_opacity({}, 200, 255),
    'map10_helper_started': helper_scn('1.0: the exe in the mod\'s folder: started once', {'helper': 'auto'},
                                       helper_lua(), _started),
    'map10_helper_off': helper_scn('1.0: helper off: nothing looked for, nothing run', {'helper': 'off'}, helper_lua(),
                                   lambda sim: [(_n(sim, 'helper_looked') == 0 and _n(sim, 'helper_n') == 0,
                                                 'looked %d, ran %d (want 0, 0)' % (_n(sim, 'helper_looked'),
                                                                                    _n(sim, 'helper_n')))]),
    'map10_helper_no_exe': helper_scn('1.0: no exe: logged, nothing run', {}, helper_lua(exe=False),
                                      lambda sim: [(_n(sim, 'helper_n') == 0, 'ran %d' % _n(sim, 'helper_n'))] + said(
                                          sim, r'companion start: not found', 1)),
    'map10_helper_no_exec': helper_scn('1.0: os.execute hidden: logged, nothing run', {}, helper_lua(execute=None),
                                       lambda sim: said(sim, r'companion start: os\.execute is not available', 1)),
    'map10_helper_error': helper_scn('1.0: os.execute raises: logged, the mod carries on', {},
                                     helper_lua(execute='error("no")'),
                                     lambda sim: said(sim, r'companion start: could not start', 1) + [
                                         (_n(sim, 'helper_n') == 1, 'tried %d times' % _n(sim, 'helper_n'))]),
}
