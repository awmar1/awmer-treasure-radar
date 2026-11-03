"""A mission at 2560x1440: the ship, then a mission world of 6,000+ units with every loot kind around me; I walk to a
medal and a Super Credit and pick them up, toggle the world markers (F8), the radar (F7, then holding Tab), zoom
(numpad +), and open the map for a moment.

Run:  python -I dev/harness/run.py --mod . --options core,ledger,loot,markers_50 --scenario mission
"""


def build(s):
    s.screen(2560, 1440).run(seconds=22, fps=30)

    # the ship (a small world, never a mission), then the mission world: stable 3 s later, a mission (> 5000 units)
    s.world('ship', at=0.0, filler=3200, spread=60, seed=11)
    s.world('mission', at=1.0, filler=6000, spread=450, seed=7)

    # loot (z = ground). I stand at 0, 0 looking north (+y) and walk to the medal at 6, 28.
    s.unit('medal', 6, 28, pickup_at=10.0, label='the medal on my path')
    s.unit('credit', -10, 35, pickup_at=11.0, label='a credit near the medal')
    s.unit('credit', 70, -60)
    s.ring('common', 3, 1.0, cx=30, cy=45)                 # a pile of three: one marker "x3", one radar stack
    s.unit('common', -60, 80, variant=4)
    s.unit('rare', 25, 10)
    s.unit('rare', -90, -40, variant=2)
    s.unit('super', 110, 40)
    s.unit('super', -30, -100, variant=1)
    s.unit('requisition', -25, 20)
    s.unit('ammo', 12, 40)
    s.unit('grenade', 14, 41)
    s.unit('stim', -8, 15)
    s.unit('common', 40, 120, variant=7, spawn_at=12.0)   # turns up later (a new unit in the world)

    # the camera (my view; z up, yaw clockwise from north, pitch down negative)
    s.camera(0.0, 0, 0, 1.8, yaw=0, pitch=-6)
    s.camera(6.0, 0, 0, 1.8, yaw=0, pitch=-6)
    s.camera(9.6, 5, 24, 1.8, yaw=10, pitch=-8)
    s.camera(12.0, 5, 24, 1.8, yaw=60, pitch=-6)
    s.camera(16.0, 20, 30, 1.8, yaw=120, pitch=-4)
    s.camera(22.0, 20, 30, 1.8, yaw=200, pitch=-4)

    # input
    s.press('f8', 12.5)          # world markers off
    s.press('f8', 13.6)          # and on again
    s.press('f7', 14.5)          # radar (and ledger) hidden
    s.press('f7', 15.5)          # shown
    s.hold('tab', 16.0, 0.8)     # held 0.6 s+: hidden
    s.hold('tab', 17.5, 0.8)     # shown again
    s.press('numpad +', 18.5)    # zoom in
    s.cursor(0.0, 1280, 720)
    s.cursor(19.8, 2100, 300)
    s.wheel(20.2, 1)
    s.click('left', 20.4)
    s.map_open(19.5, 21.0)       # the game's map: a second world meanwhile

    s.render_frames('3s', '5s', '9.5s', '11.5s', '13s', '15s', '17s', '19s', '20s', '21.5s')

    # ---------------------------------------------------------------- checks
    s.check('the loader started the addon', lambda r: r.log_has(r'started mods/chef/treasure_radar 0\.5\.1'))
    s.check('the mission world became a mission', lambda r: r.log_has(r'mission'))
    s.check('the ledger logged counts', lambda r: r.log_has(r'ledger: .*medal 1/1'))
    s.check('no frame errors', lambda r: not r.log_has(r'frame error'))
    s.check('no radar before the mission world settles (3 s)', lambda r: (
        r.count('3s', world='main', layer=(890, 950)) == 0, '%s draws' % r.count('3s', world='main', layer=(890, 950))))

    def picked(r):
        before = r.count('9.5s', tex='medal', layer=(905, 925))
        after = r.count('11.5s', tex='medal', layer=(905, 925))
        check = r.count('11.5s', tex='check')
        return before == 2 and after == 1 and check >= 1, \
            'medal icons (radar + ledger) %s -> %s, ledger check marks after: %s' % (before, after, check)
    s.check('the picked-up medal leaves the radar; the ledger shows it cleared', picked)
    s.check('the next list counts it gone', lambda r: r.log_has(r'ledger: .*medal 0/1'))

    def markers(r):
        on, off = r.count('9.5s', layer=(870, 889)), r.count('13s', layer=(870, 889))
        return on > 0 and off == 0, 'marker draws %s (shown) / %s (F8 hidden)' % (on, off)
    s.check('world markers draw near loot, F8 hides them', markers)

    def hidden(r):
        f7 = r.count('15s', tex='sweep')
        tab = r.count('17s', tex='sweep')
        back = r.count('19s', tex='sweep')
        return f7 == 0 and tab == 0 and back > 0, 'sweep draws: F7 %s, Tab held %s, after %s' % (f7, tab, back)
    s.check('F7 and holding Tab hide the radar', hidden)
    s.check('0.5.1 draws nothing in the map world without calibration',
            lambda r: (r.count('20s', world='top') == 0, '%s top draws' % r.count('20s', world='top')))
