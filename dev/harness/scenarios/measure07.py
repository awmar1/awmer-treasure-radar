"""0.7 measurement build (Ammar Treasure Radar Measure): the ship with the kind that crashed the game made fragile, then
a mission with two worlds there all along (as in the real game). F12 on the ship, F12 in the mission, Tab opens the
map: two notches in and one out, the mouse pushed right, F12, Tab closes it, F12. The logger may only read what the
mod already has: nothing may touch the fragile kind.

Run:  python -I dev/harness/run.py --mod dev/build/Treasure-Radar-0.7.0-measure --scenario measure07 --options core
"""


def build(s):
    s.screen(1920, 1080).run(seconds=15, fps=30)
    s.world('ship', at=0.0, until=3.0, filler=2250, spread=150, seed=5)
    s.kind('ship_fragile', '46cab355bd8d4d37', group='ship')
    s.fragile('ship_fragile')
    s.unit('ship_fragile', 1, 3, world='ship', label='the kind that crashed the game')

    s.world('mission', at=3.0, filler=6000, spread=450, seed=7)
    s.world('hud_a', at=3.0, main=False)
    s.world('hud_b', at=3.0, main=False)
    s.kind('fabricator', 'a57ae2a703c02899', group='structure')
    s.kind('bug_hole_medium', 'a83587cbff25c79e', group='nest')
    s.unit('fabricator', -40, -30)
    s.unit('bug_hole_medium', -50, 60)
    s.unit('medal', 6, 28)
    s.unit('rare', 25, 10)
    s.ring('common', 3, 1.0, cx=30, cy=45)

    s.camera(0.0, 0, 0, 1.8, yaw=20, pitch=-6)
    s.camera(15.0, 0, 0, 1.8, yaw=20, pitch=-6)

    s.press('f12', 2.0)          # on the ship: idle, nothing logged
    s.press('f12', 7.0)          # the mission (it counts as one from 6 s: 3 s after its world, as the loader waits)
    s.press('tab', 8.0)          # the map opens (no new world: the Map key decides)
    s.wheel(8.6, 1)
    s.wheel(9.0, 1)
    s.wheel(9.4, -1)
    s.cursor(0.0, 960, 540)
    s.cursor(9.8, 960, 540)
    s.cursor(10.4, 1900, 540)
    s.press('f12', 11.0)         # map open
    s.press('tab', 12.0)         # closed
    s.press('f12', 13.0)
    s.render_frames('7.5s', '11.5s', '13.5s')

    s.check('the loader started the addon', lambda r: r.log_has(r'started mods/chef/treasure_radar 0\.7\.\d'))
    s.check('the logger is on', lambda r: r.log_has(r'measure: on; F12 logs a snapshot'))
    s.check('no engine crash', lambda r: (r.crashed is None, str(r.crashed and r.crashed['message'])))
    s.check('no frame errors', lambda r: not r.log_has(r'frame error|ERROR in'))
    s.check('nothing logged on the ship', lambda r: (not r.log_has(r'measure: SNAPSHOT \d+ at [0-2]\.'),
                                                     '; '.join(r.log_lines(r'SNAPSHOT'))))
    s.check('the mission header: screen, map circle, compass strip',
            lambda r: r.log_has(r'measure: new mission') and r.log_has(r'measure:   screen 1920x1080; the map circle')
            and r.log_has(r'measure:   the compass strip as drawn'))
    s.check('three snapshots in the mission', lambda r: (len(r.log_lines(r'measure: SNAPSHOT \d+')) == 3,
                                                         '; '.join(r.log_lines(r'SNAPSHOT'))))
    s.check('the snapshot lists what is near',
            lambda r: r.log_has(r'measure:   structure +FABRICATOR') and r.log_has(r'measure:   loot +MEDALS'))
    s.check('Tab opens the map (key mode)', lambda r: r.log_has(r'measure: map open at [\d.]+ s \(open 1, key mode\)'))
    s.check('each zoom notch logged', lambda r: (len(r.log_lines(r'measure: zoom [+-]1 notch')) == 3,
                                                 '; '.join(r.log_lines(r'measure: zoom'))))
    s.check('the snapshot on the open map has the zoom and the cursor',
            lambda r: r.log_has(r'measure:   map open [\d.]+ s .*zoom \+1 notches this open.*cursor 1900,540'))
    s.check('the close line', lambda r: r.log_has(r'measure: map closed after [\d.]+ s: \+1 notches'))

    def note(r):
        n = r.count('7.5s', world='main', layer=(995, 995))
        top = r.count('11.5s', world='top', layer=(1979, 1979))
        return n > 0 and top > 0, 'note draws: map closed %s, on the open map %s' % (n, top)
    s.check('the MEASURE n LOGGED note shows, on the open map too', note)
