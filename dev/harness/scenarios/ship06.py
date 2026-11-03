"""0.6 Tester option on the ship (2026-10-26): Tab held, the mouse moved, two left clicks, and the game crashed. The
probe's scan after a map click asked Unit.world_position of every unit kind, and kind 46cab355bd8d4d37 crashes the
game there. This replays that session with that kind made fragile, then a Q ping, F10 and F11: none of it may touch
the fragile kind (on the ship, F11 too is a census of kinds with positions only for proven ones).

Run:  python -I dev/harness/run.py --mod <0.6 build> --scenario ship06 \
        --options core,compass,bezel,pings,map_objective,map_nest,@loot,tester
"""


def build(s):
    s.screen(1920, 1080).run(seconds=12, fps=30)
    s.world('ship', at=0.0, filler=2250, spread=150, seed=5)     # not a mission: under the loader's 5,000 units

    s.kind('ship_fragile', '46cab355bd8d4d37', group='ship')
    s.fragile('ship_fragile')
    s.ring('ship_fragile', 4, 12)
    s.unit('ship_fragile', 1, 3, label='the kind that crashed the game')

    s.camera(0.0, 0, 0, 22, yaw=7, pitch=-9, fov=90)
    s.hold('tab', 4.0, 0.7)              # the session in the log: Tab held 0.68 s
    s.cursor(4.8, 748, 522)
    s.click('left', 5.0)
    s.cursor(5.4, 829, 476)
    s.click('left', 5.5)                 # 0.6 s later the old probe's scan started, and crashed
    s.press('q', 7.0)                    # a ping tap
    s.press('f10', 8.0)                  # MARK 1
    s.press('f11', 9.5)                  # the census

    s.check('the loader started the probe', lambda r: r.log_has(r'started mods/chef/treasure_radar_probe'))
    s.check('the ship is not a mission', lambda r: r.log_has(r'world \d+: not a mission'))
    s.check('no engine crash', lambda r: (r.crashed is None, str(r.crashed and r.crashed['message'])))
    s.check('the probe saw the map session', lambda r: r.log_has(r'MAP\? session 1 starts \(tab\)'))
    s.check('both clicks were logged', lambda r: (len(r.log_lines(r'MOUSE left up after')) == 2,
                                                  '%d click lines' % len(r.log_lines(r'MOUSE left up after'))))
    s.check('no scan after a map click or a ping off a mission',
            lambda r: not r.log_has(r'SCAN \d+ \((after a map click|after a Q ping)'))
    s.check('F10 still asks for a diff of safe calls', lambda r: r.log_has(r'SCAN \d+ \(MARK 1\) .* not asked'))
    s.check('F11 on the ship is the safe census', lambda r: r.log_has(r'F11: census requested \(not in a mission'))
    s.check('the F11 census ran without asking unproven kinds',
            lambda r: r.log_has(r'SCAN \d+ \(F11\) world \S+: \d+ units listed.* [1-9]\d* not asked')
            and r.log_has(r'CENSUS \d+: positions only for kinds proven safe'))
    s.check('no frame errors', lambda r: not r.log_has(r'frame error|ERROR in'))
