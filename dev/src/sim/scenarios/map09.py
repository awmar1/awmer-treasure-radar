r"""0.9 (CONTRACT.md "0.9"): three zoom levels on every map, the map's size class from the unit census, the companion
hook (dev/docs/COMPANION_INTERFACE.md). Key mode as in the game (a second world all mission long,
so the Map key decides; 'map_key': False, every Tab is the scenario's own), map08's world and model. Most start with a
look around (the camera turns with the mouse, so mapview learns its degrees per count). The sim's frames are at
f / 60 s. Without a fresh companion fix or the hold (0.9.2: the last fix's V of this open carried on by the mouse)
nothing world-anchored is drawn at 0 / +1 (the legend and the compass stay).

  python -I dev/src/sim/sim.py map09_levels          the level walk: 0 at the open, -1 (placed on the origin), -1 again
                                                     (the end), 0, +1, +1 again (the end); Tab close (one open=0
                                                     line), Tab open: +1 kept; -1 to 0; the mod line's fields
  python -I dev/src/sim/sim.py map09_skid            +1, then a frame with two down-notches: -1..0, not known (level=?
                                                     kz=0, nothing drawn); one more down: -1 for sure, placed; up: 0
  python -I dev/src/sim/sim.py map09_skid_fix        the same skid with a companion: the mod line goes on with level=?,
                                                     the companion measures -1 (the game took both notches): adopted
                                                     (logged once), placed at -1
  python -I dev/src/sim/sim.py map09_skid_fix_one    the same, the game took one notch: the companion measures 0,
                                                     adopted, placed around its V
  python -I dev/src/sim/sim.py map09_ignored_close   a Tab close the game ignores, a still pan (the shadow confirmed),
                                                     +1 (the shadow's), 520 still counts: the cold open takes the
                                                     shadow's +1; Tab close, Tab open: +1 kept; down twice: placed at -1
  python -I dev/src/sim/sim.py map09_ignored_open    a Tab open the game ignores, a notch, the camera turns with the
                                                     mouse: the take-back puts the press's +1 back
  python -I dev/src/sim/sim.py map09_second_tab      a Tab close the game ignores (the shadow confirmed at +1), a second
                                                     Tab (the game closes, the mod opens), the camera turns: the
                                                     take-back takes the shadow's +1
  python -I dev/src/sim/sim.py map09_real_open       a real open (a still move), two up-notches, the camera turns: the
                                                     take-back keeps the open's +1
  python -I dev/src/sim/sim.py map09_anim            Tab, the camera turns in the animation (and a little after), then a
                                                     pan: no take-back, the levels follow the wheel
  python -I dev/src/sim/sim.py map09_drift           a real open; the camera drifts 0.006 deg/count with the mouse: no
                                                     take-back (a slow turn, logged); 0.04 deg/count: the take-back
  python -I dev/src/sim/sim.py map09_drift_nolook    the same with no look around (FOLLOW_RATE alone)
  python -I dev/src/sim/sim.py map09_nocam           a notch and a Tab in runs of 3 frames without a camera: counted on
                                                     the next full frame (logged)
  python -I dev/src/sim/sim.py map09_big             a big map (census 14000, a medal 380 m out): -1 placed at 0.554
                                                     px/m (the medal inside the rim), three more downs stay -1; 0, +1
  python -I dev/src/sim/sim.py map09_unmeasured      census 3000: not measured (logged once): nothing world-anchored at
                                                     -1 (the companion answers level ?, no adoption), class=? kz=0 in
                                                     the mod line; at 0 a companion fix still places the icons (0 / +1
                                                     don't depend on the class)
  python -I dev/src/sim/sim.py map09_1440            2560x1440: the mod line's geometry, k x 1.333 at 0, +1 (a companion
                                                     fix on 10, 20) and -1
  python -I dev/src/sim/sim.py map09_4k              3840x2160: the same at x 2
  python -I dev/src/sim/sim.py map09_fix             a companion (V 30, 40 at the open): placed around V at 0, through a
                                                     pan (V advanced by the mouse counts after the fix), at +1 and a
                                                     second pan; 'fix fresh' logged once; cmx, cmy the running sums
                                                     of mx, my
  python -I dev/src/sim/sim.py map09_fix_poll        the same with a companion that reads every third mod line: V from
                                                     the cmx, cmy deltas, nothing lost
  python -I dev/src/sim/sim.py map09_stale           how=none (stale: the hold keeps the icons, logged), dot again
                                                     (fresh), the companion stops (stale after 45 writes, logged; the
                                                     hold again); at -1 its V is ignored
  python -I dev/src/sim/sim.py map09_fix_level       the companion measures +1 while the mod says 0 (a missed notch):
                                                     adopted (logged once), placed at +1; a down-notch: 0, no more
                                                     adoptions (a fix from before the notch doesn't count)
  python -I dev/src/sim/sim.py map09_nofile          no companion: whole-map only; one mod line per frame, seqs from 1,
                                                     one open=0 line at the close; the paths logged once, no other
                                                     'companion:' lines
  python -I dev/src/sim/sim.py map09_boot            a fix file from a past session at the start: ignored
  python -I dev/src/sim/sim.py map09_far             a fix whose V is 258 m from the player at 0: used (0.9.2: no
                                                     distance gate)
  python -I dev/src/sim/sim.py map09_hold_pan        the fix goes stale mid-pan: the icons stay at the dead-reckoned V
                                                     (the model's), at 0 and after a notch to +1 and a second pan; the
                                                     close drops the hold (logged)
  python -I dev/src/sim/sim.py map09_hold_whole      -1 and back to 0 with the last fix still in the window: the hold
                                                     dropped (logged), that fix not used (a write at -1 after it),
                                                     nothing world-anchored until a new fix
  python -I dev/src/sim/sim.py map09_hold_edge       the hold panned into the map's edge: V stops 134.9 m out (a
                                                     small map at 0), the cursor 0.183 h further; back west the cursor
                                                     returns first (0.9.3: nothing drawn after the pan, no dot fix)
  0.9.3, B (PLAN_0.9.3.md): at 0 / +1 the icons draw only while VW.settled (no mouse count or notch for 0.2 s, a dot
  fix of a later write, the level known), faded in and out over 0.1 s; the view model (VW.trusted, the clusters, the
  hold) runs on underneath, so placed() still checks the model in a pan and b_hidden / b_shown check the draws:
  python -I dev/src/sim/sim.py map09_settle          settled at the open; a pan: the fade out's tail (0.83, 0.5), then
                                                     nothing drawn (the model underneath), still nothing 0.15 s after
                                                     the pan; drawn again once still 0.2 s with a dot fix; a notch too
  python -I dev/src/sim/sim.py map09_grid            grid fixes: refused with no hold (nothing drawn), taken within 32 m
                                                     of the hold, refused 40 m off (the hold draws), dot again
  python -I dev/src/sim/sim.py map09_grid_stop       a grid fix on the view's stop (134.5 m, the stop 134.9): refused, the
                                                     hold draws; a pan west: grid fixes taken, still nothing drawn (no dot
                                                     fix since the pan) until a dot fix
  python -I dev/src/sim/sim.py map09_ease            fixes 1 m off: the drawn V stays; 5 m: it eases over 0.1 s; 40 m:
                                                     it snaps
  python -I dev/src/sim/sim.py map09_walk            opens with the player walking 2 m/s: logged; no grid fix before the
                                                     first dot fix; the walking line (player 1.7 m, V 3.0 m); a second
                                                     open with no dot fix: said at the close
  python -I dev/src/sim/sim.py map09_nofix_log       no companion: the "no companion fix this session" line once, after
                                                     1 s open at 0 (not after 0.83 s), not again at the next open
  python -I dev/src/sim/sim.py map09_legend_always   legend 'always' at 1080p: left of the corner radar while closed (the
                                                     main world's 960-962), beside the map while open, F7 hides it
  python -I dev/src/sim/sim.py map09_legend_always_uw  the same at 3440x1440, and the whole map placed there
  python -I dev/src/sim/sim.py map09_legend_no_radar  'always' with mode no_radar: no radar, the legend where it sits
                                                     beside the open map; the compass stays; the
                                                     map's icons at -1 (nests: the structures list runs with no radar)
  python -I dev/src/sim/sim.py map09_map_only        mode map_only, legend 'always': no radar, compass or pins; the legend
                                                     at the map's spot; the map's icons at -1
  python -I dev/src/sim/sim.py map09_legend_off      legend 'off': none open or closed
  python -I dev/src/sim/sim.py map09_legend_map      legend 'map' (the default): none while closed, beside the open map
  python -I dev/src/sim/sim.py map09_uw              3440x1440: the mod line's w, h; every level placed (k x 1.333), a
                                                     companion fix on 10, 20 at 0 and +1
"""
import importlib.util
import math
import os
import re

_spec = importlib.util.spec_from_file_location('map08_helpers', os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                                             'map08.py'))
m8 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m8)
at, lua_list, check_view, model, companion = m8.at, m8.lua_list, m8.check_view, m8.model, m8.companion
ME, FACING, UNITS, GAIN, KL, KW = m8.ME, m8.FACING, m8.UNITS, m8.GAIN, m8.KL, m8.KW
CX, CY, RIM = m8.CX, m8.CY, m8.RIM

# the look around before the first Tab: 240 counts east, the camera 30 degrees with them
LOOK = (30, 60, 8, 0)
LOOK_TURN = (30, 60, 30)
WORLD_LAYERS = [(2920, 2929), (2940, 2949)]   # overlay.lua's world-anchored layers (rings ... badges, the chevron)
LEGEND_LAYERS = (2930, 2939)
COMPASS_LAYERS = (951, 958)


def camera(turns, look=True):
    """keyframes: still at ME, turning `deg` over frames f0..f1 for each (f0, f1, deg); look: the look around first"""
    first = [LOOK_TURN] if look else []
    yaw = FACING - sum(d for (_, _, d) in first)
    keys = [(0, ME[0], ME[1], 1.6, yaw, -6)]
    for (f0, f1, d) in first + list(turns):
        keys += [(at(f0), ME[0], ME[1], 1.6, yaw, -6), (at(f1), ME[0], ME[1], 1.6, yaw + d, -6)]
        yaw += d
    return keys


def key_scn(about, frames, render, checks, press, turns=(), raw=(), wheel=(), mouse=(), units=None, nocam=(),
            look=True, **extra):
    """a key-mode scenario; extra: more scenario keys (census, size, companion, fix_file, lua, options)"""
    scn = {
        'about': about,
        'frames': frames, 'render': render,
        'defaults': True, 'options': {},
        'camera': camera(turns, look),
        'units': units or UNITS,
        'map_open': [(0.0, 99)], 'map_key': False,
        'press': [(at(f), 'tab') for f in press],
        'raw_mouse': [(at(f0), at(f1), dx, dy) for (f0, f1, dx, dy) in ([LOOK] if look else []) + list(raw)],
        'wheel': [(at(f), v) for (f, v) in wheel],
        'mouse': [(at(f0), at(f1), b) for (f0, f1, b) in mouse],
        'nocam': [(at(f0), at(f1)) for (f0, f1) in nocam],
        'checks': checks,
    }
    scn.update(extra)
    return scn


