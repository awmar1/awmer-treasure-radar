"""0.6 Tester option at 1920x1080: the probe (its own addon, mods/chef/treasure_radar_probe) loads next to the mod,
calibration is on (guides on the open map's rim, numpad 5 picks a target, 8 nudges, 0 saves into the run folder's
%LOCALAPPDATA%), and the structure list takes the guessed kinds too (a thumper). F11 asks the probe for a census;
F9 stays the mod's (it marks a structure done) and the probe ignores it.

Run:  python -I dev/harness/run.py --mod <0.6 build> --scenario tester06 \
        --options core,compass,bezel,pings,map_objective,map_nest,@loot,tester
"""


def build(s):
    s.screen(1920, 1080).run(seconds=13, fps=30)
    s.world('mission', at=0.0, filler=5600, spread=400, seed=3)

    s.kind('tcs_tower', 'e979fe35857c54d9', group='objective')       # likely: in every build
    s.kind('thumper', '1e1ff43e60d4bb9a', group='objective')         # a guess: Tester builds only
    s.kind('bug_hole_small', '2e454bd4d24eb04a', group='nest')
    s.unit('tcs_tower', 30, 20)
    s.unit('thumper', -25, 40, label='a guessed kind')
    s.unit('bug_hole_small', 10, 15, label='the nest marked done by F9 at 11 s')
    s.unit('medal', 20, 60)
    s.unit('rare', -40, 30)
    s.unit('ammo', 5, 12)

    s.camera(0.0, 0, 0, 1.8, yaw=0, pitch=-5)
    s.camera(10.0, 0, 0, 1.8, yaw=30, pitch=-5)
    s.camera(13.0, 0, 0, 1.8, yaw=30, pitch=-5)

    s.map_open(4.0, 8.5)
    s.press('numpad 5', 5.0)     # next target (MAP R)
    s.press('numpad 8', 5.5)     # nudge
    s.press('numpad 0', 6.5)     # save (into the run folder)
    s.press('f11', 10.0)         # the probe's census
    s.press('f9', 11.0)          # the mod's: the nest 18 m ahead marked done

    s.render_frames('3s', '5s', '6s', '7s', '9s', '12s')

    s.check('the loader started the addon', lambda r: r.log_has(r'started mods/chef/treasure_radar 0\.6\.\d'))
    s.check('the loader started the probe', lambda r: r.log_has(r'started mods/chef/treasure_radar_probe'))
    s.check('no frame errors', lambda r: not r.log_has(r'frame error'))
    s.check('calibration is on', lambda r: r.log_has(r'calibrate: on'))
    s.check('the guessed kinds are on', lambda r: r.log_has(r'structures: Tester build: guesses on \(\d+\)'))
    s.check('the guessed thumper is found with the TCS tower', lambda r: r.log_has(r'structures: .*\b2 objectives'))

    def guides(r):
        closed, opened = r.count('3s', world='top'), r.count('6s', world='top', layer=(1950, 1979))
        return closed == 0 and opened > 0, 'top-world draws: map closed %s, calibration layers with the map open %s' \
            % (closed, opened)
    s.check('calibration guides draw over the open map', guides)
    s.check('numpad 0 saves the nudges', lambda r: r.log_has(r'calibrate: saved'))
    s.check('F11 asks the probe for a census', lambda r: r.log_has(r'F11: census requested'))
    s.check('F9 is left to the mod', lambda r: (r.log_has(r'structures: F9 marked') and not r.log_has(r'F9: census'),
                                                'mod F9 %s, probe F9 %s' % (bool(r.log_has(r'structures: F9 marked')),
                                                                            bool(r.log_has(r'F9: census')))))
