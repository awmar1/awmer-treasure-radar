r"""fit_map: the game's map constants from a measuring mission (Ammar Treasure Radar 0.8; PLAN_0.8.md, section 4).

    python -I -B dev/tools/fit_map.py --picks picks.json [--log LOG] [--session N] [--draw OUT --shots DIR]
    python -I -B dev/tools/fit_map.py --selftest [LOG]

The log is the measurement build's own file (measure.lua): %LOCALAPPDATA%\treasure_radar_measure08.txt by default.
It is only read. The picks are spots read off the Steam screenshots, in the screenshot's own pixels (top-left
origin), one entry per F12 snapshot (the 'snap n=' of the log; the loader's log and the MEASURE n note say it too):

    {"session": 2,                            optional: which '#' session of the log (default: the last)
     "picks": [
      {"snap": 4, "shot": "20261026133201_1.jpg",
       "me": [1734, 856],                     the game's yellow dot
       "cursor": [1873, 819],                 the tip of the game's map cursor
       "loot": {"2": [1683, 781]},            a pile's icon, by the i of its snap.loot line
       "mark": {"1": [1769, 949]},            a structure's or objective's icon, by the i of its snap.mark line
       "origin": [1675, 819],                 the world origin, if it can be told (the view centre before a pan)
       "readout": [35, 45],                   the cursor readout, e.g. "NE (45°) 35 meters"
       "rim": [[1453, 819], [1675, 597], [1897, 819]],   3 or more points on the map circle's rim
       "size": [1920, 1080]}]}                the screenshot's size, if it isn't the game's (default: the log's w, h)

What it fits, each from what the picks allow (a missing pick only skips what needs it):
  cursor   px per raw mouse count (at 1080p), where the cursor stops (of the screen height) and the y sign, from the
           cursor picks: the mouse lines are replayed from the open, with the cursor starting at the map's centre
  zoom     per mission: k0 (px per m per screen height at level 0, x2 per level), the lowest and highest level, the
           wheel's sign, whether one frame's two notches count twice, whether the zoom resets on opening, and the
           ease (exponential in log2 of the scale); from each snapshot's scale (two picked points' distance over
           their distance in the world; one point is enough while the map can't have panned)
  pan      the edge-pan rule: A (the map pans a px per px the mouse pushes past the stop), B (v px per second while
           the cursor sits at the stop), both, or none; from where the picked points sit
  readout  where the cursor readout measures from: me, the world origin or the view centre
  rim      the map circle's centre and radius (a check on the log's cx, cy, r)
--draw puts the fitted spots on each picked screenshot (a crop around the map): the model's me (magenta ring), piles
and marks (cyan squares) and cursor (green cross), and the picks (red dots).
--selftest makes picks from the sim's synthetic log (python -I -B src/sim/sim.py measure, from dev) with known
constants, ±0.5 px of noise, fits them back and checks the fit; it prints PASS or FAIL and exits 0 or 1.
"""
import argparse
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEV = os.path.normpath(os.path.join(HERE, '..'))
FILE = 'treasure_radar_measure08.txt'
SIM_LOG = os.path.join(DEV, 'out', 'sim', 'measure', 'localappdata', FILE)
H0 = 1080.0
GAIN0, STOP0, K00 = 0.21, 0.183, 0.001375      # measure.lua's own guesses
TAUS = [i * 0.02 for i in range(31)]            # the ease's coarse grid (s)


# ------------------------------------------------------------------ the log

def value(s):
    try:
        return float(s)
    except ValueError:
        return s


def parse(path):
    """The log's sessions, each {'head', 'missions', 'snaps'}; a mission holds its records by kind."""
    sessions, mis = [], None
    with open(path, encoding='utf-8', errors='replace') as f:
        for raw in f:
            raw = raw.rstrip('\r\n')
            if raw.startswith('#'):
                if 'measure log' in raw or not sessions:
                    sessions.append({'head': raw[1:].strip(), 'missions': [], 'snaps': {}})
                    mis = None
                continue
            parts = raw.split(' ')
            if len(parts) < 2 or not sessions:
                continue
            try:
                t = float(parts[0])
            except ValueError:
                continue
            tag = parts[1]
            rec = {'t': t}
            for kv in parts[2:]:
                if '=' in kv:
                    k, v = kv.split('=', 1)
                    rec[k] = value(v)
            sess = sessions[-1]
            if tag == 'mission':
                mis = {'rec': rec, 'index': len(sess['missions']) + 1, 'open': [], 'close': [], 'zoom': [],
                       'mouse': [], 'click': []}
                sess['missions'].append(mis)
            elif mis is None:
                continue
            elif tag in ('open', 'close', 'zoom', 'mouse', 'click'):
                mis[tag].append(rec)
            elif tag == 'snap':
                sess['snaps'][int(rec['n'])] = {'t': t, 'rec': rec, 'mis': mis, 'me': None, 'loot': {}, 'mark': {}}
            elif tag in ('snap.me', 'snap.loot', 'snap.mark'):
                sn = sess['snaps'].get(int(rec.get('n', -1)))
                if sn is None:
                    continue
                if tag == 'snap.me':
                    sn['me'] = rec
                else:
                    sn[tag[5:]][int(rec['i'])] = rec
    for sess in sessions:
        for mis in sess['missions']:
            ends = {int(c['n']): c['t'] for c in mis['close']}
            mis['opens'] = []
            for o in mis['open']:
                end = ends.get(int(o['n']))
                inside = lambda r: o['t'] < r['t'] <= (end if end is not None else 1e18) + 1e-6  # noqa: E731
                mis['opens'].append({'n': int(o['n']), 't': o['t'], 'end': end, 'rec': o,
                                     'mouse': [(r['t'], r['dx'], r['dy']) for r in mis['mouse'] if inside(r)],
                                     'zoom': [(r['t'], r['d']) for r in mis['zoom'] if inside(r)]})
    return sessions


