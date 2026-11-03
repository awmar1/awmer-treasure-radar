r"""0.8's map overlay (view.lua, overlay.lua, legend.lua) over the player's own Tab-map screenshots: the world of
dev/docs/mock_0.8_map_detail.png (snapshot 3: a small map, three zoom levels), checked against the map model the 0.8
measuring runs fitted (CONTRACT.md "0.9": k = 0.7805 / 1.4766 / 2.953 px/m at 1080p for zoom -1 / 0 / +1).

  python -I dev/src/sim/sim.py map08_out     zoom -1 (the mock): the whole map on the origin: clusters, badges, rings,
                                             legend
  python -I dev/src/sim/sim.py map08         zoom 0, a stand-in companion fixing the view on the origin (the
                                             snapshot's view: COMPANION_INTERFACE.md)
  python -I dev/src/sim/sim.py map08_in      zoom +1, the same

The waypoint (Numpad 1, aimed at the credit pile before the map opens) is on the credit cluster, 97 m away. The
backdrops are the player's screenshots, read only (when they're missing the sim warns and draws its ground instead;
the checks still run). The 'backdrop' and 'checks' keys: scenarios/base.py. 0.8.1-0.8.3's pans, hover and skid cases
went with the cursor model (dev/src/retired/sim-0.8.3/scenarios/map08.py); map09.py has 0.9's.
Helpers for map09.py: at, lua_list, check_view, model, companion (a stand-in screen reader), the world (UNITS ...).
"""
import math
import os

SHOTS = os.environ.get('TREASURE_RADAR_SHOTS', '')   # a folder of these game screenshots; without it, the drawn ground
SHOT = {-1: '20261026103354_1.jpg', 0: '20261026103347_1.jpg', 1: '20261026103357_1.jpg'}

ME = (42.0, -1.0)                  # the camera (Treasure Radar's own position); the game's player dot is at (40.1, 0.7)
FACING = 322.9
LOOT = [('credit', -21, 73, 1), ('medal', -20, 74, 1), ('ammo', -20, 75, 3), ('ammo', -56, -44, 3),
        ('grenade', -57, -44, 1), ('medal', 153, -9, 1), ('credit', 165, 77, 1), ('medal', 201, 12, 1),
        ('common', -124, 19, 1), ('common', -119, 12, 1), ('common', 87, 158, 1)]
NESTS = [('small', -118, -11), ('small', -117, 44), ('medium', -173, 30), ('medium', 97, 173), ('small', 105, -185)]
OBJECTIVES = [(87, 166), (85, 189)]        # the oil pumps (an objective kind stands in)

UNITS = [(k, x, y, 0) for (k, x, y, n) in LOOT for _ in range(n)]
UNITS += [('bug_hole_' + size, x, y, 0) for (size, x, y) in NESTS]
UNITS += [('egg_sack', x, y, 0) for (x, y) in OBJECTIVES]

# aimed at the credit pile (the assist aims 0.3 m over a pile), then turned the way the screenshot faces
_dx, _dy = LOOT[0][1] - ME[0], LOOT[0][2] - ME[1]
AIM_YAW = math.degrees(math.atan2(_dx, _dy)) % 360
AIM_PITCH = math.degrees(math.atan2(0.3 - 1.6, math.hypot(_dx, _dy)))
CAMERA = [(0, ME[0], ME[1], 1.6, AIM_YAW, AIM_PITCH), (1.2, ME[0], ME[1], 1.6, AIM_YAW, AIM_PITCH),
          (1.6, ME[0], ME[1], 1.6, FACING, -6)]

# the measured model, top-left origin (the screenshots' pixels)
CX, CY, RIM = 1674.0, 819.5, 222.0
KL = {-1: 0.7805, 0: 1.4766, 1: 2.953}             # px per m at 1080p (-1: a small map's whole map)
KW = {'small': 0.7805, 'big': 0.554}               # -1: the whole map, by the map's size class
R_MAP = 285.3
H1 = {'me': (40.1, 0.7), 'nest_s1': (-118, -11), 'nest_s2': (-117, 43), 'pump1': (87, 166), 'nest_m1': (97, 173),
      'nest_s3': (105, -185), 'pump2': (85, 189), 'nest_m2': (-173, 30)}
# the mock's clusters at zoom -1: (top kind, badge, x, y)
MOCK = [('credit', '+2', 1660, 764), ('credit', None, 1798, 762), ('medal', None, 1789, 826),
        ('medal', None, 1824, 810), ('common', '2', 1585, 807), ('common', None, 1740, 702), ('ammo', '+1', 1633, 852)]
RINGS = {-1: 4, 0: 2, 1: 0}                # nest rings drawn (inside the circle, not beside a pump)
RANK = ['super', 'rare', 'credit', 'medal', 'common', 'requisition', 'ammo', 'grenade', 'stim']
TOP_RING = 2920                            # overlay.lua's ring layer (chef.TOP + 920)


def model(x, y, level, view=(0.0, 0.0)):
    k = KL[level]
    return CX + (x - view[0]) * k, CY - (y - view[1]) * k