def gate(fn, off):
    """a companion that writes nothing in the frame spans `off` (it keeps following the game's view)"""
    def g(sim, frame, f):
        r = fn(sim, frame, f)
        return None if any(a <= frame < b for (a, b) in off) else r
    g.truth, g.fixes = fn.truth, fn.fixes
    return g


# ------------------------------------------------------------------ check helpers
def mv(sim):
    return sim.G.T.mod.mapview


def vw(sim):
    return sim.G.T.mod.view


def logs(sim):
    L = sim.G.SIM.logs
    return [L[i] for i in range(1, len(L) + 1)]


def logged(sim, pattern, want=None):
    """a log line matching `pattern` (want: how many)"""
    n = sum(1 for s in logs(sim) if re.search(pattern, s))
    ok = n > 0 if want is None else n == want
    return ok, 'log /%s/: %d lines%s' % (pattern, n, '' if want is None else ' (want %d)' % want)


def fixes(sim, want):
    V = mv(sim)
    return (V.fixes == want, 'V.fixes %s (want %d)' % (V.fixes, want))


def shadow(sim, want):
    s = vw(sim).shadow_is
    return (s == want, 'shadow %s (want %s)' % (s, want))


def map_open(sim, want):
    o = bool(sim.G.T.mod.main.S.map_open)
    return (o == want, 'S.map_open %s (want %s)' % (o, want))


def level_is(sim, want, lo=None, hi=None):
    """VW.level (None: not known) and its bounds"""
    VW = vw(sim)
    lo = want if lo is None else lo
    hi = want if hi is None else hi
    return (VW.level == want and VW.lo == lo and VW.hi == hi, 'level %s (%s..%s; want %s, %s..%s)' % (
        VW.level, VW.lo, VW.hi, want, lo, hi))


def main_is(sim, lo, hi, which='main'):
    m = getattr(vw(sim), which)
    return ((m.sl0, m.sl1) == (lo, hi), '%s level %s..%s (want %s..%s)' % (which, m.sl0, m.sl1, lo, hi))


def held(sim, want):
    v = bool(vw(sim).held)
    return (v == want, 'VW.held %s (want %s)' % (v, want))


def fresh(sim, want):
    v = bool(vw(sim).fresh)
    return (v == want, 'VW.fresh %s (want %s)' % (v, want))


def v_is(sim, x, y, why=''):
    VW = vw(sim)
    return (bool(VW.trusted) and abs(VW.vx - x) < 0.05 and abs(VW.vy - y) < 0.05,
            'V %.2f, %.2f (want %.2f, %.2f%s)' % (VW.vx, VW.vy, x, y, why))


def by_frame(table):
    """checks per rendered frame: {frame: fn(sim) -> [(ok, msg)]}; sim.frame_now is the frame"""
    def fn(sim, f):
        sim.frame_now = f
        return table[f](sim) if f in table else [(False, 'no checks for frame %d' % f)]
    return fn


def layer_draws(sim, lo, hi):
    d = sim.SIM.draws
    n = 0
    for i in range(1, len(d) + 1):
        layer = d[i].layer
        if layer is not None and lo <= layer <= hi:
            n += 1
    return n


def nothing(sim):
    """the map open and nothing world-anchored drawn; the legend and the compass are"""
    VW = vw(sim)
    world = sum(layer_draws(sim, a, b) for (a, b) in WORLD_LAYERS)
    leg, comp = layer_draws(sim, *LEGEND_LAYERS), layer_draws(sim, *COMPASS_LAYERS)
    return [(bool(VW.open) and not VW.trusted and VW.n == 0, 'open %s, trusted %s, %d clusters (want True, False, 0)' % (
                VW.open, VW.trusted, VW.n)),
            (world == 0, '%d world-anchored draws (want 0)' % world),
            (leg > 0, '%d legend draws' % leg),
            (comp > 0, '%d compass draws' % comp)]


def world_draws(sim):
    return sum(layer_draws(sim, a, b) for (a, b) in WORLD_LAYERS)


def b_hidden(sim):
    """0.9.3 (B): not settled, faded out: no world-anchored draws; the legend and the compass stay"""
    VW = vw(sim)
    return [(not VW.settled and VW.fade == 0, 'settled %s, fade %.3f (want False, 0)' % (VW.settled, VW.fade)),
            (world_draws(sim) == 0, '%d world-anchored draws (want 0: not settled)' % world_draws(sim)),
            (layer_draws(sim, *LEGEND_LAYERS) > 0, '%d legend draws' % layer_draws(sim, *LEGEND_LAYERS)),
            (layer_draws(sim, *COMPASS_LAYERS) > 0, '%d compass draws' % layer_draws(sim, *COMPASS_LAYERS))]


def b_shown(sim):
    """0.9.3 (B): settled, faded in: the world-anchored draws (when a cluster is in the view)"""
    VW = vw(sim)
    return [(bool(VW.settled) and abs(VW.fade - 1) < 1e-9, 'settled %s, fade %.3f (want True, 1)' % (
                VW.settled, VW.fade)),
            ((world_draws(sim) > 0) == (VW.n > 0), '%d world-anchored draws, %d clusters' % (world_draws(sim), VW.n))]


def fade_in(lo, hi):
    """0.9.3: the fade out's tail: not settled, the fade between lo and hi, still drawn"""
    def fn(sim):
        VW = vw(sim)
        return [(not VW.settled and lo < VW.fade < hi, 'settled %s, fade %.3f (want False, %.2f..%.2f)' % (
                    VW.settled, VW.fade, lo, hi)),
                (world_draws(sim) > 0, '%d world-anchored draws (want some: the tail)' % world_draws(sim))]
    return fn


def how_is(sim, want):
    f = vw(sim).fix
    h = f.how if f is not None else None
    return (h == want, 'the fix read: how %s (want %s)' % (h, want))


def alter(fn, edit):
    """a companion whose published fixes pass through edit(frame published, fix) (a copy)"""
    def g(sim, frame, f):
        r = fn(sim, frame, f)
        return edit(frame, dict(r)) if r is not None else None
    g.truth, g.fixes = fn.truth, fn.fixes
    return g


def bias_x(spans):
    """an edit: the fix's V x plus dx for fixes published in [f0, f1)"""
    def edit(frame, fx):
        for (f0, f1, dx) in spans:
            if f0 <= frame < f1 and 'vx' in fx:
                fx['vx'] = '%.1f' % (float(fx['vx']) + dx)
        return fx
    return edit


def rings_at(level, view):
    """overlay.lua's nest rings at 1080p: inside the circle by 6 px, not within 14 px of an objective"""
    objs = [model(x, y, level, view) for (x, y) in m8.OBJECTIVES]
    n = 0
    for (_, x, y) in m8.NESTS:
        sx, sy = model(x, y, level, view)
        if math.hypot(sx - CX, sy - CY) > RIM - 6:
            continue
        if any(math.hypot(sx - ox, sy - oy) < 14 for (ox, oy) in objs):
            continue
        n += 1
    return n


def placed(sim, level, view=(0.0, 0.0)):
    """map08's model at 1080p (a small map)"""
    return check_view(sim, level, view, rings=rings_at(level, view), mock=False)


def placed_k(sim, level, k1080, view=(0.0, 0.0), loot=None, nests=None, objectives=None):
    """any screen, any k: every cluster at its piles' mean spot about S.map (bottom-left origin), every pile inside the
    rim in a cluster, the nest rings; k1080: px per m at 1080p"""
    T = sim.G.T
    VW, S = vw(sim), T.mod.main.S
    s = sim.h / 1080
    k = k1080 * s
    mx, my, r = S.map.cx, S.map.cy, S.map.r
    out = [(bool(VW.open and VW.trusted), 'open %s, trusted %s' % (VW.open, VW.trusted)),
           (VW.level == level, 'level %s (want %d)' % (VW.level, level)),
           (abs(VW.k - k) < 1e-3, 'k %.4f px/m (want %.4f)' % (VW.k, k)),
           (abs(VW.vx - view[0]) < 0.05 and abs(VW.vy - view[1]) < 0.05, 'V %.2f, %.2f (want %.2f, %.2f)' % (
               VW.vx, VW.vy, view[0], view[1]))]

    def spot(x, y):
        return mx + (x - view[0]) * k, my + (y - view[1]) * k

    clusters = lua_list(VW.clusters, VW.n)
    for c in clusters:
        piles = lua_list(c.marks, c.piles)
        spots = [spot(m.x, m.y) for m in piles]
        ex, ey = sum(p[0] for p in spots) / len(spots), sum(p[1] for p in spots) / len(spots)
        e = math.hypot(c.sx - ex, c.sy - ey)
        out.append((e <= 2 * s, 'cluster %-7s at (%.1f, %.1f), model (%.1f, %.1f), %.2f px' % (
            c.kind.id, c.sx, sim.h - c.sy, ex, sim.h - ey, e)))
    loot = m8.LOOT if loot is None else loot
    want = sum(1 for (_, x, y, n) in loot if math.hypot(*[a - b for a, b in zip(spot(x, y), (mx, my))]) <= r - 2 * s)
    got = sum(c.piles for c in clusters)
    out.append((got == want, '%d piles in clusters (want %d inside the rim)' % (got, want)))
    objs = [spot(x, y) for (x, y) in (m8.OBJECTIVES if objectives is None else objectives)]
    rings = 0
    for (_, x, y) in (m8.NESTS if nests is None else nests):
        sx, sy = spot(x, y)
        if math.hypot(sx - mx, sy - my) > r - 6 * s:
            continue
        if any(math.hypot(sx - ox, sy - oy) < 14 * s for (ox, oy) in objs):
            continue
        rings += 1
    draws = sim.SIM.draws
    rings_n = sum(1 for i in range(1, len(draws) + 1)
                  if draws[i].op == 'bitmap' and draws[i].layer == 2920 and str(draws[i].tex).startswith('ov/nest'))
    out.append((rings_n == rings, '%d nest rings (want %d)' % (rings_n, rings)))
    return out


def line(sim):
    return sim.mod_lines[-1][1] if sim.mod_lines else {}


def line_is(sim, want):
    """the mod line written this frame holds these fields (strings)"""
    if not sim.mod_lines:
        return [(False, 'no mod line written')]
    f, fields = sim.mod_lines[-1]
    out = []
    if want.get('open') == '1':
        out.append((f == getattr(sim, 'frame_now', f), 'the last mod line is from frame %d (want %s)' % (
            f, getattr(sim, 'frame_now', f))))
    bad = ['%s=%s (want %s)' % (k, fields.get(k), v) for k, v in want.items() if fields.get(k) != v]
    out.append((not bad, 'mod line seq %s: %s' % (fields.get('seq'), '; '.join(bad) if bad else 'as wanted (%s)' % (
        ' '.join('%s=%s' % kv for kv in want.items())))))
    return out


