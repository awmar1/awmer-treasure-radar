"""0.7: the mission scenario for 0.7.0 with its default options, at 2560x1440. Like the real game, two more worlds are
there from the mission's start (the map's world list can't tell the map open), so the Map key (Tab) decides. I set
a waypoint on the medal by looking at it (numpad 1), pick it up (the waypoint clears itself), set one on a sample
pile, toggle the world markers (F8) and the HUD (F7), tap Tab twice quickly (the map opened and closed again), mark
the TCS tower done (F9), and open the map: the quiet rim (marks and the waypoint just outside it), no overlay, numpad
9 does nothing, numpad 1 says to close the map and aim; numpad 3 clears the waypoints. The compass pips sit on the
game's strip (the measured geometry in compass.lua).

Run:  python -I dev/harness/run.py --mod dev/build/Treasure-Radar-0.7.0 --scenario mission07 \
        --options core,loot_all,extras_all,radar_medium,markers_50,opacity_100
"""
import re


def build(s):
    s.screen(2560, 1440).run(seconds=24, fps=30)

    s.world('ship', at=0.0, filler=3200, spread=60, seed=11)
    s.world('mission', at=1.0, filler=6000, spread=450, seed=7)
    # the game's other worlds, there all mission long (seen in the 0.6 Tester's logs)
    s.world('hud_a', at=1.0, main=False)
    s.world('hud_b', at=1.0, main=False)

    # structures (ids from dev/src/addon/structures.lua)
    s.kind('tcs_tower', 'e979fe35857c54d9', group='objective')
    s.kind('bug_hole_medium', 'a83587cbff25c79e', group='nest')
    s.kind('detector_tower', '2670e0047b2eb409', group='side_objective')
    s.kind('fabricator', 'a57ae2a703c02899', group='structure')
    s.unit('tcs_tower', 50, 12, label='the TCS tower (F9 at 18.8 s)')
    s.unit('bug_hole_medium', -50, 60)
    s.unit('detector_tower', 100, -20)
    s.unit('fabricator', -40, -30)

    # loot. I stand at 0, 0 looking north (+y) and walk to the medal at 6, 28.
    s.unit('medal', 6, 28, pickup_at=10.0, label='the medal on my path')
    s.unit('credit', -10, 35, pickup_at=11.0, label='a credit near the medal')
    s.unit('credit', 70, -60)
    s.ring('common', 3, 1.0, cx=30, cy=45)
    s.unit('common', -60, 80, variant=4)
    s.unit('rare', 25, 10)
    s.unit('rare', -90, -40, variant=2)
    s.unit('super', 110, 40)
    s.unit('super', -30, -100, variant=1)
    s.unit('requisition', -25, 20)
    s.unit('ammo', 12, 40)
    s.unit('grenade', 14, 41)
    s.unit('stim', -8, 15)
    s.unit('common', 40, 120, variant=7, spawn_at=12.0)

    # the camera: at 9.6 s I look down at the medal (4 m ahead, bearing 14 degrees); at 12.0 s at the sample ring
    # (30, 45: bearing 50 degrees from where I stand, 33 m off and 2.6 degrees down)
    s.camera(0.0, 0, 0, 1.8, yaw=0, pitch=-6)
    s.camera(6.0, 0, 0, 1.8, yaw=0, pitch=-6)
    s.camera(9.6, 5, 24, 1.8, yaw=14, pitch=-20)
    s.camera(10.0, 5, 24, 1.8, yaw=14, pitch=-20)
    s.camera(12.0, 5, 24, 1.8, yaw=50, pitch=-3)
    s.camera(12.5, 5, 24, 1.8, yaw=50, pitch=-3)
    s.camera(16.0, 20, 30, 1.8, yaw=120, pitch=-2)
    s.camera(24.0, 20, 30, 1.8, yaw=200, pitch=-2)

    # input
    s.press('numpad 1', 9.8)     # a waypoint on the medal I'm looking at
    s.press('numpad 1', 12.2)    # and one on the sample ring
    s.press('f8', 12.8)          # world markers off
    s.press('f8', 13.6)          # and on again
    s.press('f7', 14.5)          # HUD hidden
    s.press('f7', 15.5)          # shown
    s.press('tab', 16.0)         # the map opened ...
    s.press('tab', 16.3)         # ... and closed again, inside the 0.75 s proof window
    s.press('numpad +', 18.5)    # zoom in
    s.press('f9', 18.8)          # the TCS tower (35 m, ~35 degrees off my view) marked done
    s.map_open(19.5, 21.2)       # the game's map (Tab taps at both ends)
    s.press('numpad 9', 19.9)    # 0.6's map selection: nothing in 0.7
    s.press('numpad 1', 20.2)    # on the open map: a toast to close it and aim
    s.cursor(0.0, 1280, 720)
    s.cursor(20.3, 2100, 300)
    s.wheel(20.7, 1)
    s.click('left', 20.8)
    s.press('numpad 3', 21.6)    # clear every waypoint

    s.render_frames('3s', '9.5s', '9.9s', '11.5s', '12.4s', '13.2s', '15s', '17.5s', '19s', '20s', '20.5s',
                    '21.5s', '22.5s')

    # ---------------------------------------------------------------- checks
    s.check('the loader started the addon', lambda r: r.log_has(r'started mods/chef/treasure_radar 0\.7\.\d'))
    s.check('no frame errors', lambda r: not r.log_has(r'frame error'))
    s.check('the ledger logged counts', lambda r: r.log_has(r'ledger: .*medal 1/1'))
    s.check('the structures were found',
            lambda r: r.log_has(r'structures: .*objective') and r.log_has(r'structures: .*nest'))
    s.check('nothing before the mission world settles (3 s)', lambda r: (
        r.count('3s', world='main', layer=(860, 999)) == 0, '%s draws' % r.count('3s', world='main', layer=(860, 999))))

    def map_marks(r):
        n = r.count('9.5s', tex='map/', layer=(900, 949))
        return n >= 2, '%s map/* draws on the radar' % n
    s.check('objectives and structures on the radar', map_marks)

    def compass(r):
        lines = r.log_lines(r'compass: 2560x1440, center x')
        m = lines and re.search(r'center x (\d+), middle (\d+) px from the top, (\d+) px for ([\d.]+) degrees', lines[-1])
        if not m:
            return False, 'no compass geometry line'
        cx, mid, half = int(m.group(1)), int(m.group(2)), int(m.group(3))
        pips = r.draws_of('9.5s', world='main', layer=(952, 953)) or []
        if not pips:
            return False, 'no pip icons'
        row = 1440 - mid
        dy = max(abs(p[1][3] + p[1][5] / 2 - row) for p in pips)
        dx = max(abs(p[1][2] + p[1][4] / 2 - cx) for p in pips)
        return dy <= 0.012 * 1440 and dx <= half + 2, \
            '%d pips; middle %d px from the top (row y %d): farthest pip %.1f px off the row, %.0f px off center ' \
            '(strip half %d px)' % (len(pips), mid, row, dy, dx, half)
    s.check('the compass pips sit on the measured strip', compass)

    def waypoint(r):
        on, off = r.count('9.9s', tex='ping/wp'), r.count('11.5s', tex='ping/wp')
        return on > 0 and off == 0 and r.log_has(r'pings: waypoint MEDAL.* set \(aimed'), \
            'ping/wp draws: %s with the waypoint, %s after the pickup' % (on, off)
    s.check('numpad 1 sets a waypoint on the aimed medal; the pickup clears it', waypoint)
    s.check('the cleared waypoint was logged', lambda r: r.log_has(r'pings: waypoint .*, 0 left'))
    s.check('numpad 1 sets one on the aimed sample ring',
            lambda r: (r.log_has(r'pings: waypoint COMMON.* set \(aimed'), '; '.join(r.log_lines(r'pings: waypoint'))))

    def picked(r):
        before = r.count('9.5s', tex='icons/medal', layer=(900, 949))
        after = r.count('11.5s', tex='icons/medal', layer=(900, 949))
        check = r.count('11.5s', tex='ui/check', layer=(900, 949))
        return before >= 2 and after == before - 1 and check >= 1, \
            'medal icons (radar + ledger) %s -> %s, ledger check marks after: %s' % (before, after, check)
    s.check('the picked-up medal leaves the radar; the ledger shows it cleared', picked)
    s.check('the next list counts it gone', lambda r: r.log_has(r'ledger: .*medal 0/1'))

    def markers(r):
        on, off = r.count('12.4s', tex='pin/disc', layer=(860, 899)), r.count('13.2s', tex='pin/disc', layer=(860, 899))
        wp = r.count('13.2s', tex='ping/wp')
        return on > 1 and off == 1 and wp > 0, \
            'pin draws %s (shown) / %s (F8 hidden: the waypoint\'s own, its glyph %s)' % (on, off, wp)
    s.check('world markers draw near loot, F8 hides them (the waypoint\'s pin stays)', markers)

    def hidden(r):
        f7, back = r.count('15s', tex='radar/'), r.count('17.5s', tex='radar/')
        return f7 == 0 and back > 0, 'radar/* draws: F7 %s, after %s' % (f7, back)
    s.check('F7 hides the radar', hidden)
    s.check('F9 marks the TCS tower done', lambda r: r.log_has(r'structures: F9 marked TCS TOWER \d+ m done'))

    s.check('the two worlds from the start make it key mode',
            lambda r: r.log_has(r'map: a second world is there with the map closed too; the Map key decides'))

    def quick(r):
        n = r.count('17.5s', world='top')
        opened = len(r.log_lines(r'^.*map open \('))
        return n == 0, 'top-world draws 1.2 s after two quick taps: %s; map opens logged so far: %d' % (n, opened)
    s.check('two quick Tab taps leave the map closed', quick)

    def top(r):
        closed, opened, after = r.count('19s', world='top'), r.count('20s', world='top'), r.count('21.5s', world='top')
        return closed == 0 and opened > 0 and after == 0, \
            'top-world draws: before %s, map open %s, after %s' % (closed, opened, after)
    s.check('the map views draw in the top world only while the map is open', top)

    def rim(r):
        marks = r.count('20s', world='top', layer=(1900, 1919))
        wp = r.count('20s', world='top', tex='ping/wp')
        over = r.count('20s', world='top', layer=(1920, 1949))
        return marks > 0 and wp > 0 and over == 0, \
            'rim draws %s (the waypoint %s); overlay draws %s' % (marks, wp, over)
    s.check('the open map: rim marks and the waypoint, no overlay', rim)
    s.check('numpad 9 selects nothing', lambda r: not r.log_has(r'pings: .*select'))

    def toast(r):
        n = r.count('20.5s', world='top', layer=(1975, 1979))
        sets = len(r.log_lines(r'pings: waypoint .* set \('))
        return n > 0 and sets == 2, 'toast draws on the open map %s; waypoints set all run %d' % (n, sets)
    s.check('numpad 1 on the open map only says how', toast)
    s.check('numpad 3 clears the waypoints', lambda r: (r.log_has(r'pings: \d+ waypoints? cleared'),
                                                        'ping/wp at 22.5 s: %s' % r.count('22.5s', tex='ping/wp')))