def badge(c):
    if c.mixed:
        return '+%d' % (c.piles - 1)
    return str(int(c.total)) if c.total > 1 else None


def lua_list(t, n=None):
    n = len(t) if n is None else int(n)
    return [t[i] for i in range(1, n + 1)]


def check_view(sim, level, view=(0.0, 0.0), rings=None, mock=True):
    """the model, the clusters, the rings and the legend at this zoom level, the view centred on `view` (m)"""
    out = []
    T = sim.G.T
    VW, S, P = T.mod.view, T.mod.main.S, T.mod.pings
    h = sim.h
    out.append((bool(VW.open and VW.trusted), 'open %s, trusted %s' % (VW.open, VW.trusted)))
    out.append((VW.level == level, 'level %s (want %d)' % (VW.level, level)))
    k = KL[level]
    out.append((abs(VW.k - k) < 1e-3, 'k %.4f px/m (want %.4f)' % (VW.k, k)))
    # the model points (check_h1) inside the circle
    for tag, (x, y) in H1.items():
        mx, my = model(x, y, level, view)
        if math.hypot(mx - CX, my - CY) > RIM:
            continue
        sx, sy = VW.to_screen(x, y)
        e = math.hypot(sx - mx, (h - sy) - my)
        out.append((e <= 3, 'model %-8s zoom %+d: (%.1f, %.1f) vs (%.1f, %.1f), %.2f px' % (
            tag, level, sx, h - sy, mx, my, e)))
    # every cluster sits at its piles' mean model spot
    clusters = lua_list(VW.clusters, VW.n)
    for c in clusters:
        piles = lua_list(c.marks, c.piles)
        spots = [model(m.x, m.y, level, view) for m in piles]
        mx, my = sum(p[0] for p in spots) / len(spots), sum(p[1] for p in spots) / len(spots)
        e = math.hypot(c.sx - mx, (h - c.sy) - my)
        out.append((e <= 2, 'cluster %-7s %-3s at (%.1f, %.1f), model (%.1f, %.1f), %.2f px' % (
            c.kind.id, badge(c) or '', c.sx, h - c.sy, mx, my, e)))
    if level == -1 and mock:
        out.append((len(clusters) == len(MOCK), '%d clusters (the mock: %d)' % (len(clusters), len(MOCK))))
        for kind, b, x, y in MOCK:
            # the mock's spots were drawn at 0.8's first guess (0.7425 px/m about 1675.0, 819.0): scaled to the
            # measured model, they're where the clusters are now
            f = KL[-1] / 0.7425
            mx, my = CX + (x - 1675.0) * f, CY + (y - 819.0) * f
            hit = [c for c in clusters if c.kind.id == kind and badge(c) == b and
                   abs(c.sx - mx) <= 2 and abs((h - c.sy) - my) <= 2]
            out.append((len(hit) == 1, 'mock cluster %s %s at (%d, %d): %s' % (
                kind, b or '-', x, y, 'found' if hit else 'MISSING')))
    # nest rings (the pump hides nest_m1 at zoom -1)
    draws = sim.SIM.draws
    rings_n = sum(1 for i in range(1, len(draws) + 1)
                if draws[i].op == 'bitmap' and draws[i].layer == TOP_RING and str(draws[i].tex).startswith('ov/nest'))
    want = RINGS[level] if rings is None else rings
    out.append((rings_n == want, '%d nest rings (want %d)' % (rings_n, want)))
    # the legend's rows: value order, then the nests
    L = VW.legend
    ids = [r.kind.id for r in lua_list(L)]
    out.append((ids == [k for k in RANK if k in ids], 'legend rows %s' % ','.join(ids)))
    out.append((L.nests[2] == len(NESTS), 'legend nests %s/%s' % (L.nests[1], L.nests[2])))
    return out


def check_waypoint(sim, want):
    T = sim.G.T
    VW, S, P = T.mod.view, T.mod.main.S, T.mod.pings
    W = lua_list(P.waypoints)
    if not want:
        return [(len(W) == 0, '%d waypoints (want none)' % len(W))]
    out = [(len(W) == 1 and W[0].kind.id == 'credit', 'waypoint %s' % (W[0].kind.id if W else None))]
    if W:
        d = math.hypot(W[0].x - S.me.x, W[0].y - S.me.y)
        out.append((round(d) == 97, 'waypoint %.1f m away (want 97)' % d))
    if not W:
        return out
    # on the map: its cluster holds it; off the map (zoom +1): the cyan chevron at the rim instead
    sx, sy = VW.to_screen(W[0].x, W[0].y)
    wp = [c for c in lua_list(VW.clusters, VW.n) if c.wp]
    draws = sim.SIM.draws
    chev = sum(1 for i in range(1, len(draws) + 1)
               if draws[i].op == 'bitmap' and str(draws[i].tex).startswith('ov/chev'))
    if VW.inside(sx, sy, 2 * sim.h / 1080):
        out.append((len(wp) == 1 and wp[0].kind.id == 'credit' and wp[0].piles == 3 and chev == 0,
                    'the waypoint cluster: %s, %d chevrons' % (wp[0].kind.id if wp else None, chev)))
    else:
        out.append((not wp and chev == 1, 'the waypoint off the map: %d clusters hold it, %d chevrons (want 0, 1)' % (
            len(wp), chev)))
    return out