def geometry(sim, level, cls='small'):
    """the mod line's geometry against S.map, and against 0.8's 1080p numbers scaled by h / 1080"""
    S = sim.G.T.mod.main.S
    h = sim.h
    s = h / 1080
    k = (KW[cls] if level == -1 else KL[level]) if cls else None
    want = {'open': '1', 'level': '%d' % level, 'class': cls or '?', 'w': '%d' % sim.w, 'h': '%d' % h,
            'cx': '%.1f' % S.map.cx, 'cy': '%.1f' % (h - S.map.cy), 'rim': '%.1f' % S.map.r,
            'kz': ('%.4f' % (k * s)) if k else '0', 'px': '%.1f' % ME[0], 'py': '%.1f' % ME[1]}
    out = line_is(sim, want)
    out.append((abs(S.map.cx - 1674.0 * s) < 0.6 and abs(h - S.map.cy - 819.5 * s) < 0.6 and
                abs(S.map.r - 0.2056 * h) < 0.05,
                'S.map %.1f, %.1f (top-left), rim %.1f (want %.1f, %.1f, %.1f: 0.8 x %.3f)' % (
                    S.map.cx, h - S.map.cy, S.map.r, 1674.0 * s, 819.5 * s, 0.2056 * h, s)))
    return out


def open0_lines(sim):
    return [fl for (fr, fl) in sim.mod_lines if fl.get('open') == '0']


def no_companion_logs(sim):
    """no companion: no fix / level lines. The mod's own once-per-session 'companion: mod line -> ...' line (0.9.1)
    is not one of them: it names the two paths and comes without a companion too (paths_logged_once)."""
    n = sum(1 for s in logs(sim) if ' companion: ' in s and ' companion: mod line -> ' not in s)
    return (n == 0, '%d companion: lines besides the paths line (want 0)' % n)


def paths_logged_once(sim):
    """0.9.1: the mod names its two files once per session, in %LOCALAPPDATA%\\Temp"""
    n = sum(1 for s in logs(sim) if re.search(
        r' companion: mod line -> .*\\Temp\\treasure_radar_mod\.txt, fix <- .*\\Temp\\treasure_radar_fix\.txt$', s))
    return (n == 1, 'the paths line (Temp): %d (want 1)' % n)


# ------------------------------------------------------------------ 1. the level walk
# Tab 90 (0); -1 at 160 (-1), -1 at 190 (the end: -1); +1 at 230 (0), 260 (+1), 290 (the end: +1); Tab close 330 and
# a look around (360..390); Tab open 420 (+1 kept); -1 at 470 (0)
def _lv_400(sim):
    o0 = open0_lines(sim)
    return [map_open(sim, False), (not vw(sim).open, 'VW.open %s' % vw(sim).open),
            (len(o0) == 1 and line(sim).get('open') == '0', '%d open=0 lines, the last line open=%s (want 1, 0)' % (
                len(o0), line(sim).get('open')))]


LEVELS = key_scn('0.9: the level walk -1 / 0 / +1, the wheel stopping at both ends; the level kept across a close',
                 520, [140, 180, 220, 250, 280, 320, 400, 460, 500], by_frame({
                     140: lambda sim: nothing(sim) + geometry(sim, 0) + [
                         level_is(sim, 0),
                         logged(sim, r'map: world \d+, 7000 units: a small map \(levels -1, 0, \+1; the whole map at '
                                     r'0\.7805 px/m at 1080p, R 285\.3 m\)$', 1)],
                     180: lambda sim: placed(sim, -1) + geometry(sim, -1),
                     220: lambda sim: placed(sim, -1) + [
                         level_is(sim, -1), logged(sim, r'map: notch -1 at .*: notches -2, level -1\.\.-1 \(known\)', 1)],
                     250: lambda sim: nothing(sim) + geometry(sim, 0) + [level_is(sim, 0)],
                     280: lambda sim: nothing(sim) + geometry(sim, 1) + [level_is(sim, 1)],
                     320: lambda sim: nothing(sim) + [
                         level_is(sim, 1), logged(sim, r'map: notch \+1 at .*: notches 1, level 1\.\.1 \(known\)', 1),
                         logged(sim, 'the level is not known', 0)],
                     400: _lv_400,
                     460: lambda sim: nothing(sim) + geometry(sim, 1) + [
                         level_is(sim, 1), (len(open0_lines(sim)) == 1, '%d open=0 lines (want 1)' % len(
                             open0_lines(sim)))],
                     500: lambda sim: nothing(sim) + [level_is(sim, 0), logged(sim, r'map: world \d+, ', 1)],
                 }),
                 press=[90, 330, 420], turns=[(360, 390, 30)], raw=[(360, 390, 8, 0)],
                 wheel=[(160, -1), (190, -1), (230, 1), (260, 1), (290, 1), (470, -1)])

# ------------------------------------------------------------------ 2. a frame with two notches
SKID = key_scn('0.9: a frame with two down-notches from +1: -1..0, not known (nothing drawn); one more: -1, placed',
               300, [150, 180, 230, 280], by_frame({
                   150: lambda sim: nothing(sim) + [level_is(sim, 1)],
                   180: lambda sim: nothing(sim) + [
                       level_is(sim, None, -1, 0),
                       logged(sim, r'map: the level is not known \(-1\.\.0\)$', 1)] + line_is(sim, {
                           'open': '1', 'level': '?', 'class': 'small', 'kz': '0'}),
                   230: lambda sim: placed(sim, -1) + [logged(sim, r'map: the level is known \(-1\.\.-1\)$', 1)],
                   280: lambda sim: nothing(sim) + [level_is(sim, 0)],
               }),
               press=[90], wheel=[(130, 1), (160, -2), (200, -1), (250, 1)])

# the same skid with a companion: the mod line goes on (level=? kz=0) and the companion answers the level it measures.
# Both notches taken (-1): adopted once the wheel is quiet (ADOPT_QUIET), placed on the origin at -1
SKID_COMP = companion((0.0, 0.0), start=100, game_level=lambda f: 0 if f < 130 else (1 if f < 160 else -1))
SKID_FIX = key_scn("0.9: the skid's -1..0 with a companion: its -1 adopted (logged once), placed at -1",
                   260, [150, 175, 210, 250], by_frame({
                       150: lambda sim: placed(sim, 1, truth(SKID_COMP, sim)) + [level_is(sim, 1)],
                       175: lambda sim: nothing(sim) + [level_is(sim, None, -1, 0)] + line_is(sim, {
                           'open': '1', 'level': '?', 'class': 'small', 'kz': '0'}),
                       210: lambda sim: placed(sim, -1) + [
                           level_is(sim, -1),
                           logged(sim, r'companion: level -1 from the fix \(seq \d+, a 50\.7 px grid cell\); the mod '
                                       r'had -1\.\.0$', 1)] + line_is(sim, {
                           'open': '1', 'level': '-1', 'class': 'small', 'kz': '0.7805'}),
                       250: lambda sim: placed(sim, -1) + [level_is(sim, -1), logged(sim, r'companion: level', 1)],
                   }),
                   press=[90], companion=SKID_COMP, wheel=[(130, 1), (160, -2)])

# one notch taken (0): the companion measures 0, adopted, placed around its V
SKID1_COMP = companion((12.0, -8.0), start=100, game_level=lambda f: 0 if f < 130 else (1 if f < 160 else 0))
SKID_FIX_ONE = key_scn("0.9: the skid's -1..0 with a companion that measures 0: adopted, placed around its V",
                       270, [175, 210, 260], by_frame({
                           175: lambda sim: nothing(sim) + [level_is(sim, None, -1, 0)],
                           210: lambda sim: placed(sim, 0, truth(SKID1_COMP, sim)) + [
                               level_is(sim, 0),
                               logged(sim, r'companion: level 0 from the fix \(seq \d+, a 96\.0 px grid cell\); the '
                                           r'mod had -1\.\.0$', 1)],
                           # 0.9.3: 20 frames after the pan (220..239): settled, drawn
                           260: lambda sim: placed(sim, 0, truth(SKID1_COMP, sim)) + b_shown(sim) + [
                               logged(sim, r'companion: level', 1)],
                       }),
                       press=[90], companion=SKID1_COMP, wheel=[(130, 1), (160, -2)], raw=[(220, 240, 3, 1)])

# ------------------------------------------------------------------ 3. an ignored close
# Tab open 90, Tab close 180 (the game ignores it); 220..249 the mouse 150 east, 60 up, the camera still (the shadow
# confirmed); +1 at 280 (the shadow's); 330..381 520 counts back and forth (net nothing): the cold open. Tab close 450
# (the game too), a look around, Tab open 570 (+1 kept); -1 at 620 and 640: placed at -1
IGNORED_CLOSE = key_scn('0.9: a Tab close the game ignores, a pan, +1; 520 still counts: the cold open takes the '
                        "shadow's +1", 700, [140, 340, 420, 560, 600, 680], by_frame({
                            140: lambda sim: nothing(sim) + [level_is(sim, 0)],
                            340: lambda sim: [shadow(sim, 'confirmed'), map_open(sim, False), main_is(sim, 0, 0),
                                              main_is(sim, 1, 1, 'shadow')],
                            420: lambda sim: nothing(sim) + [
                                map_open(sim, True), (bool(mv(sim).cold), 'V.cold %s (want True)' % mv(sim).cold),
                                shadow(sim, None), level_is(sim, 1),
                                logged(sim, r'map: cold open: the shadow \(confirmed\) taken: level 1$', 1)],
                            560: lambda sim: [map_open(sim, False)],
                            600: lambda sim: nothing(sim) + [map_open(sim, True), level_is(sim, 1)],
                            680: lambda sim: placed(sim, -1) + [fixes(sim, 0)],
                        }),
                        press=[90, 180, 450, 570], turns=[(500, 530, 30)],
                        raw=[(220, 250, 5, -2), (330, 356, 10, 0), (356, 382, -10, 0), (500, 530, 8, 0)],
                        wheel=[(280, 1), (620, -1), (640, -1)])

