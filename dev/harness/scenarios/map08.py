"""0.9: the map overlay through the real loader, in the world of dev/docs/mock_0.8_map_detail.png (snapshot 3), against
the 0.9 map model (1080p, HUD Scale 0.9): three levels on every map. -1 is the whole map centred on the world origin at
rim / R_map px per m (0.7805 on this small map: about 4000 units), 0 and +1 (1.4766, 2.953) are centred on the game's
map cursor, which no Lua can read: there the world icons draw only around a fresh fix of the screen-reading companion
(dev/docs/COMPANION_INTERFACE.md). This run has no companion, so 0 and +1 show the legend (and the compass) only. A
mission starts at 0, the level is kept across closes, the wheel stops at both ends, and a frame with two notches may
have zoomed once (the level not known until an end). As in the real game, two more worlds are there from the mission's
start, so the Map key (Tab) opens the map.

I stand at 42, -1 and set a waypoint on the credit pile (numpad 1). Then:
  open 1   zoom 0: the legend only; in to +1, in again (the end: still +1), the mouse west: nothing world-anchored;
           out to 0 and -1: the whole map on the origin, the clusters at the model's spots and scale; closed
  open 2   still -1; out again (the end: still -1); two notches in one frame (0..+1: not known, nothing); one more in
           (+1 for sure, nothing without a fix); closed
  open 3   still +1 (nothing); out twice: -1, the whole map again; closed: nothing left.
The mod line (%LOCALAPPDATA%\\Temp\\treasure_radar_mod.txt) is written every frame while open and once with open=0 at
each close (and its paths are logged once).
The overlay (TOP + 920-929 and 940-949) and the legend (TOP + 930-939) land in the top world at their layer - 1000.

Run:  python -I dev/harness/run.py --mod dev/build/Treasure-Radar-0.9.2 --scenario map08 --options core
"""
import math
import os
import re

FPS = 30
ME = (42.0, -1.0)
LOOT = [('credit', -21, 73, 1), ('medal', -20, 74, 1), ('ammo', -20, 75, 3), ('ammo', -56, -44, 3),
        ('grenade', -57, -44, 1), ('medal', 153, -9, 1), ('credit', 165, 77, 1), ('medal', 201, 12, 1),
        ('common', -124, 19, 1), ('common', -119, 12, 1), ('common', 87, 158, 1)]
NESTS = [('bug_hole_small', -118, -11), ('bug_hole_small', -117, 44), ('bug_hole_medium', -173, 30),
         ('bug_hole_medium', 97, 173), ('bug_hole_small', 105, -185)]
PUMPS = [(87, 166), (85, 189)]
AMMO = (-56.5, -44.0)              # the ammo cluster's mean (ammo and grenade), in metres
WORLD_V = (-20.33 - AMMO[0], 74.0 - AMMO[1])   # to the credit cluster's mean (three piles)
OVERLAY, LEGEND, WORLDLY = (1920, 1949), (1930, 1939), ((1920, 1929), (1940, 1949))
L_ICON = (1923, 1923)

# the 0.9 map model (a small map)
KL = {-1: 0.7805, 0: 1.4766, 1: 2.953}
CENTRE = (1674.0, 260.5)