# ------------------------------------------------------------------ the companion's stand-in
GAIN = {-1: 0.269, 0: 0.246, 1: 0.123}        # m the game's view centre moves per raw count (COMPANION_INTERFACE.md)
KZ1080 = {0: 1.4766, 1: 2.953}


def at(f):
    """a time just before frame f (the sim's frames are at f / 60 s)"""
    return f / 60 - 1e-3


def companion(v0=(0.0, 0.0), game_level=None, start=0, every=2, lag=2, how=None, until=None, whole=None, poll=1):
    """a stand-in for the screen reader (dev/docs/COMPANION_INTERFACE.md, with the coordinator's 0.9 additions). The
    game's side: its zoom level at a frame (game_level(frame); default the mod's, and nothing while the mod's is ?), and
    its view centre V: v0 at each open, then moved by the counts the mod reports (the game got the same ones) at the
    game level's gain. It reads the mod line every `poll` frames and moves V by the cmx, cmy deltas between the lines it
    read (so it loses no counts of the lines it missed). It idles on open=0 only: with level=? or kz=0 it still captures
    and answers with the level it measures from the grid. Every `every` frames from `start` (until `until`) it captures:
    the seq then current, V then, the level and its grid cell; it publishes that fix `lag` frames later (its processing
    time). At -1 on a map whose class is ? the cell isn't one it knows: level ?, cell 0. how(frame): 'dot' (the
    default), 'grid' or 'none'. whole: the V it reports at level -1 (default the origin, the whole map's).
    fn.truth[frame] = (V, the game's level); fn.fixes = [(frame, fix)] written."""
    st = {'v': None, 'seq': None, 'cm': None, 'pending': []}
    truth, fixes = {}, []

    def fn(sim, frame, f):
        if not f or frame % poll:
            return None
        new = f.get('seq') != st['seq']
        st['seq'] = f.get('seq')
        if f.get('open') != '1':
            st['v'], st['cm'], st['pending'] = None, None, []
            return None
        if game_level:
            lvl = game_level(frame)
        else:
            lvl = int(f['level']) if f.get('level') != '?' else None
        cm = (int(f['cmx']), int(f['cmy']))
        if new:
            if st['v'] is None:
                st['v'] = v0
            elif lvl is not None:
                g = GAIN[lvl]
                dx, dy = cm[0] - st['cm'][0], cm[1] - st['cm'][1]
                st['v'] = (st['v'][0] + dx * g, st['v'][1] - dy * g)
            st['cm'] = cm
        truth[frame] = (st['v'], lvl)
        if lvl is not None and frame >= start and (until is None or frame < until) and (frame - start) % every == 0:
            h = int(f['h'])
            if lvl == -1:
                k = KW.get(f.get('class'), 0)
                v = whole or (0.0, 0.0)
            else:
                k = KZ1080[lvl]
                v = st['v']
            hw = how(frame) if how else 'dot'
            fix = {'seq': f['seq'], 'ts': '%.3f' % (1761550000 + frame / 60), 'how': hw}
            if hw != 'none':
                fix.update({'vx': '%.1f' % v[0], 'vy': '%.1f' % v[1], 'err': '0.5'})
            if k:
                fix.update({'level': '%d' % lvl, 'cell': '%.1f' % (65 * k * h / 1080)})
            else:
                fix.update({'level': '?', 'cell': '0'})
            st['pending'].append((frame + lag, fix))
        out = None
        while st['pending'] and st['pending'][0][0] <= frame:
            out = st['pending'].pop(0)[1]
        if out is not None:
            fixes.append((frame, out))
        return out

    fn.truth, fn.fixes = truth, fixes
    return fn


def zoom_scn(level, about):
    frames = 280
    scn = {
        'about': about,
        'frames': frames, 'render': [frames - 4],
        'defaults': True, 'options': {},
        'backdrop': os.path.join(SHOTS, SHOT[level]),
        'camera': CAMERA,
        'units': UNITS,
        'press': [(1.0, 'numpad 1')],
        'map_open': [(3.6, 99)],                  # after Numpad 1's toast
        'wheel': [(4.0, level)] if level else [],
        'checks': lambda sim, f: check_view(sim, level) + check_waypoint(sim, True),
    }
    if level != -1:
        # 0.9: at 0 and +1 the view is the game cursor's: the snapshot's is on the origin, as a companion would find it
        scn['companion'] = companion((0.0, 0.0))
    return scn


SCENARIOS = {
    'map08_out': zoom_scn(-1, '0.8 overlay over snapshot 3 at zoom -1 (the mock): clusters, badges, rings, legend'),
    'map08': zoom_scn(0, '0.8 overlay over snapshot 3 at zoom 0, a companion fix on the origin'),
    'map08_in': zoom_scn(1, '0.8 overlay over snapshot 3 at zoom +1, a companion fix on the origin'),
}