# ------------------------------------------------------------------ 4. an ignored open
# open 1 (90): 120 counts east, +1 at 200; Tab close 240, a look around. Tab open 360 the game ignores: -1 at 400 (0 in
# the mod's mind); the camera turns with the mouse at 450: the take-back, +1 again. Tab open 560 (the game too): +1;
# -1 at 610 and 630: placed at -1
IGNORED_OPEN = key_scn("0.9: a Tab open the game ignores, a notch; the camera turns: the press's level back",
                       680, [330, 440, 520, 600, 660], by_frame({
                           330: lambda sim: [map_open(sim, False), shadow(sim, None), level_is(sim, 1)],
                           440: lambda sim: nothing(sim) + [map_open(sim, True), level_is(sim, 0)],
                           520: lambda sim: [
                               fixes(sim, 1), map_open(sim, False), main_is(sim, 1, 1),
                               logged(sim, r"map: open taken back \(press open, not real\): kept the press's: level 1 "
                                           r"\(the open's 0, the press's 1\)$", 1)],
                           600: lambda sim: nothing(sim) + [map_open(sim, True), level_is(sim, 1)],
                           660: lambda sim: placed(sim, -1) + [fixes(sim, 1)],
                       }),
                       press=[90, 240, 360, 560], turns=[(280, 310, 30), (450, 480, 30)],
                       raw=[(130, 160, 4, 0), (280, 310, 8, 0), (450, 480, 8, 0)],
                       wheel=[(200, 1), (400, -1), (610, -1), (630, -1)])

# ------------------------------------------------------------------ 5. an ignored close, then a second Tab
# as IGNORED_CLOSE up to +1 (the shadow confirmed at +1, the mod's own level 0); Tab 360: the game closes, the mod
# opens; the camera turns with the mouse at 450: the take-back takes the shadow's. Tab open 560 (the game too): +1
SECOND_TAB = key_scn("0.9: a Tab close the game ignores (the shadow confirmed), a second Tab, the camera turns: the "
                     "shadow's level", 680, [140, 340, 520, 600, 660], by_frame({
                         140: lambda sim: nothing(sim) + [level_is(sim, 0)],
                         340: lambda sim: [shadow(sim, 'confirmed'), map_open(sim, False), main_is(sim, 0, 0),
                                           main_is(sim, 1, 1, 'shadow')],
                         520: lambda sim: [
                             fixes(sim, 1), map_open(sim, False), main_is(sim, 1, 1),
                             logged(sim, r"map: open taken back \(press open, not real\): kept the shadow's "
                                         r"\(confirmed\): level 1 \(the open's 0, the press's 0\)$", 1)],
                         600: lambda sim: nothing(sim) + [map_open(sim, True), level_is(sim, 1)],
                         660: lambda sim: placed(sim, -1) + [fixes(sim, 1)],
                     }),
                     press=[90, 180, 360, 560], turns=[(450, 480, 30)],
                     raw=[(220, 250, 5, -2), (450, 480, 8, 0)],
                     wheel=[(280, 1), (610, -1), (630, -1)])

# ------------------------------------------------------------------ 6. a real open taken back
# Tab 90; 130..149 200 counts east, the camera still (a still move: the open is real); +1 at 180 and 195 (+1, the
# end); 240..269 the camera turns with the mouse: closed, the open's +1 kept; Tab 330: +1
REAL_OPEN = key_scn("0.9: a real open (a still move), two up-notches, then a follow: the open's +1 kept",
                    400, [300, 380], by_frame({
                        300: lambda sim: [
                            fixes(sim, 1), map_open(sim, False), main_is(sim, 1, 1),
                            (mv(sim).stills_press == 1, 'V.stills_press %s (want 1)' % mv(sim).stills_press),
                            logged(sim, r"map: open taken back \(press open, real: a still move since the press\): "
                                        r"kept the open's: level 1 \(the open's 1, the press's 0\)$", 1)],
                        380: lambda sim: nothing(sim) + [map_open(sim, True), level_is(sim, 1)],
                    }),
                    press=[90, 330], turns=[(240, 270, 30)], wheel=[(180, 1), (195, 1)],
                    raw=[(130, 150, 10, 0), (240, 270, 8, 0)])

# ------------------------------------------------------------------ 7. the animation
# Tab at 90; the mouse 4 counts a frame east 90..159; the camera turns 8 degrees in the animation (90..115) and 1
# degree after it (120..140: far under the learned rate); +1 at 210
_anim = {}


def _anim_85(sim):
    _anim['follows'] = mv(sim).follows
    return [(mv(sim).follows >= 1, 'the look around: V.follows %s' % mv(sim).follows), map_open(sim, False)]


ANIM = key_scn('0.9: Tab, the camera turns in the animation and a little after, then a pan: no take-back',
               260, [85, 200, 245], by_frame({
                   85: _anim_85,
                   200: lambda sim: nothing(sim) + [
                       level_is(sim, 0), fixes(sim, 0), shadow(sim, None),
                       (mv(sim).follows == _anim['follows'], 'V.follows %s (want %s: the animation says nothing)' % (
                           mv(sim).follows, _anim['follows']))],
                   245: lambda sim: nothing(sim) + [level_is(sim, 1), fixes(sim, 0), logged(sim, 'open taken back', 0)],
               }),
               press=[90], turns=[(90, 115, 8), (120, 140, 1)], raw=[(90, 160, 4, 0)], wheel=[(210, 1)])


# ------------------------------------------------------------------ 8. camera drift
# Tab 90 (real); the camera drifts with the mouse: 160..169 100 counts, 0.6 deg; 220..239 200 counts, 1.2 deg (0.006
# deg/count: a slow turn, logged); 300..309 100 counts, 4 deg (0.04 deg/count): a follow, the take-back
def drift_scn(about, look):
    need = '0.0250' if look else '0.0150'      # RATIO_PART * the look's 0.125, else FOLLOW_RATE
    return key_scn(about, 360, [200, 280, 350], by_frame({
        200: lambda sim: nothing(sim) + [fixes(sim, 0), map_open(sim, True), level_is(sim, 0)],
        280: lambda sim: [fixes(sim, 0), map_open(sim, True), logged(sim, 'open taken back', 0),
                          logged(sim, r'map: a slow turn, not a follow: [\d.]+ deg in \d+ counts \(0\.00[56]\d '
                                      r'deg/count, a follow needs %s\)' % need.replace('.', r'\.'))],
        350: lambda sim: [fixes(sim, 1), map_open(sim, False), main_is(sim, 0, 0),
                          logged(sim, r'map: closed \(the camera turns with the mouse: .* \(0\.0[34]\d\d deg/count, a '
                                      r'follow needs %s\)' % need.replace('.', r'\.'), 1),
                          logged(sim, 'open taken back', 1)],
    }), press=[90], look=look,
        turns=[(160, 170, 0.6), (220, 240, 1.2), (300, 310, 4.0)],
        raw=[(160, 170, 10, 0), (220, 240, 10, 0), (300, 310, 10, 0)])


DRIFT = drift_scn('0.9: the camera drifts 0.006 deg/count with the mouse: no take-back; 0.04: a take-back', True)
DRIFT_NOLOOK = drift_scn('0.9: as map09_drift with no look around (no ratio learned: FOLLOW_RATE alone)', False)


# ------------------------------------------------------------------ 9. frames without a camera
# Tab 90; frames 150..152 without a camera: a notch +1 (151); frames 240..242: a Tab (241)
def _nocam_280(sim):
    V = mv(sim)
    return [map_open(sim, False), (not vw(sim).open, 'VW.open %s' % vw(sim).open),
            (V.t_press is not None and abs(V.t_press - 243 / 60) < 1e-6, 'V.t_press %s (want %.3f: the next full frame)' % (
                V.t_press, 243 / 60)),
            (V.opens == 1, 'V.opens %s (want 1)' % V.opens),
            logged(sim, r'map: 3 frames without a camera \(0\.05 s; the map was open\)', 2)]


NOCAM = key_scn('0.9: a notch and a Tab in frames without a camera: counted on the next full frame',
                300, [200, 280], by_frame({
                    200: lambda sim: nothing(sim) + [
                        level_is(sim, 1),
                        (mv(sim).notches_mission == 1, 'V.notches_mission %s (want 1)' % mv(sim).notches_mission),
                        logged(sim, r'map: 3 frames without a camera \(0\.05 s; the map was open\)', 1)],
                    280: _nocam_280,
                }),
                press=[90, 241], wheel=[(151, 1)], nocam=[(150, 153), (240, 243)])

# ------------------------------------------------------------------ 10. the map's size class
# a big map: census 14000, a medal 380 m east (210.6 px from the centre at 0.554: inside the rim). Tab 90 (0); -1 at
# 130; three more at 170, 185, 200 (the end: -1); +1 at 240 (0), 255 (+1)
BIG_LOOT = m8.LOOT + [('medal', 380, 10, 1)]
BIG_UNITS = UNITS + [('medal', 380, 10, 0)]


def _medal(sim, k1080):
    VW, S = vw(sim), sim.G.T.mod.main.S
    k = k1080 * sim.h / 1080
    ex, ey = S.map.cx + 380 * k, S.map.cy + 10 * k
    hit = [c for c in lua_list(VW.clusters, VW.n) if c.kind.id == 'medal' and abs(c.sx - ex) < 2 and abs(c.sy - ey) < 2]
    return (len(hit) == 1, 'the medal 380 m out: %d clusters at (%.1f, %.1f)' % (len(hit), ex, sim.h - ey))


BIG = key_scn('0.9: a big map (census 14000): -1 placed at 0.554 px/m, the bottom stays -1; 0 and +1',
              300, [120, 160, 230, 250, 280], by_frame({
                  120: lambda sim: nothing(sim) + geometry(sim, 0, 'big') + [
                      level_is(sim, 0), (vw(sim)['class'] == 'big', 'VW.class %s' % vw(sim)['class']),
                      logged(sim, r'map: world \d+, 14000 units: a big map \(levels -1, 0, \+1; the whole map at '
                                  r'0\.5540 px/m at 1080p, R 401\.0 m\)$', 1)],
                  160: lambda sim: placed_k(sim, -1, 0.554, loot=BIG_LOOT) + geometry(sim, -1, 'big') + [
                      _medal(sim, 0.554)],
                  230: lambda sim: placed_k(sim, -1, 0.554, loot=BIG_LOOT) + [level_is(sim, -1), _medal(sim, 0.554)],
                  250: lambda sim: nothing(sim) + [level_is(sim, 0)],
                  280: lambda sim: nothing(sim) + geometry(sim, 1, 'big') + [level_is(sim, 1)],
              }),
              press=[90], units=BIG_UNITS, census=14000,
              wheel=[(130, -1), (170, -1), (185, -1), (200, -1), (240, 1), (260, 1)])

# census 3000: not measured (a real mission is never this low; above the big map's top counts as big since 1.0).
# Tab 90; -1 at 130; +1 at 170. A companion (V 0, 0): at -1 the cell of an unmeasured map isn't one it knows (level ?,
# no adoption); at 0 it fixes V (the scale at 0 / +1 doesn't depend on the class). Said once the count stays put, 5 s
UNM_COMP = companion()


def _no_fix_file(sim):
    p = os.path.join(sim.temp, 'treasure_radar_fix.txt')
    return (not os.path.exists(p), 'the fix file %s (want none)' % ('exists' if os.path.exists(p) else 'is not there'))