def context(sn):
    """A snapshot's open map: its mission's screen, its open, and the mouse and zoom since the open."""
    rec, mis = sn['rec'], sn['mis']
    if not rec.get('open'):
        return None
    oi = None
    for i, op in enumerate(mis['opens']):
        if op['t'] <= sn['t'] + 1e-6 and (op['end'] is None or op['end'] >= sn['t'] - 1e-6):
            oi = i
    if oi is None:
        return None
    op, t = mis['opens'][oi], sn['t']
    return {'n': int(rec['n']), 't': t, 'mis': mis, 'opens': mis['opens'], 'oi': oi, 'op': op,
            'w': rec['w'], 'h': rec['h'], 'cx': rec['cx'], 'cy': rec['cy'], 'r': rec['r'], 'sn': sn,
            'mouse': [e for e in op['mouse'] if e[0] <= t + 1e-6],
            'zoom': [e for e in op['zoom'] if e[0] <= t + 1e-6]}


# ------------------------------------------------------------------ the models

def cursor_run(c, g, stop, ys):
    """The mouse replayed from the open: the cursor at the snapshot, each push past the stop (t, px, py) and the
    spells at the stop (t from, t to, unit direction)."""
    cx, cy, h = c['cx'], c['cy'], c['h']
    lim, s = stop * h, g * h / H0
    x, y, pushes, segs, at = cx, cy, [], [], None
    for t, dx, dy in c['mouse']:
        nx, ny = x + dx * s, y + ys * dy * s
        ox, oy = nx - cx, ny - cy
        d = math.hypot(ox, oy)
        if d > lim:
            f = lim / d
            px, py = cx + ox * f, cy + oy * f
            pushes.append((t, nx - px, ny - py))
            nx, ny = px, py
        if at is not None:
            segs.append((at[0], t, at[1], at[2]))
            at = None
        x, y = nx, ny
        d = math.hypot(x - cx, y - cy)
        if d >= lim - 0.25 and d > 0:
            at = (t, (x - cx) / d, (y - cy) / d)
    if at is not None and c['t'] > at[0]:
        segs.append((at[0], c['t'], at[1], at[2]))
    return x, y, pushes, segs


def ease(L, target, dt, tau):
    if tau <= 0:
        return target
    return L if dt <= 0 else target + (L - target) * math.exp(-dt / tau)


def run_zoom(zoom, t0, t, start, Z):
    """One open's zoom up to t under Z = (lo, hi, sign, multi, reset, tau): the eased level, the level it's heading
    for, the last change's time (None: none), and the notches past lo and past hi."""
    lo, hi, sign, multi, _, tau = Z
    L = target = float(start)
    last, changed, past = t0, None, [0, 0]
    for tz, d in zoom:
        if tz > t + 1e-6:
            break
        L, last = ease(L, target, tz - last, tau), tz
        n = int(round(d * sign))
        step = 1 if n > 0 else -1
        for _ in range(abs(n) if multi == 'each' else min(1, abs(n))):
            nt = min(hi, max(lo, target + step))
            if nt == target:
                past[step > 0] += 1
            else:
                target, changed = nt, tz
    return ease(L, target, t - last, tau), target, changed, past[0], past[1]


def start_level(opens, oi, Z):
    if Z[4] or oi == 0:
        return 0
    prev = opens[oi - 1]
    end = prev['end'] if prev['end'] is not None else prev['t']
    return run_zoom(prev['zoom'], prev['t'], end, start_level(opens, oi - 1, Z), Z)[1]


def level(c, t, Z):
    return run_zoom(c['zoom'], c['op']['t'], t, start_level(c['opens'], c['oi'], Z), Z)


def pan_basis(c, pushes, segs, kf):
    """Rule A's and rule B's pans in metres per unit coefficient: U (per px pushed), W (per px/s at the stop)."""
    ux = uy = wx = wy = 0.0
    for t, px, py in pushes:
        k = kf(t)
        ux, uy = ux + px / k, uy + py / k
    for t0, t1, dx, dy in segs:
        dt = t1 - t0
        k = kf(0.5 * (t0 + t1))
        wx, wy = wx + dx * dt / k, wy + dy * dt / k
    return (ux, uy), (wx, wy)