def build(s):
    s.screen(1920, 1080).run(seconds=17, fps=FPS)
    s.hud(scale=0.9)                         # the measuring run's
    s.world('mission', at=0.0, filler=4000, spread=400, seed=5)
    s.world('hud_a', at=0.0, main=False)
    s.world('hud_b', at=0.0, main=False)

    # structures (ids from dev/src/addon/structures.lua); an objective kind stands in for the oil pumps
    s.kind('bug_hole_small', '2e454bd4d24eb04a', group='nest')
    s.kind('bug_hole_medium', 'a83587cbff25c79e', group='nest')
    s.kind('egg_sack', '06d3c4720e642fc1', group='objective')
    for kind, x, y, n in LOOT:
        for _ in range(n):
            s.unit(kind, x, y)
    for kind, x, y in NESTS:
        s.unit(kind, x, y)
    for x, y in PUMPS:
        s.unit('egg_sack', x, y)

    dx, dy = LOOT[0][1] - ME[0], LOOT[0][2] - ME[1]
    yaw = math.degrees(math.atan2(dx, dy)) % 360
    pitch = math.degrees(math.atan2(0.3 - 1.8, math.hypot(dx, dy)))
    s.camera(0.0, ME[0], ME[1], 1.8, yaw=yaw, pitch=pitch)
    s.camera(4.0, ME[0], ME[1], 1.8, yaw=yaw, pitch=pitch)
    s.camera(4.5, ME[0], ME[1], 1.8, yaw=322.9, pitch=-6)
    s.camera(17.0, ME[0], ME[1], 1.8, yaw=322.9, pitch=-6)

    s.press('numpad 1', 3.6)     # the waypoint on the credit pile (the mission world settles at 3.2 s)
    # open 1
    s.press('tab', 5.0)          # zoom 0 (a mission starts there)
    s.wheel(6.0, 1)              # +1
    s.wheel(6.3, 1)              # the end: still +1
    s.raw_mouse(6.62, 6.98, -15)  # west (the game's view moves; the mod can't see where to)
    s.wheel(7.5, -1)             # 0
    s.wheel(7.9, -1)             # -1: the whole map (past view.lua's BUSY after the last step)
    s.press('tab', 8.5)
    # open 2
    s.press('tab', 9.5)          # still -1
    s.wheel(10.2, -1)            # the end: still -1
    s.wheel(11.0, 2)             # two notches in one frame: 0 or +1
    s.wheel(11.8, 1)             # +1 for sure
    s.press('tab', 12.3)
    # open 3
    s.press('tab', 12.8)         # still +1
    s.wheel(13.6, -1)            # 0
    s.wheel(14.0, -1)            # -1
    s.press('tab', 16.0)
    s.render_frames('4.5s', '5.8s', '6.5s', '6.8s', '8.2s', '9.0s', '10.0s', '10.6s', '11.5s', '12.1s', '13.3s',
                    '14.8s', '16.5s')

    def centres(r, frame, name):
        icons = [d[1] for d in r.draws_of(frame, world='top', layer=L_ICON, kind='bitmap')]
        names = r.tex_names or {}
        return [(x + w / 2, y + h / 2) for (_, _, x, y, w, h, _, tex, *_rest) in icons
                if names.get(tex, tex) == name]

    def n_icons(r, frame):
        return len(r.draws_of(frame, world='top', layer=L_ICON, kind='bitmap'))

    def at(frame):
        """The ammo cluster's icon where the model puts it at -1: the whole map on the origin."""
        def fn(r):
            ammo = centres(r, frame, 'icons/ammo')
            if len(ammo) != 1:
                return False, 'icons at %s: %d ammo (of %d)' % (frame, len(ammo), n_icons(r, frame))
            k = KL[-1]
            want = (CENTRE[0] + AMMO[0] * k, CENTRE[1] + AMMO[1] * k)
            e = math.hypot(ammo[0][0] - want[0], ammo[0][1] - want[1])
            return e <= 1.5, 'ammo icon at %s: (%.1f, %.1f), the model (%.1f, %.1f): %.2f px off' % (
                frame, ammo[0][0], ammo[0][1], want[0], want[1], e)
        return fn

    def spacing(frame):
        def fn(r):
            ammo, credit = centres(r, frame, 'icons/ammo'), centres(r, frame, 'icons/credit')
            if len(ammo) != 1 or not credit:
                return False, 'icons at %s: %d ammo, %d credit' % (frame, len(ammo), len(credit))
            a = ammo[0]
            c = min(credit, key=lambda p: (p[0] - a[0]) ** 2 + (p[1] - a[1]) ** 2)
            v = (c[0] - a[0], c[1] - a[1])
            k = KL[-1]
            want = (WORLD_V[0] * k, WORLD_V[1] * k)
            e = math.hypot(v[0] - want[0], v[1] - want[1])
            return e <= 1.5, 'ammo -> credit icon at %s: (%.1f, %.1f) px, the model (%.1f, %.1f): %.2f px off' % (
                frame, v[0], v[1], want[0], want[1], e)
        return fn

    def legend_only(frame):
        """0 / +1 without a companion fix: nothing world-anchored in the top world, the legend kept"""
        def fn(r):
            worldly = sum(r.count(frame, world='top', layer=l) for l in WORLDLY)
            legend = r.count(frame, world='top', layer=LEGEND)
            return worldly == 0 and legend > 0, 'at %s: world-anchored draws %d, legend %d' % (frame, worldly, legend)
        return fn

    def whole(frame):
        """-1: the overlay (icons, rings) drawn, the legend kept"""
        def fn(r):
            over = r.count(frame, world='top', layer=(1920, 1929))
            legend = r.count(frame, world='top', layer=LEGEND)
            return over > 0 and legend > 0, 'at %s: overlay %d, legend %d' % (frame, over, legend)
        return fn

    def gone(frame):
        return lambda r: (r.count(frame, world='top', layer=OVERLAY) == 0,
                          'top-world draws at 1920-1949: %s' % r.count(frame, world='top', layer=OVERLAY))

    def compass(frame):
        return lambda r: (r.count(frame, world='main', layer=(951, 958)) > 0,
                          'compass draws at %s: %s' % (frame, r.count(frame, world='main', layer=(951, 958))))

    def mod_line(r):
        p = os.path.join(getattr(r, 'lad', '') or '', 'Temp', 'treasure_radar_mod.txt')
        try:
            text = open(p, encoding='utf-8').read()
        except OSError as e:
            return False, 'the mod line: %s' % e
        f = dict(kv.split('=', 1) for kv in text.split() if '=' in kv)
        ok = (text.endswith(' end\n') and f.get('open') == '0' and f.get('level') == '-1' and
              f.get('class') == 'small' and f.get('kz') == '0.7805' and f.get('cy') == '819.5' and
              f.get('rim') == '222.0' and 'cmx' in f and 'cmy' in f and int(f.get('seq', 0)) > 200)
        return ok, 'the last mod line: %s' % text.strip()

    s.check('a small map, logged once', lambda r: (
        len(r.log_lines(r'map: world \d+, \d+ units: a small map \(levels -1, 0, \+1; the whole map at 0\.7805')) == 1,
        '; '.join(r.log_lines(r'map: world')[:2])))
    s.check('nothing of the overlay with the map closed', gone('4.5s'))
    s.check('open 1, zoom 0: no fix, the legend only', legend_only('5.8s'))
    s.check('open 1, zoom 0: the compass stays', compass('5.8s'))
    s.check('open 1, zoom +1: the legend only', legend_only('6.5s'))
    s.check('open 1, in again: still +1 (the end), the legend only', legend_only('6.8s'))
    s.check('open 1, zoom -1: the whole map on the origin', at('8.2s'))
    s.check('open 1, zoom -1: the clusters at the model scale', spacing('8.2s'))
    s.check('open 1, zoom -1: the overlay and the legend', whole('8.2s'))
    s.check('the waypoint set on the credit pile (a Super Credit)', lambda r: (
        r.log_has(r'pings: waypoint SUPER CREDIT set \(aimed'), '; '.join(r.log_lines(r'pings: waypoint')[:2])))
    s.check('closed: nothing left', gone('9.0s'))
    s.check('open 2: still zoom -1', at('10.0s'))
    s.check('open 2, out again: still -1 (the end)', at('10.6s'))
    s.check('open 2, two notches in a frame: the level not known (0..1), the legend only', legend_only('11.5s'))
    s.check('the two-notch frame logged as not known', lambda r: (
        r.log_has(r'map: the level is not known \(0\.\.1\)$'), '; '.join(r.log_lines(r'map: the level')[:3])))
    s.check('open 2, one more in: +1 for sure, the legend only', legend_only('12.1s'))
    s.check('open 3: still +1, the legend only', legend_only('13.3s'))
    s.check('open 3, out twice: the whole map again', at('14.8s'))
    s.check('gone with the map', gone('16.5s'))
    s.check('the mod line: open=0 at the close, the geometry, cmx and cmy', mod_line)
    s.check('no companion: no fix lines', lambda r: (not r.log_has(r'companion: (fix|level)'),
                                                    '; '.join(r.log_lines(r'companion:')[:3])))
    s.check('the companion paths logged once', lambda r: (
        len(r.log_lines(r'companion: mod line -> ')) == 1 and
        r.log_has(r'companion: mod line -> .*LocalAppData\\Temp\\treasure_radar_mod\.txt, fix <- .*Temp\\treasure_radar_fix\.txt'),
        '; '.join(r.log_lines(r'companion: mod line')[:2])))
    # 0.9.1: 0.9.0's camprobe is gone; 0.9.3: 0.9.2's lineprobe too (retired: dev/src/retired/lineprobe-0.9.2.lua)
    s.check('no camprobe or lineprobe lines', lambda r: (not r.log_has(r'probe: '),
                                                        '; '.join(r.log_lines(r'probe: ')[:3])))
    s.check('every texture is in the build', lambda r: (not r.log_has(r'no texture named'),
                                                       '; '.join(r.log_lines(r'no texture named')[:4])))
    s.check('no frame errors', lambda r: not r.log_has(r'frame error'))
    s.check('no Lua errors', lambda r: (not r.log_has(r'\berror: |could not (start|compile)|switched off'),
                                        '; '.join(r.log_lines(r'\berror: ')[:3])))
    _ = re