UNMEASURED = key_scn('1.0: census 3000: the map size not measured (logged once): nothing world-anchored at -1; a fix at 0 places',
                     400, [160, 200, 390], by_frame({
                         160: lambda sim: nothing(sim) + [
                             level_is(sim, -1), (vw(sim).census == 3000, 'VW.census %s' % vw(sim).census)] +
                         line_is(sim, {'open': '1', 'level': '-1', 'class': '?', 'kz': '0'}),
                         200: lambda sim: placed(sim, 0, truth(UNM_COMP, sim)) + [
                             level_is(sim, 0), logged(sim, r'companion: level', 0),
                             (any(fx.get('level') == '?' for (fr, fx) in UNM_COMP.fixes if fr < 170),
                              'fixes at -1 with level ? (the companion doesn\'t know the cell)'),
                             (any(fx.get('level') == '0' for (fr, fx) in UNM_COMP.fixes if fr >= 170),
                              'fixes at 0 with level 0')] +
                         line_is(sim, {'open': '1', 'level': '0', 'class': '?', 'kz': '0'}),
                         390: lambda sim: [logged(sim, r'map: world \d+, 3000 units: the map size is not measured '
                                                       r'\(below 4000\): no world icons at the whole-map level$', 1)],
                     }),
                     press=[90], census=3000, companion=UNM_COMP, wheel=[(130, -1), (170, 1)])


# ------------------------------------------------------------------ 11. other screens
# Tab 90 (0), a companion fix on 10, 20; +1 at 150; -1 at 200 and 222 (-1; further apart than view.lua's BUSY)
def res_scn(about, w, h, geo=True):
    """geo: the mod line's geometry against 0.8's 1080p numbers (16:9 only; else the line's w, h and S.map)"""
    def g(level):
        if geo:
            return lambda sim: geometry(sim, level)
        return lambda sim: line_is(sim, {'open': '1', 'level': '%d' % level, 'w': '%d' % w, 'h': '%d' % h,
                                         'cx': '%.1f' % sim.G.T.mod.main.S.map.cx,
                                         'rim': '%.1f' % sim.G.T.mod.main.S.map.r})
    return key_scn(about, 260, [140, 190, 250], by_frame({
        140: lambda sim: placed_k(sim, 0, KL[0], (10.0, 20.0)) + g(0)(sim) + b_shown(sim),
        190: lambda sim: placed_k(sim, 1, KL[1], (10.0, 20.0)) + g(1)(sim) + b_shown(sim),
        250: lambda sim: placed_k(sim, -1, KW['small']) + g(-1)(sim) + b_shown(sim),
    }), press=[90], size=(w, h), companion=companion((10.0, 20.0)), wheel=[(150, 1), (200, -1), (222, -1)])


RES_1440 = res_scn('0.9: 2560x1440: the mod line geometry, every level placed at k x 1.333', 2560, 1440)
RES_4K = res_scn('0.9: 3840x2160: the mod line geometry, every level placed at k x 2', 3840, 2160)
RES_UW = res_scn("0.9.3: 3440x1440: the mod line's w, h, every level placed at k x 1.333", 3440, 1440, geo=False)

# ------------------------------------------------------------------ 12. the companion's fix
# V 30, 40 at the open; captures every 2 frames from 100 (published 2 frames later). Tab 90; 130..159 4 east, 2 down a
# frame (120, 60 counts at 0: 29.5 m east, 14.8 m south); +1 at 200; 230..249 6 west a frame (120 counts at +1: 14.8 m)
FIX_COMP = companion((30.0, 40.0), start=100)


def truth(comp, sim):
    return comp.truth[sim.frame_now][0]


def _fix_190(sim):
    mx = sum(int(fl['mx']) for (fr, fl) in sim.mod_lines if 130 <= fr < 160)
    my = sum(int(fl['my']) for (fr, fl) in sim.mod_lines if 130 <= fr < 160)
    return placed(sim, 0, truth(FIX_COMP, sim)) + [
        (mx == 120 and my == 60, 'the mod lines of frames 130..159: mx %d, my %d (want 120, 60)' % (mx, my)),
        (abs(truth(FIX_COMP, sim)[0] - (30 + 120 * GAIN[0])) < 1e-6 and
         abs(truth(FIX_COMP, sim)[1] - (40 - 60 * GAIN[0])) < 1e-6, 'the game V %.2f, %.2f' % truth(FIX_COMP, sim))]


def _cum(sim):
    """every mod line's cmx, cmy: the running sums of its mx, my over the session's lines"""
    out, cx, cy, bad = [], 0, 0, None
    for (fr, fl) in sim.mod_lines:
        cx, cy = cx + int(fl['mx']), cy + int(fl['my'])
        if bad is None and (fl.get('cmx') != '%d' % cx or fl.get('cmy') != '%d' % cy):
            bad = 'frame %d: cmx %s cmy %s (want %d, %d)' % (fr, fl.get('cmx'), fl.get('cmy'), cx, cy)
    moved = any(fl['mx'] != '0' for (fr, fl) in sim.mod_lines)
    out.append((bad is None and moved and len(sim.mod_lines) > 0,
                'cmx, cmy the sums of mx, my over %d lines%s' % (len(sim.mod_lines), ': ' + bad if bad else '')))
    return out


FIX = key_scn('0.9: a companion fix at 0: the icons around V, through a pan, at +1 and a second pan',
              290, [95, 125, 150, 190, 215, 240, 270], by_frame({
                  95: lambda sim: nothing(sim) + [level_is(sim, 0), (not vw(sim).fresh, 'VW.fresh %s' % vw(sim).fresh)],
                  125: lambda sim: placed(sim, 0, truth(FIX_COMP, sim)) + b_shown(sim) + [
                      (vw(sim).fresh, 'VW.fresh %s' % vw(sim).fresh)],
                  150: lambda sim: placed(sim, 0, truth(FIX_COMP, sim)) + b_hidden(sim),
                  190: lambda sim: _fix_190(sim) + b_shown(sim),
                  215: lambda sim: placed(sim, 1, truth(FIX_COMP, sim)),
                  240: lambda sim: placed(sim, 1, truth(FIX_COMP, sim)) + b_hidden(sim),
                  270: lambda sim: placed(sim, 1, truth(FIX_COMP, sim)) + b_shown(sim) + [
                      logged(sim, 'on the move', 0), logged(sim, 'no companion fix this session', 0),
                      logged(sim, r'companion: fix fresh \(seq \d+, the mod at \d+; dot, V 30\.0, 40\.0, err 0\.5 m, '
                                  r'level 0, cell 96\.0 px\)$', 1),
                      logged(sim, 'companion: fix stale', 0), logged(sim, 'not used', 0),
                      logged(sim, r'companion: first fix read \(seq \d+\)$', 1), paths_logged_once(sim),
                      logged(sim, r'companion: level', 0)] + _cum(sim),
              }),
              press=[90], companion=FIX_COMP, raw=[(130, 160, 4, 2), (230, 250, -6, 0)], wheel=[(200, 1)])

# the same with a companion that reads only every third mod line (it misses two of three): V from the cmx, cmy deltas
POLL_COMP = companion((30.0, 40.0), start=102, poll=3)
FIX_POLL = key_scn('0.9: a companion that reads every third mod line: V from the cmx, cmy deltas, nothing lost',
                   290, [126, 150, 189, 216, 240, 270], by_frame({
                       126: lambda sim: placed(sim, 0, truth(POLL_COMP, sim)),
                       150: lambda sim: placed(sim, 0, truth(POLL_COMP, sim)) + b_hidden(sim),
                       189: lambda sim: placed(sim, 0, truth(POLL_COMP, sim)) + b_shown(sim) + [
                           (abs(truth(POLL_COMP, sim)[0] - (30 + 120 * GAIN[0])) < 1e-6 and
                            abs(truth(POLL_COMP, sim)[1] - (40 - 60 * GAIN[0])) < 1e-6,
                            'the companion\'s V %.2f, %.2f (want 59.52, 25.24: no counts lost)' % truth(POLL_COMP, sim))],
                       216: lambda sim: placed(sim, 1, truth(POLL_COMP, sim)),
                       240: lambda sim: placed(sim, 1, truth(POLL_COMP, sim)) + b_hidden(sim),
                       270: lambda sim: placed(sim, 1, truth(POLL_COMP, sim)) + b_shown(sim) + [
                           (abs(truth(POLL_COMP, sim)[0] - (30 + 120 * GAIN[0] - 120 * GAIN[1])) < 1e-6,
                            'the companion\'s V x %.2f' % truth(POLL_COMP, sim)[0]),
                           logged(sim, 'companion: fix stale', 0), logged(sim, r'companion: level', 0)] + _cum(sim),
                   }),
                   press=[90], companion=POLL_COMP, raw=[(130, 160, 4, 2), (230, 250, -6, 0)], wheel=[(200, 1)])

# a stale fix: how=none 150..189 (stale: the hold keeps V, 0.9.2), dot again (fresh), no writes 230..319 (stale 45
# writes after the last, ~271: the hold again), writes again; -1 at 340: the companion's whole-map V (50, 50) is
# ignored (placed on the origin), the hold kept at -1 (it drops when the level leaves -1: map09_hold_whole)
STALE_COMP = gate(companion((0.0, 0.0), start=100, how=lambda f: 'none' if 150 <= f < 190 else 'dot',
                            whole=(50.0, 50.0)), [(230, 320)])
STALE = key_scn('0.9.2: a stale fix (how none, then no writes): the hold keeps the icons; at -1 the fix is ignored',
                390, [140, 175, 205, 300, 370], by_frame({
                    140: lambda sim: placed(sim, 0) + [fresh(sim, True), held(sim, False)],
                    175: lambda sim: placed(sim, 0, truth(STALE_COMP, sim)) + b_shown(sim) + [
                        fresh(sim, False), held(sim, True),
                        logged(sim, r'companion: fix stale \(how none; its seq \d+, the mod at \d+\)$', 1),
                        logged(sim, r'companion: holding V from fix seq \d+ \(\d+ writes, 0\.0 m of pan\)$', 1)],
                    205: lambda sim: placed(sim, 0) + [fresh(sim, True), held(sim, False),
                                                       logged(sim, 'companion: fix fresh', 2)],
                    300: lambda sim: placed(sim, 0, truth(STALE_COMP, sim)) + b_shown(sim) + [
                        fresh(sim, False), held(sim, True),
                        logged(sim, r'companion: fix stale \(not one of the last 45 writes; its seq \d+, the mod at '
                                    r'\d+\)$', 1),
                        logged(sim, r'companion: holding V from fix seq \d+ \(\d+ writes, 0\.0 m of pan\)$', 2),
                        logged(sim, 'hold dropped', 0)],
                    370: lambda sim: placed(sim, -1) + [
                        held(sim, False), logged(sim, 'hold dropped', 0), logged(sim, 'not used', 0),
                        (vw(sim).fix is not None and vw(sim).fix.vx == 50, 'the fix read: V %s (want 50, ignored)' % (
                            vw(sim).fix.vx if vw(sim).fix is not None else None))],
                }),
                press=[90], companion=STALE_COMP, wheel=[(340, -1)])