# ------------------------------------------------------------------ picks

def prepare(sess, picks, say):
    """The picked snapshots, each with its context, points [(world x, y, screen x, y, label)], cursor and readout."""
    out, size0 = [], picks.get('size')
    for p in picks.get('picks', []):
        n = int(p['snap'])
        sn = sess['snaps'].get(n)
        c = context(sn) if sn else None
        if c is None:
            say(f'  snap {n}: {"not in this session" if sn is None else "the map was closed"}; skipped')
            continue
        w, h = c['w'], c['h']
        size = p.get('size') or size0 or [w, h]
        conv = lambda q: (q[0] * w / size[0], h - q[1] * h / size[1])  # noqa: E731
        pts = []
        if p.get('me') and sn['me']:
            pts.append((sn['me']['x'], sn['me']['y']) + conv(p['me']) + ('me',))
        for kind in ('loot', 'mark'):
            for i, q in (p.get(kind) or {}).items():
                r = sn[kind].get(int(i))
                if r is None:
                    say(f'  snap {n}: no {kind} {i} in the log; skipped')
                else:
                    pts.append((r['x'], r['y']) + conv(q) + (f'{kind} {i}',))
        if p.get('origin'):
            pts.append((0.0, 0.0) + conv(p['origin']) + ('origin',))
        c.update(pick=p, points=pts, cursor=conv(p['cursor']) if p.get('cursor') else None,
                 readout=p.get('readout'), rim=[conv(q) for q in p.get('rim') or []])
        out.append(c)
    return out


