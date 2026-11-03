"""The top world: with HUD calibration on (an extra options file, calibrate = true), the addon draws its map-rim
ring at layer 2000+960. The loader sends that to the first world that isn't the main one (the open map's), at layer
-1000, and drops it when the map closes (without touching the GUI of the world that went away).

Run:  python -I dev/harness/run.py --mod . --options core,ledger,loot --scenario map_top
"""


def build(s):
    s.screen(1920, 1080).run(seconds=14, fps=30)
    s.options_file(calibrate=True)
    s.world('mission', at=0.0, filler=5600, spread=400, seed=3)
    s.unit('medal', 20, 60)
    s.unit('rare', -40, 30)
    s.unit('super', 80, -20)
    s.unit('ammo', 5, 12)
    s.camera(0.0, 0, 0, 1.8, yaw=0, pitch=-5)
    s.camera(14.0, 0, 0, 1.8, yaw=90, pitch=-5)
    s.map_open(5.0, 8.0)
    s.map_open(10.0, 12.0)
    s.render_frames('4.5s', '6s', '9s', '11s', '13s')

    def top(r):
        closed = r.count('4.5s', world='top')
        opened = r.count('6s', world='top')
        main_hi = r.count('6s', world='main', layer=(1000, 99999))
        return closed == 0 and opened > 0 and main_hi == 0, \
            'top-world draws: map closed %s, map open %s; main-world draws at 1000+: %s' % (closed, opened, main_hi)
    s.check('layer 2000+ lands in the top world while the map is open', top)
    s.check('it lands at its layer - 1000 (chef.TOP + 960 = 2960 -> 1960)',
            lambda r: all(d[1][1] == 1960 for d in r.draws_of('6s', world='top')))
    s.check('a second opening works again (new top GUI)', lambda r: r.count('11s', world='top') > 0)
    s.check('gone with the map', lambda r: r.count('9s', world='top') == 0 and r.count('13s', world='top') == 0)
    s.check('no frame errors', lambda r: not r.log_has(r'frame error'))