# the fix's level: the game at +1 150..219 while the mod says 0 (a notch the mod missed); -1 at 220: both at 0
FL_COMP = companion((0.0, 0.0), start=100, game_level=lambda f: 1 if 150 <= f < 220 else 0)
FIX_LEVEL = key_scn("0.9: the companion's level (+1) overrides the mod's (0), logged once; after a notch, 0 again",
                    280, [140, 200, 260], by_frame({
                        140: lambda sim: placed(sim, 0),
                        200: lambda sim: placed(sim, 1) + geometry(sim, 1) + [
                            logged(sim, r'companion: level 1 from the fix \(seq \d+, a 191\.9 px grid cell\); the mod '
                                        r'had 0$', 1)],
                        260: lambda sim: placed(sim, 0) + [logged(sim, r'companion: level', 1)],
                    }),
                    press=[90], companion=FL_COMP, wheel=[(220, -1)])


# no companion: whole-map only. Tab 90 (0: nothing); -1 at 150 (placed); Tab close 200
def _nofile_240(sim):
    seqs = [int(fl['seq']) for (fr, fl) in sim.mod_lines]
    frames = [fr for (fr, fl) in sim.mod_lines]
    o0 = open0_lines(sim)
    return [map_open(sim, False), no_companion_logs(sim), paths_logged_once(sim), _no_fix_file(sim),
            (seqs == list(range(1, len(seqs) + 1)), 'seqs %s..%s, %d lines (want 1.. in a row)' % (
                seqs[0] if seqs else None, seqs[-1] if seqs else None, len(seqs))),
            (frames == list(range(frames[0], frames[0] + len(frames))) if frames else False,
             'one line a frame: frames %s..%s' % (frames[0] if frames else None, frames[-1] if frames else None)),
            (len(o0) == 1 and sim.mod_lines[-1][1].get('open') == '0', '%d open=0 lines, the last one\'s open=%s' % (
                len(o0), sim.mod_lines[-1][1].get('open') if sim.mod_lines else None))]


NOFILE = key_scn('0.9: no companion: whole-map only; a mod line a frame while open, one open=0 line at the close',
                 260, [140, 180, 240], by_frame({
                     140: lambda sim: nothing(sim) + [level_is(sim, 0), no_companion_logs(sim), _no_fix_file(sim)] +
                     line_is(sim, {'open': '1', 'level': '0', 'class': 'small', 'kz': '1.4766'}),
                     180: lambda sim: placed(sim, -1) + [no_companion_logs(sim)],
                     240: _nofile_240,
                 }),
                 press=[90, 200], wheel=[(150, -1)])

# a fix file from a past session (seq 5, +1, V 100, 100): ignored
BOOT = key_scn('0.9: a fix file from a past session at the start: ignored',
               200, [140, 190], by_frame({
                   140: lambda sim: nothing(sim) + [level_is(sim, 0), no_companion_logs(sim),
                                                    (not vw(sim).fresh, 'VW.fresh %s' % vw(sim).fresh)],
                   190: lambda sim: nothing(sim) + [level_is(sim, 0), no_companion_logs(sim), paths_logged_once(sim)],
               }),
               press=[90], fix_file='seq=5 ts=1761549000.000 how=dot vx=100.0 vy=100.0 err=0.5 level=1 cell=191.9 end\n')

# a fix whose V is 258 m from the player (0.9.1's gate, the rim's reach at 0 (150 m) plus 10, refused it): 0.9.2 uses
# it (the gate threw good fixes away on long pans)
FAR = key_scn('0.9.2: a fix 258 m from the player at 0: used (no distance gate)',
              220, [140, 210], by_frame({
                  140: lambda sim: placed(sim, 0, (300.0, 0.0)) + [fresh(sim, True), held(sim, False),
                                                                   logged(sim, 'not used', 0)],
                  210: lambda sim: placed(sim, 0, (300.0, 0.0)) + [logged(sim, 'not used', 0), held(sim, False)],
              }),
              press=[90], companion=companion((300.0, 0.0), start=100))

# ------------------------------------------------------------------ 13. the hold (0.9.2)
G0, G1 = GAIN[0], GAIN[1]

# the fix goes stale mid-pan. V 30, 40 at the open; the companion writes nothing from 150 (its last fix ~148, stale 45
# writes later, ~191); 160..259 3 east, 2 down a frame at 0 (300, 200 counts: 73.8 m east, 49.2 m south); +1 at 270;
# 280..299 6 west a frame (120 counts at +1: 14.8 m); Tab close at 340 drops the hold
HP_COMP = gate(companion((30.0, 40.0), start=100), [(150, 9999)])
HOLD_PAN = key_scn('0.9.2: the fix goes stale mid-pan: the hold carries V on by the mouse (0, then +1); the close '
                   'drops it',
                   370, [140, 180, 240, 262, 320, 360], by_frame({
                       140: lambda sim: placed(sim, 0, truth(HP_COMP, sim)) + [fresh(sim, True), held(sim, False)],
                       180: lambda sim: placed(sim, 0, truth(HP_COMP, sim)) + b_hidden(sim) + [
                           fresh(sim, True), held(sim, False)],
                       # 0.9.3: from here the hold carries V underneath, nothing drawn (no dot fix after the pan)
                       240: lambda sim: placed(sim, 0, truth(HP_COMP, sim)) + b_hidden(sim) + [
                           fresh(sim, False), held(sim, True),
                           logged(sim, r'companion: fix stale \(not one of the last 45 writes; its seq \d+, the mod '
                                       r'at \d+\)$', 1),
                           logged(sim, r'companion: holding V from fix seq \d+ \(\d+ writes, [\d.]+ m of pan\)$', 1)],
                       262: lambda sim: placed(sim, 0, truth(HP_COMP, sim)) + b_hidden(sim) + [
                           held(sim, True), v_is(sim, 30 + 300 * G0, 40 - 200 * G0, ': the fix plus 300, 200 counts'),
                           (abs(truth(HP_COMP, sim)[0] - (30 + 300 * G0)) < 1e-6, 'the game V %.2f, %.2f' % truth(
                               HP_COMP, sim))],
                       320: lambda sim: placed(sim, 1, truth(HP_COMP, sim)) + b_hidden(sim) + [
                           held(sim, True), v_is(sim, 30 + 300 * G0 - 120 * G1, 40 - 200 * G0, ': and 120 west at +1'),
                           logged(sim, 'hold dropped', 0), logged(sim, 'companion: holding V', 1)],
                       360: lambda sim: [
                           map_open(sim, False), held(sim, False),
                           logged(sim, r'companion: hold dropped \(the map closed; held from fix seq \d+, \d+ writes, '
                                       r'76\.9 m of pan\)$', 1)],
                   }),
                   press=[90, 340], companion=HP_COMP, raw=[(160, 260, 3, 2), (280, 300, -6, 0)], wheel=[(270, 1)])

# a zoom in from -1 drops the hold. V 30, 40; the companion writes nothing 160..259 (its last fix ~158, seq ~67); -1 at
# 162 (placed on the origin), 0 at 178: the hold drops, and the last fix (still one of the last 45 writes at 192) isn't
# used (a write at -1 after it): nothing world-anchored until the fixes come back (placed at 290)
HW_COMP = gate(companion((30.0, 40.0), start=100), [(160, 260)])
HOLD_WHOLE = key_scn('0.9.2: a zoom from -1 to 0 drops the hold; the fix from before -1 not used; a new fix places',
                     300, [140, 175, 192, 240, 290], by_frame({
                         140: lambda sim: placed(sim, 0, truth(HW_COMP, sim)) + [fresh(sim, True), held(sim, False)],
                         175: lambda sim: placed(sim, -1) + [held(sim, False), logged(sim, 'hold dropped', 0)],
                         192: lambda sim: nothing(sim) + [
                             level_is(sim, 0), fresh(sim, True), held(sim, False),
                             logged(sim, r'companion: hold dropped \(the zoom in from the whole map; held from fix seq '
                                         r'\d+, \d+ writes, 0\.0 m of pan\)$', 1),
                             logged(sim, r'companion: fix seq \d+ not used \(the map went to the whole-map level after '
                                         r'it\)$', 1)],
                         240: lambda sim: nothing(sim) + [fresh(sim, False), held(sim, False),
                                                          logged(sim, 'companion: holding V', 0)],
                         290: lambda sim: placed(sim, 0, truth(HW_COMP, sim)) + [
                             fresh(sim, True), held(sim, False), logged(sim, 'hold dropped', 1)],
                     }),
                     press=[90], companion=HW_COMP, wheel=[(162, -1), (183, 1)])


# the hold at the map's edge (a small map at 0: the game stops its view R 285.3 - rim / 1.4766 = 134.9 m out on each
# axis, REVIEW_0.8.2; the cursor 0.183 h further, 133.8 m, RESEARCH_MAP 9). V 100, 0; the companion writes nothing
# from 150 (stale ~191). 200..299 8 east a frame (800 counts, 196.8 m; the cursor stops at 268.8 m): V stops at 134.9;
# 310..359 8 west (98.4 m): the cursor comes back first, V stays; 370..399 8 west (59.0 m): V 111.3 (with no stop for
# the cursor it would still be 134.9). Checked against these numbers (the sim's companion doesn't stop its V)
def _edge(cursor, note):
    def fn(sim):
        S = sim.G.T.mod.main.S
        stop = 285.3 - S.map.r / KL[0]
        pin = 0.183 * 1080 / KL[0]
        x = min(stop, cursor(stop, pin))
        return placed(sim, 0, (x, 0.0)) + b_hidden(sim) + [
            held(sim, True), fresh(sim, False),
            v_is(sim, x, 0.0, ': %s; the view stops %.2f m out, the cursor %.2f' % (note, stop, stop + pin))]
    return fn


EDGE_COMP = gate(companion((100.0, 0.0), start=100), [(150, 9999)])
HOLD_EDGE = key_scn("0.9.2: the hold panned into the map's edge: V stops there, the cursor further; back, the "
                    'cursor first',
                    410, [180, 250, 302, 362, 402], by_frame({
                        180: lambda sim: placed(sim, 0, (100.0, 0.0)) + b_shown(sim) + [
                            fresh(sim, True), held(sim, False)],
                        250: _edge(lambda st, pin: 100 + 400 * G0, '400 counts east'),
                        302: _edge(lambda st, pin: min(100 + 800 * G0, st + pin), '800 counts east'),
                        362: _edge(lambda st, pin: min(100 + 800 * G0, st + pin) - 400 * G0, 'then 400 west'),
                        402: lambda sim: _edge(lambda st, pin: min(100 + 800 * G0, st + pin) - 640 * G0,
                                               'then 640 west')(sim) + [
                            (vw(sim).vx < 134.9 - 20, 'V x %.2f: inside the stop (the cursor stopped at the edge)' %
                             vw(sim).vx)],
                    }),
                    press=[90], companion=EDGE_COMP, raw=[(200, 300, 8, 0), (310, 360, -8, 0), (370, 400, -8, 0)])