def scale_of(c, unpanned):
    """The snapshot's scale in px per m per screen height: from pairs of points, or (unpanned) from the centre."""
    pts, ks = c['points'], []
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            dw = math.hypot(pts[i][0] - pts[j][0], pts[i][1] - pts[j][1])
            if dw > 5:
                ks.append(math.hypot(pts[i][2] - pts[j][2], pts[i][3] - pts[j][3]) / dw)
    if not ks and unpanned:
        for wx, wy, sx, sy, _ in pts:
            dw = math.hypot(wx, wy)
            if dw > 10:
                ks.append(math.hypot(sx - c['cx'], sy - c['cy']) / dw)
    if not ks:
        return None
    ks.sort()
    return ks[len(ks) // 2] / c['h']


def circle(pts):
    """The circle through the points (least squares): centre x, y and radius."""
    sx = sy = sxx = syy = sxy = sxz = syz = sz = 0.0
    n = len(pts)
    for x, y in pts:
        z = x * x + y * y
        sx, sy, sz = sx + x, sy + y, sz + z
        sxx, syy, sxy, sxz, syz = sxx + x * x, syy + y * y, sxy + x * y, sxz + x * z, syz + y * z
    a = [[sxx, sxy, sx, -sxz], [sxy, syy, sy, -syz], [sx, sy, n, -sz]]
    for i in range(3):                       # Gauss-Jordan on the normal equations of x²+y² + Dx + Ey + F = 0
        p = max(range(i, 3), key=lambda r: abs(a[r][i]))
        a[i], a[p] = a[p], a[i]
        if abs(a[i][i]) < 1e-12:
            return None
        for r in range(3):
            if r != i:
                f = a[r][i] / a[i][i]
                a[r] = [a[r][j] - f * a[i][j] for j in range(4)]
    D, E, F = (a[i][3] / a[i][i] for i in range(3))
    return -D / 2, -E / 2, math.sqrt(max(0.0, D * D / 4 + E * E / 4 - F))


# ------------------------------------------------------------------ the fit

def fit_cursor(cs, say):
    picked = [c for c in cs if c['cursor']]
    gain = next((c['mis']['rec'].get('gain') for c in cs if isinstance(c['mis']['rec'].get('gain'), float)), GAIN0)
    res = {'g': gain, 'stop': STOP0, 'ys': -1, 'n': len(picked), 'rms': None, 'g_seen': False, 'stop_seen': False,
           'ys_seen': False, 'start': None}
    if not picked:
        say(f'  cursor: no cursor picks; the log\'s gain {gain:g} and a stop at {STOP0} h are assumed')
        return res

    def err(g, stop, ys):
        e = 0.0
        for c in picked:
            x, y, _, _ = cursor_run(c, g, stop, ys)
            e += (x - c['cursor'][0]) ** 2 + (y - c['cursor'][1]) ** 2
        return e

    grid = [(g / 100, 0.12 + s * 0.005, ys) for g in range(2, 151) for s in range(27) for ys in (-1, 1)]
    g, stop, ys = min(grid, key=lambda q: err(*q))
    fine = [(g + i * 0.0005, stop + j * 0.0005, ys) for i in range(-20, 21) for j in range(-10, 11)
            if g + i * 0.0005 > 0]
    g, stop, ys = min(fine, key=lambda q: err(*q))
    runs = [cursor_run(c, g, stop, ys) for c in picked]
    res.update(g=g, stop=stop, ys=ys, rms=math.sqrt(err(g, stop, ys) / len(picked)),
               g_seen=any(c['mouse'] for c in picked),
               stop_seen=any(r[2] for r in runs),
               ys_seen=any(abs(sum(e[2] for e in c['mouse'])) * g > 3 for c in picked))
    if not res['stop_seen']:
        res['stop'] = STOP0
    if not res['ys_seen']:
        res['ys'] = -1
    still = [c for c in picked if not c['mouse']]
    if still:
        res['start'] = (max(math.hypot(c['cursor'][0] - c['cx'], c['cursor'][1] - c['cy']) for c in still),
                        len(still))
    return res


def fit_zoom(cs, cur, say):
    """Per mission: the levels, k0 and the ease."""
    out = []
    for mis in sorted({id(c['mis']): c['mis'] for c in cs}.values(), key=lambda m: m['index']):
        mc = []
        for c in cs:
            if c['mis'] is not mis:
                continue
            _, _, pushes, segs = cursor_run(c, cur['g'], cur['stop'], cur['ys'])
            c['still'] = not pushes and not segs
            c['scale'] = scale_of(c, c['still'])
            if c['scale']:
                mc.append(c)
        if not mc:
            say(f'  zoom: mission {mis["index"]}: no snapshot with a scale (two points, or one before any pan)')
            continue
        multi = ('each', 'once') if any(abs(d) > 1 for c in mc for _, d in c['zoom']) else ('each',)

        def score(Z):
            logs = [math.log2(c['scale']) - level(c, c['t'], Z)[0] for c in mc]
            m = sum(logs) / len(logs)
            return math.sqrt(sum((v - m) ** 2 for v in logs) / len(logs)), m

        def penalty(Z):
            return 1e-4 * (Z[1] - Z[0]) + 1e-5 * ((Z[2] < 0) + (Z[3] != 'each') + (not Z[4])) + 1e-6 * Z[5]

        def best(Zs):
            return min(((score(Z)[0] + penalty(Z), Z) for Z in Zs), key=lambda q: q[0])[1]

        Zs = [(lo, hi, sg, mu, rs, tau) for lo in range(-4, 1) for hi in range(0, 5) for sg in (1, -1)
              for mu in multi for rs in (True, False) for tau in TAUS]
        Z = best(Zs)
        Z = best([Z[:5] + (max(0.0, Z[5] + i * 0.0025),) for i in range(-8, 9)])
        rms, m = score(Z)
        # a limit is confirmed when one level more on that side fits clearly worse
        def worse(Zw):
            return best([Zw[:5] + (tau,) for tau in TAUS])
        lo_ok = score(worse((Z[0] - 1,) + Z[1:]))[0] > max(0.05, 3 * rms) if Z[0] > -4 else False
        hi_ok = score(worse((Z[0], Z[1] + 1) + Z[2:]))[0] > max(0.05, 3 * rms) if Z[1] < 4 else False
        moving = sum(1 for c in mc if (lambda q: q[2] is not None and c['t'] - q[2] < 0.5)(level(c, c['t'], Z)))
        reopened = len({c['oi'] for c in mc}) > 1
        out.append({'mis': mis, 'Z': Z, 'k0': 2 ** m, 'rms': rms, 'n': len(mc), 'lo_ok': lo_ok, 'hi_ok': hi_ok,
                    'moving': moving, 'reopened': reopened, 'snaps': mc})
    return out


def kf_of(c, zm):
    Z, k0, h = zm['Z'], zm['k0'], c['h']
    return lambda t: k0 * h * 2 ** level(c, t, Z)[0]


def fit_pan(cs, cur, zooms):
    by_mis = {id(z['mis']): z for z in zooms}
    rows = []
    for c in cs:
        zm = by_mis.get(id(c['mis']))
        if zm is None or not c['points']:
            continue
        kf = kf_of(c, zm)
        k = kf(c['t'])
        _, _, pushes, segs = cursor_run(c, cur['g'], cur['stop'], cur['ys'])
        U, W = pan_basis(c, pushes, segs, kf)
        n = len(c['points'])
        px = sum(wx - (sx - c['cx']) / k for wx, wy, sx, sy, _ in c['points']) / n
        py = sum(wy - (sy - c['cy']) / k for wx, wy, sx, sy, _ in c['points']) / n
        rows.append({'c': c, 'k': k, 'U': U, 'W': W, 'P': (px, py), 'w': n * k * k, 'n': n})
    if not rows:
        return None

    def rms(a, v):
        e = sum(r['w'] * ((r['P'][0] - a * r['U'][0] - v * r['W'][0]) ** 2 +
                          (r['P'][1] - a * r['U'][1] - v * r['W'][1]) ** 2) for r in rows)
        return math.sqrt(e / sum(r['n'] for r in rows))

    def dot(f, g):
        return sum(r['w'] * (f(r)[0] * g(r)[0] + f(r)[1] * g(r)[1]) for r in rows)

    U, W, P = (lambda r: r['U']), (lambda r: r['W']), (lambda r: r['P'])
    uu, ww, uw, up, wp = dot(U, U), dot(W, W), dot(U, W), dot(U, P), dot(W, P)
    fits = {'none': (0.0, 0.0)}
    if uu > 0:
        fits['A'] = (up / uu, 0.0)
    if ww > 0:
        fits['B'] = (0.0, wp / ww)
    det = uu * ww - uw * uw
    if uu > 0 and ww > 0 and abs(det) > 1e-12 * uu * ww:
        fits['A+B'] = ((up * ww - wp * uw) / det, (wp * uu - up * uw) / det)
    errs = {k: rms(*v) for k, v in fits.items()}
    rule = 'none'
    one = min((k for k in ('A', 'B') if k in errs), key=lambda k: errs[k], default=None)
    if one and errs[one] < 0.8 * errs['none'] and errs['none'] - errs[one] > 1:
        rule = one
        if 'A+B' in errs and errs['A+B'] < 0.8 * errs[one] and errs[one] - errs['A+B'] > 1:
            rule = 'A+B'
    start = [math.hypot(*r['P']) for r in rows if r['U'] == (0.0, 0.0) and r['W'] == (0.0, 0.0)]
    return {'rule': rule, 'a': fits[rule][0], 'v': fits[rule][1], 'errs': errs, 'rows': rows, 'start': start,
            'pushed': uu > 0, 'parked': ww > 0}


def pan_at(c, cur, zm, pan):
    kf = kf_of(c, zm)
    _, _, pushes, segs = cursor_run(c, cur['g'], cur['stop'], cur['ys'])
    U, W = pan_basis(c, pushes, segs, kf)
    a, v = (pan['a'], pan['v']) if pan else (0.0, 0.0)
    return (a * U[0] + v * W[0], a * U[1] + v * W[1]), kf(c['t'])


def fit_readout(cs, cur, zooms, pan):
    by_mis = {id(z['mis']): z for z in zooms}
    obs = {id(r['c']): r['P'] for r in (pan['rows'] if pan else [])}
    errs, bear, n = {'me': 0.0, 'origin': 0.0, 'centre': 0.0}, {'me': [], 'origin': [], 'centre': []}, 0
    for c in cs:
        zm = by_mis.get(id(c['mis']))
        if zm is None or not c['readout'] or not c['cursor'] or not c['sn']['me']:
            continue
        P, k = pan_at(c, cur, zm, pan)
        P = obs.get(id(c), P)
        wx, wy = P[0] + (c['cursor'][0] - c['cx']) / k, P[1] + (c['cursor'][1] - c['cy']) / k
        m, deg = float(c['readout'][0]), float(c['readout'][1])
        me = c['sn']['me']
        for key, (ox, oy) in (('me', (me['x'], me['y'])), ('origin', (0.0, 0.0)), ('centre', P)):
            d = math.hypot(wx - ox, wy - oy)
            errs[key] += (d - m) ** 2
            if m > 5 and d > 5:
                b = math.degrees(math.atan2(wx - ox, wy - oy)) % 360
                bear[key].append(abs((b - deg + 180) % 360 - 180))
        n += 1
    if not n:
        return None
    errs = {k: math.sqrt(v / n) for k, v in errs.items()}
    return {'from': min(errs, key=lambda k: errs[k]), 'errs': errs, 'n': n,
            'bearing': {k: (sum(v) / len(v) if v else None) for k, v in bear.items()}}


def fit(sess, picks, say=print):
    cs = prepare(sess, picks, say)
    res = {'cs': cs, 'cursor': fit_cursor(cs, say)}
    res['zoom'] = fit_zoom(cs, res['cursor'], say)
    res['pan'] = fit_pan(cs, res['cursor'], res['zoom'])
    res['readout'] = fit_readout(cs, res['cursor'], res['zoom'], res['pan'])
    rim = [q for c in cs for q in c['rim']]
    res['rim'] = None
    if len(rim) >= 3:
        fitted = circle(rim)
        if fitted:
            c0 = next(c for c in cs if c['rim'])
            res['rim'] = fitted + ((c0['cx'], c0['cy'], c0['r'], c0['h']),)
    return res


# ------------------------------------------------------------------ the report

def report(res, say=print):
    cur, cs = res['cursor'], res['cs']
    say(f'fit_map: {len(cs)} picked snapshots')
    if cur['rms'] is not None:
        say(f'  cursor   gain {cur["g"]:.4f} px per count at 1080p{"" if cur["g_seen"] else " (no mouse seen)"}; '
            f'stops at {cur["stop"]:.4f} h ({cur["stop"] * 1080:.1f} px at 1080p)'
            f'{"" if cur["stop_seen"] else " (not reached: assumed)"}; mouse up = cursor '
            f'{"up" if cur["ys"] < 0 else "down"}{"" if cur["ys_seen"] else " (assumed)"}; '
            f'rms {cur["rms"]:.1f} px over {cur["n"]}')
    if cur['start']:
        say(f'  start    the cursor at the centre on opening: within {cur["start"][0]:.1f} px '
            f'({cur["start"][1]} snapshots before any mouse)')
    for z in res['zoom']:
        lo, hi, sg, mu, rs, tau = z['Z']
        say(f'  zoom     mission {z["mis"]["index"]}: k0 {z["k0"]:.6f} h per m ({z["k0"] * 1080:.3f} px/m at 1080p), '
            f'x2 per level; levels {lo}{"" if z["lo_ok"] else " or lower"} .. {hi}{"" if z["hi_ok"] else " or higher"}; '
            f'wheel down = zoom {"out" if sg > 0 else "in"}; {"each notch" if mu == "each" else "one step per frame"};'
            f' {"resets" if rs else "kept"} on opening{"" if z["reopened"] else " (one open: assumed)"}; '
            f'rms {z["rms"]:.3f} log2 over {z["n"]}')
        say(f'  ease     tau {tau:.3f} s (90% in {tau * math.log(10):.2f} s)'
            f'{"" if z["moving"] else "; no snapshot within 0.5 s of a change: an upper bound only"}')
    pan = res['pan']
    if pan:
        e = pan['errs']
        what = {'none': 'no pan seen', 'A': f'rule A: {pan["a"]:.3f} px of pan per px pushed past the stop',
                'B': f'rule B: {pan["v"]:.1f} px/s while the cursor sits at the stop',
                'A+B': f'A+B: {pan["a"]:.3f} px per px pushed and {pan["v"]:.1f} px/s at the stop'}[pan['rule']]
        say(f'  pan      {what}; rms px: ' + ', '.join(f'{k} {v:.1f}' for k, v in e.items())
            + ('' if pan['pushed'] or pan['parked'] else ' (the cursor never reached the stop)'))
        if pan['start']:
            say(f'  reopen   before any push the map sits {max(pan["start"]):.1f} m from the open model '
                f'({len(pan["start"])} snapshots; ~0 = the pan resets)')
    ro = res['readout']
    if ro:
        b = ro['bearing'][ro['from']]
        say(f'  readout  measures from {ro["from"]}{"" if b is None else f" (bearing off {b:.0f} deg)"}; '
            f'rms m: ' + ', '.join(f'{k} {v:.1f}' for k, v in ro['errs'].items()) + f' over {ro["n"]}')
    if res['rim']:
        x, y, r, (cx, cy, r0, h) = res['rim']
        say(f'  rim      centre {x:.1f}, {y:.1f} (log {cx:.1f}, {cy:.1f}), radius {r:.1f} (log {r0:.1f}): '
            f'{x / h:.4f}, {y / h:.4f}, {r / h:.4f} of the screen height')
    say('  per snapshot (t since open, level, scale obs/model, cursor off px, points off px):')
    by_mis = {id(z['mis']): z for z in res['zoom']}
    for c in cs:
        zm = by_mis.get(id(c['mis']))
        if zm is None:
            continue
        L = level(c, c['t'], zm['Z'])[0]
        P, k = pan_at(c, cur, zm, pan)
        sc = f'{c["scale"] / (zm["k0"] * 2 ** L):.3f}' if c.get('scale') else '  -  '
        x, y, _, _ = cursor_run(c, cur['g'], cur['stop'], cur['ys'])
        co = f'{math.hypot(x - c["cursor"][0], y - c["cursor"][1]):5.1f}' if c['cursor'] else '   - '
        po = [math.hypot(c['cx'] + k * (wx - P[0]) - sx, c['cy'] + k * (wy - P[1]) - sy)
              for wx, wy, sx, sy, _ in c['points']]
        say(f'    snap {c["n"]:3d}  {c["t"] - c["op"]["t"]:5.2f} s  lv {L:+.2f}  {sc}  {co}  '
            + (' '.join(f'{v:.1f}' for v in po) or '-'))
    say('constants:')
    say(f'  cursor_gain = {cur["g"]:.4f}   CURSOR_STOP = {cur["stop"]:.4f}   CURSOR_Y = {cur["ys"]:+d}')
    for z in res['zoom']:
        lo, hi, sg, mu, rs, tau = z['Z']
        say(f'  mission {z["mis"]["index"]}: K0 = {z["k0"]:.6f}   LO = {lo}   HI = {hi}   WHEEL = {sg:+d}   '
            f'EASE = {tau:.3f}   RESET = {str(rs).lower()}')
    if pan:
        say(f'  PAN = \'{pan["rule"]}\'   PAN_A = {pan["a"]:.3f}   PAN_V = {pan["v"]:.1f}')
    if ro:
        say(f'  READOUT = \'{ro["from"]}\'')


def draw(res, shots, out, say=print):
    sys.path.insert(0, os.path.join(HERE, '_pylib'))
    from PIL import Image, ImageDraw
    os.makedirs(out, exist_ok=True)
    cur, by_mis = res['cursor'], {id(z['mis']): z for z in res['zoom']}
    for c in res['cs']:
        shot, zm = c['pick'].get('shot'), by_mis.get(id(c['mis']))
        if not shot or zm is None:
            continue
        path = os.path.join(shots, shot)
        if not os.path.isfile(path):
            say(f'  draw: {path} not found')
            continue
        im = Image.open(path).convert('RGB')
        W, H = im.size
        fx, fy = W / c['w'], H / c['h']
        img = lambda x, y: (x * fx, (c['h'] - y) * fy)  # noqa: E731
        d = ImageDraw.Draw(im)
        P, k = pan_at(c, cur, zm, res['pan'])
        sn = c['sn']
        spots = [(r['x'], r['y']) for kind in ('loot', 'mark') for r in sn[kind].values()]
        for wx, wy in spots:
            x, y = img(c['cx'] + k * (wx - P[0]), c['cy'] + k * (wy - P[1]))
            d.rectangle([x - 4, y - 4, x + 4, y + 4], outline=(0, 255, 255))
        if sn['me']:
            x, y = img(c['cx'] + k * (sn['me']['x'] - P[0]), c['cy'] + k * (sn['me']['y'] - P[1]))
            d.ellipse([x - 9, y - 9, x + 9, y + 9], outline=(255, 64, 255), width=2)
        x, y = img(*cursor_run(c, cur['g'], cur['stop'], cur['ys'])[:2])
        d.line([x - 8, y, x + 8, y], fill=(0, 255, 0), width=2)
        d.line([x, y - 8, x, y + 8], fill=(0, 255, 0), width=2)
        for q in [p[2:4] for p in c['points']] + ([c['cursor']] if c['cursor'] else []):
            x, y = img(*q)
            d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(255, 0, 0))
        x, y = img(c['cx'], c['cy'])
        m = (c['r'] + 40) * fy
        box = [int(max(0, x - m)), int(max(0, y - m)), int(min(W, x + m)), int(min(H, y + m))]
        crop = im.crop(box)
        crop = crop.resize((crop.width * 2, crop.height * 2), Image.LANCZOS)
        dst = os.path.join(out, f'fit_snap{c["n"]:03d}.png')
        crop.save(dst)
        say(f'  draw: {dst}')


