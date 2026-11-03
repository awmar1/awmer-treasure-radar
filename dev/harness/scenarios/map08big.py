"""0.9: a big map (about 14000 units: the census says big, 11001-24000) through the real loader. Three levels as on
every map: -1 is the whole map centred on the world origin at rim / R_map = 222 / 401 = 0.554 px per m (1080p), so a
medal 385 m out (213 px) is drawn just inside the rim (icons keep 6 px clear of it); 0 and +1 are centred on the game's
map cursor and, with no companion fix (none in this run), show the legend only. The wheel stops at both ends: three
more downs at -1 stay -1 (0.8.3 pinned the bottom at -3 after five; gone).

  Tab: 0 (the legend only); down: -1 (placed at 0.554 px/m); down twice more: still -1; up: 0; up: +1; Tab: closed.

Run:  python -I dev/harness/run.py --mod dev/build/Treasure-Radar-0.9.2 --scenario map08big --options core
"""
import math

FPS = 30
CENTRE = (1674.0, 260.5)
K_BIG = 0.554                      # px per m at -1 on a big map, 1080p
RIM = 222.0
AMMO = (-30.0, -20.0)
MEDAL = (385.0, 10.0)
LEGEND = (1930, 1939)
WORLDLY = ((1920, 1929), (1940, 1949))
L_ICON = (1923, 1923)


def build(s):
    s.screen(1920, 1080).run(seconds=13, fps=FPS)
    s.hud(scale=0.9)
    s.world('mission', at=0.0, filler=14000, spread=420, seed=9)
    s.world('hud_a', at=0.0, main=False)
    s.world('hud_b', at=0.0, main=False)
    s.unit('ammo', *AMMO)
    s.unit('credit', 25, 30)
    s.unit('medal', *MEDAL)           # 385 m out: inside a big map's 401 m
    for x, y in ((10, -50), (-40, 40), (50, -10)):
        s.unit('common', x, y)        # samples: the loader's sign of a mission
    s.camera(0.0, 0, 0, 1.8, yaw=0, pitch=-6)
    s.camera(13.0, 0, 0, 1.8, yaw=0, pitch=-6)

    s.press('tab', 5.5)          # zoom 0 (a mission starts there)
    s.wheel(6.5, -1)             # -1: the whole map
    s.wheel(7.3, -1)             # the end: still -1
    s.wheel(8.0, -1)             # still -1
    s.wheel(9.0, 1)              # 0
    s.wheel(9.6, 1)              # +1
    s.press('tab', 11.5)
    s.render_frames('6.1s', '7.0s', '7.7s', '8.7s', '9.4s', '10.1s', '12.0s')

    def icon_at(r, frame, name):
        names = r.tex_names or {}
        return [(x + w / 2, y + h / 2) for (_, _, x, y, w, h, _, tex, *_rest) in
                (d[1] for d in r.draws_of(frame, world='top', layer=L_ICON, kind='bitmap'))
                if names.get(tex, tex) == name]

    def placed(frame, name, at):
        def fn(r):
            got = icon_at(r, frame, name)
            if len(got) != 1:
                return False, '%d %s icons at %s' % (len(got), name, frame)
            want = (CENTRE[0] + at[0] * K_BIG, CENTRE[1] + at[1] * K_BIG)
            e = math.hypot(got[0][0] - want[0], got[0][1] - want[1])
            d = math.hypot(got[0][0] - CENTRE[0], got[0][1] - CENTRE[1])
            return e <= 1.5 and d <= RIM, '%s icon at %s: (%.1f, %.1f), the model (%.1f, %.1f): %.2f px off, ' \
                '%.1f px from the centre (rim %.0f)' % (name, frame, got[0][0], got[0][1], want[0], want[1], e, d, RIM)
        return fn

    def legend_only(frame):
        def fn(r):
            worldly = sum(r.count(frame, world='top', layer=l) for l in WORLDLY)
            legend = r.count(frame, world='top', layer=LEGEND)
            return worldly == 0 and legend > 0, 'at %s: world-anchored draws %d, legend %d' % (frame, worldly, legend)
        return fn

    s.check('a big map, logged once', lambda r: (
        len(r.log_lines(r'map: world \d+, \d+ units: a big map \(levels -1, 0, \+1; the whole map at 0\.5540 px/m '
                        r'at 1080p, R 401\.0 m\)')) == 1, '; '.join(r.log_lines(r'map: world')[:2])))
    s.check('zoom 0: no fix, the legend only', legend_only('6.1s'))
    s.check('zoom -1: the ammo at 0.554 px/m on the origin', placed('7.0s', 'icons/ammo', AMMO))
    s.check('zoom -1: the medal 385 m out inside the rim', placed('7.0s', 'icons/medal', MEDAL))
    s.check('down again: still -1 (the end)', placed('7.7s', 'icons/ammo', AMMO))
    s.check('down a third time: still -1', placed('8.7s', 'icons/medal', MEDAL))
    s.check('the notches at the end logged at -1', lambda r: (
        len(r.log_lines(r'map: notch -1 .*level -1\.\.-1 \(known\)')) == 3,
        '%d notch lines at -1' % len(r.log_lines(r'map: notch -1 .*level -1\.\.-1 \(known\)'))))
    s.check('up: 0, the legend only', legend_only('9.4s'))
    s.check('up: +1, the legend only', legend_only('10.1s'))
    s.check('gone with the map', lambda r: (r.count('12.0s', world='top', layer=(1920, 1949)) == 0,
                                            'top-world draws %s' % r.count('12.0s', world='top', layer=(1920, 1949))))
    s.check('no companion: no fix lines', lambda r: not r.log_has(r'companion: (fix|level)'))
    s.check('no frame errors', lambda r: not r.log_has(r'frame error'))