# ------------------------------------------------------------------ 14. 0.9.3: B and the options
# settle and fade. V 30, 40; Tab 90 (settled by 125); 140..169 4 east a frame (120 counts at 0); +1 at 210
SET_COMP = companion((30.0, 40.0), start=100)
SETTLE = key_scn('0.9.3: settled at the open; a pan: the fade out, nothing drawn, still nothing 0.15 s on, drawn again '
                 'once still 0.2 s with a dot fix; a notch the same',
                 250, [125, 140, 142, 155, 178, 190, 218, 240], by_frame({
                     125: lambda sim: placed(sim, 0, truth(SET_COMP, sim)) + b_shown(sim),
                     140: fade_in(0.75, 0.9),
                     142: fade_in(0.4, 0.6),
                     155: lambda sim: b_hidden(sim) + [fresh(sim, True), v_is(sim, *truth(SET_COMP, sim),
                                                                               why=': the model underneath')],
                     178: lambda sim: b_hidden(sim) + [v_is(sim, *truth(SET_COMP, sim))],
                     190: lambda sim: placed(sim, 0, truth(SET_COMP, sim)) + b_shown(sim),
                     218: lambda sim: [(not vw(sim).settled, 'settled %s (want False: a notch at 210)' % vw(sim).settled),
                                       (world_draws(sim) == 0, '%d world-anchored draws 8 frames after a notch' %
                                        world_draws(sim))],
                     240: lambda sim: placed(sim, 1, truth(SET_COMP, sim)) + b_shown(sim) + [
                         logged(sim, 'not used', 0), logged(sim, 'on the move', 0),
                         logged(sim, 'no companion fix this session', 0)],
                 }),
                 press=[90], companion=SET_COMP, raw=[(140, 170, 4, 0)], wheel=[(210, 1)])

# grid fixes. V 30, 40; captures 100..129 grid (no hold yet), 130..159 dot, 160..219 grid, those published 192..221
# 40 m east of the truth, 220.. dot
GRID_COMP = alter(companion((30.0, 40.0), start=100, how=lambda f: 'grid' if f < 130 or 160 <= f < 220 else 'dot'),
                  bias_x([(192, 222, 40.0)]))
GRID = key_scn('0.9.3: grid fixes: refused with no hold, taken within 32 m of the hold, refused 40 m off, dot again',
               260, [125, 155, 185, 215, 250], by_frame({
                   125: lambda sim: nothing(sim) + [held(sim, False), how_is(sim, 'grid'), logged(
                       sim, r'companion: fix seq \d+ not used \(a grid fix with no hold to agree with\)$', 1)],
                   155: lambda sim: placed(sim, 0, truth(GRID_COMP, sim)) + b_shown(sim) + [how_is(sim, 'dot')],
                   185: lambda sim: placed(sim, 0, truth(GRID_COMP, sim)) + b_shown(sim) + [
                       how_is(sim, 'grid'), held(sim, False), fresh(sim, True), logged(sim, 'not used', 1)],
                   215: lambda sim: placed(sim, 0, truth(GRID_COMP, sim)) + b_shown(sim) + [
                       how_is(sim, 'grid'), held(sim, True),
                       (abs(vw(sim).fix.vx - 70.0) < 0.05, 'the fix read: V x %.1f (want 70.0)' % vw(sim).fix.vx),
                       logged(sim, r'companion: fix seq \d+ not used \(a grid fix more than 32 m from the hold\)$', 1)],
                   250: lambda sim: placed(sim, 0, truth(GRID_COMP, sim)) + b_shown(sim) + [
                       how_is(sim, 'dot'), held(sim, False), logged(sim, 'not used', 2)],
               }),
               press=[90], companion=GRID_COMP)

# a grid fix on the view's stop (a small map at 0: 285.3 - rim / 1.4766 = 134.9 m). V 134.5, 0; captures 100..129 dot,
# 130..239 grid, 240.. dot; 170..189 4 west a frame (80 counts: 19.7 m, off the stop)
GS_COMP = companion((134.5, 0.0), start=100, how=lambda f: 'dot' if f < 130 or f >= 240 else 'grid')


def _gs_hidden(sim):
    return b_hidden(sim) + [held(sim, False), how_is(sim, 'grid'), fresh(sim, True),
                            v_is(sim, *truth(GS_COMP, sim), why=': a grid fix taken'),
                            logged(sim, 'not used', 1)]


GRID_STOP = key_scn("0.9.3: a grid fix on the view's stop: refused (the hold draws); off it after a pan: taken, "
                    'nothing drawn until a dot fix',
                    270, [125, 160, 200, 230, 262], by_frame({
                        125: lambda sim: placed(sim, 0, (134.5, 0.0)) + b_shown(sim) + [how_is(sim, 'dot')],
                        160: lambda sim: placed(sim, 0, (134.5, 0.0)) + b_shown(sim) + [
                            how_is(sim, 'grid'), held(sim, True),
                            logged(sim, r"companion: fix seq \d+ not used \(a grid fix on the view's stop\)$", 1)],
                        200: _gs_hidden,
                        230: _gs_hidden,
                        262: lambda sim: placed(sim, 0, truth(GS_COMP, sim)) + b_shown(sim) + [
                            how_is(sim, 'dot'), held(sim, False)],
                    }),
                    press=[90], companion=GS_COMP, raw=[(170, 190, -4, 0)])

# the ease. V 30, 40, dot fixes; published 150..179 1 m east of it, 180..219 5 m, 220.. 40 m (from 35: 35 m, a snap)
EASE_COMP = alter(companion((30.0, 40.0), start=100), bias_x([(150, 180, 1.0), (180, 220, 5.0), (220, 9999, 40.0)]))
EASE_A, EASE_B = list(range(176, 201)), list(range(216, 233))
_eased = {}


def _ease_rec(sim):
    _eased[sim.frame_now] = (vw(sim).vx, vw(sim).tvx)
    return [(bool(vw(sim).trusted and vw(sim).settled), 'trusted %s, settled %s' % (vw(sim).trusted, vw(sim).settled))]


def _ease_a(sim):
    out = _ease_rec(sim)
    xs = [_eased[f][0] for f in EASE_A if f in _eased]
    mid = [f for f in EASE_A if f in _eased and 30.05 < _eased[f][0] < 34.95]
    up = all(b >= a - 1e-9 for a, b in zip(xs, xs[1:]))
    return out + [v_is(sim, 35.0, 40.0, ': eased to the 5 m fix'),
                  (abs(vw(sim).tvx - 35.0) < 0.05, "the model's V x %.2f (want 35.00)" % vw(sim).tvx),
                  (2 <= len(mid) <= 6 and up, 'the ease: %d frames between 30 and 35 (want 2..6, EASE_T 0.1 s), '
                                              'rising %s: %s' % (len(mid), up, ' '.join('%.2f' % x for x in xs)))]


def _ease_b(sim):
    out = _ease_rec(sim)
    xs = [_eased[f][0] for f in EASE_B if f in _eased]
    mid = [x for x in xs if 35.05 < x < 69.95]
    return out + [v_is(sim, 70.0, 40.0, ': snapped to the 40 m fix'),
                  (not mid, 'the snap: %d frames between 35 and 70 (want 0): %s' % (
                      len(mid), ' '.join('%.2f' % x for x in xs)))]


_EASE_T = {f: _ease_rec for f in EASE_A[:-1] + EASE_B[:-1]}
_EASE_T.update({
    170: lambda sim: b_shown(sim) + [v_is(sim, 30.0, 40.0, ': the 1 m fix inside the dead band'),
                                     (abs(vw(sim).tvx - 31.0) < 0.05, "the model's V x %.2f (want 31.00)" % vw(sim).tvx)],
    EASE_A[-1]: _ease_a, EASE_B[-1]: _ease_b,
    240: lambda sim: placed(sim, 0, (70.0, 40.0)) + b_shown(sim),
})
EASE = key_scn('0.9.3: the drawn V: a fix 1 m off moves nothing, 5 m eases over 0.1 s, 40 m snaps',
               250, sorted(_EASE_T), by_frame(_EASE_T), press=[90], companion=EASE_COMP)


# walking: the player 2 m/s north all along to frame 300 (y -1 + 2 t). Tab 90 (y 2.0); the companion's V 42, 5 (3 m
# from the player's spot at the open); captures grid before 140, dot 140..229, grid from 230. Tab close 200, open 230
# (still walking), close 290: no dot fix in that open
def _walk_cam():
    yaw = FACING - LOOK_TURN[2]
    y = lambda f: ME[1] + 2.0 * at(f)
    return [(0, ME[0], ME[1], 1.6, yaw, -6), (at(30), ME[0], y(30), 1.6, yaw, -6),
            (at(60), ME[0], y(60), 1.6, yaw + LOOK_TURN[2], -6), (at(300), ME[0], y(300), 1.6, yaw + LOOK_TURN[2], -6)]


WALK_COMP = companion((42.0, 5.0), start=100, how=lambda f: 'grid' if f < 140 or f >= 230 else 'dot')
WALK_LINE = r'open on the move: player moved ([\d.]+) m before the first dot fix, V moved ([\d.]+) m$'


def _walk_160(sim):
    got = [re.search(WALK_LINE, l) for l in logs(sim)]
    got = [m for m in got if m]
    pm, vm = (float(got[0].group(1)), float(got[0].group(2))) if got else (None, None)
    return b_shown(sim) + [
        v_is(sim, 42.0, 5.0, ': the dot fix'),
        (len(got) == 1 and 1.4 <= pm <= 1.9 and 2.8 <= vm <= 3.2,
         'the walking line: %d, player %s m (want 1.4..1.9: 2 m/s for ~0.87 s), V %s m (want ~3.0)' % (
             len(got), pm, vm))]


WALK = key_scn('0.9.3: opens on the move: logged; no grid fix before the first dot fix; the walking line; an open '
               'with no dot fix said at the close',
               330, [125, 160, 220, 260, 320], by_frame({
                   125: lambda sim: nothing(sim) + [
                       logged(sim, r'map: open on the move \(the player at 2\.0 m/s\): no grid fix before its first dot '
                                   r'fix$', 1),
                       logged(sim, r'companion: fix seq \d+ not used \(a grid fix before the first dot fix of an open on '
                                   r'the move\)$', 1),
                       logged(sim, 'grid fix with no hold', 0)],
                   160: _walk_160,
                   220: lambda sim: [map_open(sim, False), logged(sim, 'no dot fix before the close', 0)],
                   260: lambda sim: nothing(sim) + [logged(sim, r'map: open on the move \(', 2)],
                   320: lambda sim: [map_open(sim, False),
                                     logged(sim, r'open on the move: no dot fix before the close$', 1),
                                     logged(sim, WALK_LINE, 1),
                                     logged(sim, r'not used \(a grid fix before the first dot fix of an open on the '
                                                 r'move\)$', 2)],
               }),
               press=[90, 200, 230, 290], companion=WALK_COMP, camera=_walk_cam())