# ------------------------------------------------------------------ the self-test

TRUTHS = [
    {'name': 'rule A, readout from the view centre', 'g': 0.23, 'stop': 0.183, 'ys': -1, 'k0': 0.001375,
     'Z': (-1, 1, 1, 'each', True, 0.12), 'a': 0.8, 'v': 0.0, 'rule': 'A', 'readout': 'centre', 'seed': 8},
    {'name': 'rule B, readout from me, levels -2..1', 'g': 0.18, 'stop': 0.180, 'ys': -1, 'k0': 0.0012,
     'Z': (-2, 1, 1, 'each', True, 0.25), 'a': 0.0, 'v': 90.0, 'rule': 'B', 'readout': 'me', 'seed': 9},
]


def synth(sess, T):
    """Picks for every snapshot with the map open, made from the truth T, with ±0.5 px of noise."""
    rnd = random.Random(T['seed'])
    picks = []
    for n in sorted(sess['snaps']):
        sn = sess['snaps'][n]
        c = context(sn)
        if c is None or not sn['me']:
            continue
        h, cx, cy, r = c['h'], c['cx'], c['cy'], c['r']
        x, y, pushes, segs = cursor_run(c, T['g'], T['stop'], T['ys'])
        kf = lambda t: T['k0'] * h * 2 ** level(c, t, T['Z'])[0]  # noqa: E731
        U, W = pan_basis(c, pushes, segs, kf)
        P = (T['a'] * U[0] + T['v'] * W[0], T['a'] * U[1] + T['v'] * W[1])
        k = kf(c['t'])
        spot = lambda wx, wy: (cx + k * (wx - P[0]), cy + k * (wy - P[1]))  # noqa: E731
        img = lambda q: [round(q[0] + rnd.uniform(-0.5, 0.5), 1), round(h - q[1] + rnd.uniform(-0.5, 0.5), 1)]  # noqa
        seen = lambda q: math.hypot(q[0] - cx, q[1] - cy) < r - 4  # noqa: E731
        pk = {'snap': n, 'shot': f'synthetic_{n}.png', 'cursor': img((x, y))}
        me = spot(sn['me']['x'], sn['me']['y'])
        if seen(me):
            pk['me'] = img(me)
        for kind in ('loot', 'mark'):
            got = {str(i): img(spot(q['x'], q['y'])) for i, q in sn[kind].items() if seen(spot(q['x'], q['y']))}
            if got:
                pk[kind] = got
        wx, wy = P[0] + (x - cx) / k, P[1] + (y - cy) / k
        ox, oy = {'me': (sn['me']['x'], sn['me']['y']), 'origin': (0.0, 0.0), 'centre': P}[T['readout']]
        pk['readout'] = [round(math.hypot(wx - ox, wy - oy)), round(math.degrees(math.atan2(wx - ox, wy - oy)) % 360)]
        if not picks:
            pk['rim'] = [img((cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))))
                         for a in (200, 95, 340, 260)]
        picks.append(pk)
    return {'picks': picks}


