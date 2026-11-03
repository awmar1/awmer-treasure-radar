"""0.6 Tester option in a mission, left alone the way a player would: the map opened and clicked, a Q ping, the probe's
automatic census 20 s in and its diffs every 10 s, and a unit kind that crashes the game on Unit.world_position.
Without F11 nothing may touch that kind; the loot kinds (proven: 0.5.1's loader asks them) still get positions. F11
in a mission does ask every kind, so it isn't pressed here.

Run:  python -I dev/harness/run.py --mod <0.6 build> --scenario probe_mission06 \
        --options core,compass,bezel,pings,map_objective,map_nest,@loot,tester
"""


def build(s):
    s.screen(1920, 1080).run(seconds=40, fps=30)     # the census ends near 24 s, its diff 10 s later
    s.world('mission', at=0.0, filler=5600, spread=400, seed=7)

    s.kind('fragile', '46cab355bd8d4d37', group='other')
    s.fragile('fragile')
    s.ring('fragile', 6, 25)
    s.unit('fragile', 3, 8, label='a kind that crashes on a position')
    s.unit('medal', 20, 40)
    s.unit('rare', -30, 25)
    s.unit('ammo', 6, 14)

    s.camera(0.0, 0, 0, 1.8, yaw=0, pitch=-5)
    s.camera(40.0, 0, 0, 1.8, yaw=20, pitch=-5)

    s.map_open(4.0, 9.0)
    s.cursor(5.0, 900, 500)
    s.click('left', 5.5)
    s.cursor(6.0, 1000, 600)
    s.click('left', 6.5)
    s.press('q', 11.0)
    s.press('f10', 13.0)

    s.check('the loader started the probe', lambda r: r.log_has(r'started mods/chef/treasure_radar_probe'))
    s.check('a mission', lambda r: r.log_has(r'world \d+: mission'))
    s.check('no engine crash', lambda r: (r.crashed is None, str(r.crashed and r.crashed['message'])))
    s.check('a scan after a map click, of safe calls',
            lambda r: r.log_has(r'SCAN \d+ \(after a map click[^)]*\) .* [1-9]\d* not asked'))
    s.check('a scan after a ping', lambda r: r.log_has(r'SCAN \d+ \([^)]*after a Q ping'))
    s.check('the automatic census ran 20 s in, of safe calls',
            lambda r: r.log_has(r'SCAN \d+ \(auto, 20 s into the mission\) .* [1-9]\d* not asked')
            and r.log_has(r'CENSUS \d+: positions only for kinds proven safe'))
    s.check('the loot kinds still get positions',
            lambda r: r.log_has(r'CENSUS \d+: Treasure Radar 0\.5\.1 kinds .*medal 1 \(\d+ m\)'))
    s.check('a diff every 10 s', lambda r: r.log_has(r'SCAN \d+ \(every\)'))
    s.check('no frame errors', lambda r: not r.log_has(r'frame error|ERROR in'))
