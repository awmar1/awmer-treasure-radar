"""0.6: the mission scenario for the 0.6 addon (textures by path, T.TEX), with objectives and structures: at
2560x1440, the ship, then a mission with every loot kind, a TCS tower, a bug hole, a detector tower and a fabricator.
I set a waypoint on the medal by looking at it (numpad 1), pick it up (the waypoint clears itself), toggle the world
markers (F8) and the HUD (F7, holding Tab), mark the TCS tower done (F9), zoom (numpad +), and open the map: numpad 9
picks an icon, numpad 1 sets its waypoint, numpad 3 clears them all.

Run:  python -I dev/harness/run.py --mod <0.6 build> --scenario mission06 \
        --options core,ledger,compass,bezel,pings,overlay,markers_50,map_objective,map_side,map_nest,map_structure,@loot
(@loot = every loot kind's option.)
"""


def build(s):
    s.screen(2560, 1440).run(seconds=23, fps=30)

    s.world('ship', at=0.0, filler=3200, spread=60, seed=11)
    s.world('mission', at=1.0, filler=6000, spread=450, seed=7)

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

    # the camera: at 9.6 s I look down at the medal (4 m ahead, bearing 14 degrees)
    s.camera(0.0, 0, 0, 1.8, yaw=0, pitch=-6)
    s.camera(6.0, 0, 0, 1.8, yaw=0, pitch=-6)
    s.camera(9.6, 5, 24, 1.8, yaw=14, pitch=-20)
    s.camera(10.0, 5, 24, 1.8, yaw=14, pitch=-20)
    s.camera(12.0, 5, 24, 1.8, yaw=60, pitch=-6)
    s.camera(16.0, 20, 30, 1.8, yaw=120, pitch=-2)
    s.camera(23.0, 20, 30, 1.8, yaw=200, pitch=-2)

    # input
    s.press('numpad 1', 9.8)     # a waypoint on the medal I'm looking at
    s.press('f8', 12.5)          # world markers off
    s.press('f8', 13.6)          # and on again
    s.press('f7', 14.5)          # HUD hidden
    s.press('f7', 15.5)          # shown
    s.hold('tab', 16.0, 0.8)     # held 0.6 s+: hidden
    s.hold('tab', 17.5, 0.8)     # shown again
    s.press('numpad +', 18.5)    # zoom in
    s.press('f9', 18.8)          # the TCS tower (35 m, ~35 degrees off my view) marked done
    s.map_open(19.5, 21.2)       # the game's map
    s.press('numpad 9', 19.9)    # pick an icon on the map
    s.press('numpad 1', 20.2)    # its waypoint
    s.cursor(0.0, 1280, 720)
    s.cursor(20.3, 2100, 300)
    s.wheel(20.7, 1)             # the overlay hides once the map may have moved
    s.click('left', 20.8)        # a click never selects (HOVER_SELECT is off)
    s.press('numpad 3', 21.6)    # clear every waypoint

    s.render_frames('3s', '5s', '9.5s', '9.9s', '11.5s', '13s', '15s', '17s', '19s', '20s', '20.5s', '21s',
                    '21.5s', '22.5s')

    # ---------------------------------------------------------------- checks
    s.check('the loader started the addon', lambda r: r.log_has(r'started mods/chef/treasure_radar 0\.6\.\d'))
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
        n = r.count('9.5s', layer=(950, 979))
        return n > 0, '%s compass draws' % n
    s.check('the compass draws pips', compass)

    def waypoint(r):
        on, off = r.count('9.9s', tex='ping/wp'), r.count('11.5s', tex='ping/wp')
        return on > 0 and off == 0 and r.log_has(r'pings: waypoint .* set \(aimed'), \
            'ping/wp draws: %s with the waypoint, %s after the pickup' % (on, off)
    s.check('numpad 1 sets a waypoint on the aimed medal; the pickup clears it', waypoint)
    s.check('the cleared waypoint was logged', lambda r: r.log_has(r'pings: waypoint .*, 0 left'))

    def picked(r):
        before = r.count('9.5s', tex='icons/medal', layer=(900, 949))
        after = r.count('11.5s', tex='icons/medal', layer=(900, 949))
        check = r.count('11.5s', tex='ui/check', layer=(900, 949))
        return before >= 2 and after == before - 1 and check >= 1, \
            'medal icons (radar + ledger) %s -> %s, ledger check marks after: %s' % (before, after, check)
    s.check('the picked-up medal leaves the radar; the ledger shows it cleared', picked)
    s.check('the next list counts it gone', lambda r: r.log_has(r'ledger: .*medal 0/1'))

    def markers(r):
        on, off = r.count('9.5s', tex='pin/disc', layer=(860, 899)), r.count('13s', tex='pin/disc', layer=(860, 899))
        return on > 0 and off == 0, 'pin draws %s (shown) / %s (F8 hidden)' % (on, off)
    s.check('world markers draw near loot, F8 hides them', markers)

    def hidden(r):
        f7, tab, back = r.count('15s', tex='radar/'), r.count('17s', tex='radar/'), r.count('19s', tex='radar/')
        return f7 == 0 and tab == 0 and back > 0, 'radar/* draws: F7 %s, Tab held %s, after %s' % (f7, tab, back)
    s.check('F7 and holding Tab hide the radar', hidden)
    s.check('F9 marks the TCS tower done', lambda r: r.log_has(r'structures: F9 marked TCS TOWER \d+ m done'))

    def top(r):
        closed, opened, after = r.count('19s', world='top'), r.count('20s', world='top'), r.count('21.5s', world='top')
        return closed == 0 and opened > 0 and after == 0, \
            'top-world draws: before %s, map open %s, after %s' % (closed, opened, after)
    s.check('the map views draw in the top world only while the map is open', top)
    s.check('numpad 9 / numpad 1 set a waypoint on the map', lambda r: r.log_has(r'pings: waypoint .* set \((?!aimed)'))
    s.check('numpad 3 clears the waypoints', lambda r: (r.log_has(r'pings: \d+ waypoints? cleared'),
                                                        'ping/wp at 22.5 s: %s' % r.count('22.5s', tex='ping/wp')))