def selftest(path):
    if not os.path.isfile(path):
        print(f'fit_map selftest: {path} is missing; run python -I -B src/sim/sim.py measure (from dev) first')
        return 1
    sess = parse(path)[-1]
    fails = 0
    for T in TRUTHS:
        lines = []
        res = fit(sess, synth(sess, T), say=lines.append)
        report(res, say=lines.append)
        cur, z, pan, ro = res['cursor'], (res['zoom'] or [None])[0], res['pan'], res['readout']
        checks = [
            ('gain', abs(cur['g'] - T['g']) < 0.003, f'{cur["g"]:.4f} vs {T["g"]}'),
            ('stop', abs(cur['stop'] - T['stop']) < 0.002, f'{cur["stop"]:.4f} vs {T["stop"]}'),
            ('y sign', cur['ys'] == T['ys'], f'{cur["ys"]} vs {T["ys"]}'),
            ('levels', z is not None and z['Z'][:5] == T['Z'][:5], f'{z and z["Z"][:5]} vs {T["Z"][:5]}'),
            ('k0', z is not None and abs(z['k0'] / T['k0'] - 1) < 0.01, f'{z and round(z["k0"], 7)} vs {T["k0"]}'),
            ('ease', z is not None and abs(z['Z'][5] - T['Z'][5]) < 0.02, f'{z and z["Z"][5]:.4f} vs {T["Z"][5]}'),
            ('pan rule', pan is not None and pan['rule'] == T['rule'], f'{pan and pan["rule"]} vs {T["rule"]}'),
            ('pan size', pan is not None and abs(pan['a'] - T['a']) <= 0.1 * T['a'] + 1e-9
             and abs(pan['v'] - T['v']) <= 0.1 * T['v'] + 1e-9, f'{pan and (round(pan["a"], 3), round(pan["v"], 1))}'
             f' vs {(T["a"], T["v"])}'),
            ('readout', ro is not None and ro['from'] == T['readout'], f'{ro and ro["from"]} vs {T["readout"]}'),
            ('rim', res['rim'] is not None and math.hypot(res['rim'][0] - res['rim'][3][0], res['rim'][1] -
                                                          res['rim'][3][1]) < 1 and abs(res['rim'][2] -
                                                                                         res['rim'][3][2]) < 1,
             f'{res["rim"] and tuple(round(v, 1) for v in res["rim"][:3])}'),
        ]
        bad = [c for c in checks if not c[1]]
        fails += len(bad)
        print(f'truth: {T["name"]}: {len(checks) - len(bad)}/{len(checks)} checks pass')
        for name, ok, what in checks:
            print(f'  {"ok  " if ok else "FAIL"} {name}: {what}')
        if bad:
            print('\n'.join('    | ' + s for s in lines))
    print(f'fit_map selftest: {"PASS" if not fails else "FAIL"} ({path})')
    return 1 if fails else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='the game map\'s constants from a measuring mission')
    ap.add_argument('--log', help=f'the measure log (default %%LOCALAPPDATA%%\\{FILE})')
    ap.add_argument('--picks', help='the picks file (JSON)')
    ap.add_argument('--session', type=int, help='which session of the log (1 = the first; default the last)')
    ap.add_argument('--draw', metavar='OUT', help='put the fitted spots on the picked screenshots, into OUT')
    ap.add_argument('--shots', metavar='DIR', help='where the screenshots are (with --draw)')
    ap.add_argument('--selftest', nargs='?', const=SIM_LOG, metavar='LOG', help='check the fit on the sim\'s log')
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest(a.selftest)
    if not a.picks:
        ap.error('--picks is needed (or --selftest)')
    log = a.log or os.path.join(os.environ.get('LOCALAPPDATA', ''), FILE)
    sessions = parse(log)
    if not sessions:
        print(f'fit_map: no session in {log}')
        return 1
    with open(a.picks, encoding='utf-8') as f:
        picks = json.load(f)
    pick = a.session or picks.get('session') or len(sessions)
    if not 1 <= pick <= len(sessions):
        print(f'fit_map: session {pick} of {len(sessions)}?')
        return 1
    sess = sessions[pick - 1]
    print(f'fit_map: {log}, session {pick} of {len(sessions)}: {sess["head"]}; {len(sess["missions"])} missions, '
          f'{len(sess["snaps"])} snapshots')
    res = fit(sess, picks)
    report(res)
    if a.draw:
        draw(res, a.shots or os.path.dirname(os.path.abspath(a.picks)), a.draw)
    return 0


if __name__ == '__main__':
    sys.exit(main())