# no companion: Tab 90, close 140 (50 frames open at 0), Tab 200 (at 0 again: 1 s at 260); -1 at 280; close 330, open
# 360 (-1 kept), +1 to 0 at 400
NOFIX_RE = r'no companion fix this session: world icons at the whole-map zoom only$'
NOFIX = key_scn('0.9.3: no companion: "no companion fix this session" once, after 1 s open at 0',
                450, [150, 250, 270, 320, 440], by_frame({
                    150: lambda sim: [map_open(sim, False), logged(sim, NOFIX_RE, 0)],
                    250: lambda sim: nothing(sim) + [logged(sim, NOFIX_RE, 0)],
                    270: lambda sim: nothing(sim) + [logged(sim, NOFIX_RE, 1), no_companion_logs(sim)],
                    320: lambda sim: placed(sim, -1) + b_shown(sim) + [logged(sim, NOFIX_RE, 1)],
                    440: lambda sim: nothing(sim) + [level_is(sim, 0), logged(sim, NOFIX_RE, 1),
                                                     logged(sim, 'no companion fix', 1)],
                }),
                press=[90, 140, 200, 330, 360], wheel=[(280, -1), (400, 1)])

# the legend. 'always': left of the corner radar while the map is closed (radar.place: its right edge 16 px (1080p)
# left of the radar's rim, centred on it, the main world's 960-962), beside the open map while open (TOP + 930..932)
PANEL_MAIN, LEG_MAIN = (960, 960), (960, 962)
PANEL_TOP = (LEGEND_LAYERS[0], LEGEND_LAYERS[0])
RADAR_LAYERS, MARKER_LAYERS = (900, 949), (860, 899)


def panel_box(sim, lo, hi):
    """the legend panel's box (its rects and corner bitmaps), screen px, bottom-left origin; None: none drawn"""
    d = sim.SIM.draws
    xs, ys = [], []
    for i in range(1, len(d) + 1):
        r = d[i]
        if r.layer is not None and lo <= r.layer <= hi and r.op in ('rect', 'bitmap') and r.w is not None:
            xs += [r.x, r.x + r.w]
            ys += [r.y, r.y + r.h]
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def legend_closed(where):
    """the map closed: the panel on the main world's layers, at `where` ('radar': left of radar.place, 'map': the open
    map's spot), none on the top layers"""
    def fn(sim):
        T = sim.G.T
        S = T.mod.main.S
        s = sim.h / 1080
        b = panel_box(sim, *PANEL_MAIN)
        out = [map_open(sim, False), (b is not None, 'the legend panel on 960 (the main world): %s' % (b,)),
               (layer_draws(sim, *LEGEND_LAYERS) == 0, '%d legend draws on the top layers (want 0: the map closed)' % (
                   layer_draws(sim, *LEGEND_LAYERS))),
               (layer_draws(sim, 961, 961) > 0 and layer_draws(sim, 962, 962) > 0, 'icons %d, counts %d' % (
                   layer_draws(sim, 961, 961), layer_draws(sim, 962, 962)))]
        if b is None:
            return out
        if where == 'radar':
            rx, ry, rr = T.mod.radar.place(S)
            x1, yc = rx - rr - 16 * s, ry
            out.append((layer_draws(sim, *RADAR_LAYERS) > 0, '%d radar draws' % layer_draws(sim, *RADAR_LAYERS)))
        else:
            x1, yc = S.map.cx - (225 + 16) * s, S.map.cy
        out.append((abs(b[2] - x1) <= 1.0 and abs((b[1] + b[3]) / 2 - yc) <= 1.5 and b[0] >= 0 and b[1] >= 0 and
                    b[3] <= sim.h,
                    'the panel %.1f..%.1f x %.1f..%.1f (bottom-left), its right edge and centre %.1f, %.1f (want %.1f, '
                    '%.1f: %s)' % (b[0], b[2], b[1], b[3], b[2], (b[1] + b[3]) / 2, x1, yc,
                                   'left of the radar' if where == 'radar' else "the open map's spot")))
        return out
    return fn


def legend_open(sim):
    S = sim.G.T.mod.main.S
    s = sim.h / 1080
    b = panel_box(sim, *PANEL_TOP)
    x1 = S.map.cx - (225 + 16) * s
    return [map_open(sim, True), (b is not None, 'the legend panel on the top layer: %s' % (b,)),
            (layer_draws(sim, *LEG_MAIN) == 0, '%d legend draws on 960-962 (want 0: the map open)' % layer_draws(
                sim, *LEG_MAIN))] + ([
        (abs(b[2] - x1) <= 1.0 and abs((b[1] + b[3]) / 2 - S.map.cy) <= 1.5,
         'the panel right edge %.1f, centre %.1f (want %.1f, %.1f: left of the map rim)' % (
             b[2], (b[1] + b[3]) / 2, x1, S.map.cy))] if b else [])


def no_legend(sim):
    n = layer_draws(sim, *LEG_MAIN) + layer_draws(sim, *LEGEND_LAYERS)
    return [(n == 0, '%d legend draws (want 0)' % n)]


def legend_always(about, size=(1920, 1080)):
    # Tab 90, -1 at 120 (the whole map, placed with no companion); close 180; F7 230, F7 250
    scn = key_scn(about, 270, [60, 140, 220, 240, 262], by_frame({
        60: legend_closed('radar'),
        140: lambda sim: legend_open(sim) + placed_k(sim, -1, KW['small']) + b_shown(sim),
        220: legend_closed('radar'),
        240: lambda sim: no_legend(sim) + [logged(sim, r'mod HUD hidden \(F7\)$', 1)],
        262: lambda sim: legend_closed('radar')(sim) + [logged(sim, r'mod HUD shown \(F7\)$', 1)],
    }), press=[90, 180], wheel=[(120, -1)], size=size, options={'legend': 'always'})
    scn['press'] = scn['press'] + [(at(230), 'f7'), (at(250), 'f7')]
    return scn


LEGEND_ALWAYS = legend_always("0.9.3: legend 'always' at 1080p: left of the radar closed, beside the map open, F7")
LEGEND_ALWAYS_UW = legend_always("0.9.3: legend 'always' at 3440x1440: left of the radar closed, beside the map open, "
                                 'F7; the whole map placed', (3440, 1440))


def _no_radar_60(sim):
    return legend_closed('map')(sim) + [
        (layer_draws(sim, *RADAR_LAYERS) == 0, '%d radar draws (want 0: no_radar)' % layer_draws(sim, *RADAR_LAYERS)),
        (layer_draws(sim, *COMPASS_LAYERS) > 0, '%d compass draws' % layer_draws(sim, *COMPASS_LAYERS))]


LEGEND_NO_RADAR = key_scn("0.9.3: legend 'always', mode no_radar: no radar; the legend at the open map's spot; the "
                          "map's icons at -1 (the structures listed with no radar)",
                          160, [60, 140], by_frame({
                              60: _no_radar_60,
                              140: lambda sim: legend_open(sim) + placed(sim, -1) + b_shown(sim),
                          }), press=[90], wheel=[(120, -1)], options={'legend': 'always', 'mode': 'no_radar'})


def _map_only_60(sim):
    return legend_closed('map')(sim) + [
        (layer_draws(sim, *RADAR_LAYERS) == 0, '%d radar draws (want 0)' % layer_draws(sim, *RADAR_LAYERS)),
        (layer_draws(sim, *COMPASS_LAYERS) == 0, '%d compass draws (want 0)' % layer_draws(sim, *COMPASS_LAYERS)),
        (layer_draws(sim, *MARKER_LAYERS) == 0, '%d pin draws (want 0)' % layer_draws(sim, *MARKER_LAYERS))]


MAP_ONLY = key_scn("0.9.3: mode map_only, legend 'always': no radar, compass or pins; the map's icons at -1",
                   180, [60, 150], by_frame({
                       60: _map_only_60,
                       150: lambda sim: legend_open(sim) + placed(sim, -1) + b_shown(sim),
                   }), press=[90], wheel=[(120, -1)], options={'legend': 'always', 'mode': 'map_only'})

LEGEND_OFF = key_scn("0.9.3: legend 'off': no legend open or closed",
                     160, [60, 150], by_frame({
                         60: lambda sim: no_legend(sim) + [map_open(sim, False)],
                         150: lambda sim: no_legend(sim) + placed(sim, -1) + [map_open(sim, True)],
                     }), press=[90], wheel=[(120, -1)], options={'legend': 'off'})
LEGEND_MAP = key_scn("0.9.3: legend 'map' (the default): none while the map is closed, beside it open",
                     160, [60, 150], by_frame({
                         60: lambda sim: no_legend(sim) + [map_open(sim, False)],
                         150: legend_open,
                     }), press=[90], wheel=[(120, -1)])

SCENARIOS = {
    'map09_levels': LEVELS,
    'map09_skid': SKID,
    'map09_skid_fix': SKID_FIX,
    'map09_skid_fix_one': SKID_FIX_ONE,
    'map09_ignored_close': IGNORED_CLOSE,
    'map09_ignored_open': IGNORED_OPEN,
    'map09_second_tab': SECOND_TAB,
    'map09_real_open': REAL_OPEN,
    'map09_anim': ANIM,
    'map09_drift': DRIFT,
    'map09_drift_nolook': DRIFT_NOLOOK,
    'map09_nocam': NOCAM,
    'map09_big': BIG,
    'map09_unmeasured': UNMEASURED,
    'map09_1440': RES_1440,
    'map09_4k': RES_4K,
    'map09_fix': FIX,
    'map09_fix_poll': FIX_POLL,
    'map09_stale': STALE,
    'map09_fix_level': FIX_LEVEL,
    'map09_nofile': NOFILE,
    'map09_boot': BOOT,
    'map09_far': FAR,
    'map09_hold_pan': HOLD_PAN,
    'map09_hold_whole': HOLD_WHOLE,
    'map09_hold_edge': HOLD_EDGE,
    'map09_settle': SETTLE,
    'map09_grid': GRID,
    'map09_grid_stop': GRID_STOP,
    'map09_ease': EASE,
    'map09_walk': WALK,
    'map09_nofix_log': NOFIX,
    'map09_legend_always': LEGEND_ALWAYS,
    'map09_legend_always_uw': LEGEND_ALWAYS_UW,
    'map09_legend_no_radar': LEGEND_NO_RADAR,
    'map09_map_only': MAP_ONLY,
    'map09_legend_off': LEGEND_OFF,
    'map09_legend_map': LEGEND_MAP,
    'map09_uw': RES_UW,
}
