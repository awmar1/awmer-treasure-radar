"""The corner radar clear of the game's chat at every screen and size: runs dev/src/addon in the module sim (no
bundle, no game) and checks the radar's draws (layers 900-949) against the chat's box (look.py's CHAT, measured on a
1080p screenshot and scaled with HUD Scale as the game scales it).

    python -I -B dev/harness/chat_check.py [--out DIR]

Cases: 1920x1080, 2560x1440, 3840x2160 and 3440x1440, each radar size (small, medium, large), facing N, E, S and W
(the N tick goes round the rim), and HUD Scale 1.25 at 1080p and 1440p. Each runs 30 frames (my waypoints go in at
0.3 s) and is checked at frames 10 and 29. Prints one row per case; exits 1 on any overlap, an off-screen radar or
no radar at all.
"""
import argparse
import importlib.util
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
DEV = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(DEV, 'src', 'sim'))

import sim  # noqa: E402


def load_look():
    path = os.path.join(DEV, 'src', 'sim', 'scenarios', 'look.py')
    spec = importlib.util.spec_from_file_location('chat_check_look', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SIZES = [(1920, 1080), (2560, 1440), (3840, 2160), (3440, 1440)]
RADAR = ['small', 'medium', 'large']
YAWS = [0, 90, 180, 270]
HUD = [((1920, 1080), 1.25), ((2560, 1440), 1.25)]
FRAMES, AT = 30, (10, 29)


def cases():
    for size in SIZES:
        for r in RADAR:
            for yaw in YAWS:
                yield size, r, yaw, None
    for size, scale in HUD:
        for r in RADAR:
            for yaw in (0, 180):
                yield size, r, yaw, scale


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--out', default=os.path.join(DEV, 'out', 'chat_check'))
    a = ap.parse_args(argv)
    look = load_look()
    bad, rows = 0, []
    print('%-10s %-6s %4s %5s  %-26s %-26s %s' % ('screen', 'radar', 'yaw', 'hud', 'radar box', 'chat box', 'result'))
    for size, r, yaw, scale in cases():
        name = '%dx%d_%s_%d%s' % (size[0], size[1], r, yaw, '_hud%g' % scale if scale else '')
        scn = {
            'name': name, 'defaults': True, 'size': size, 'options': {'radar': r},
            'frames': FRAMES, 'camera': [(0, 0, 0, 1.6, yaw, -7)],
            'units': look.LOOT + look.MARKS, 'lua': look.WAYPOINTS_LUA,
        }
        if scale:
            scn['hud'] = {'hud_scale': scale}
        s = sim.Sim(scn, out=os.path.join(a.out, name))
        fails, bb, chat = [], None, None
        for f in range(FRAMES):
            draws = s.step(f)
            if f not in AT:
                continue
            bb, n = look.layer_box(draws, 900, 949)
            chat = look.chat_box(s)
            if not bb:
                fails.append('f%d: no radar' % f)
                continue
            if look.overlaps(bb, chat):
                fails.append('f%d: overlaps the chat' % f)
            if not (bb[0] >= 0 and bb[1] >= 0 and bb[2] <= s.w and bb[3] <= s.h):
                fails.append('f%d: off screen' % f)
        warns = len(s.G.SIM.warnings) + len(s.py_warnings)
        if warns:
            fails.append('%d warnings' % warns)
        bad += bool(fails)
        print('%-10s %-6s %4d %5s  %-26s %-26s %s' % (
            '%dx%d' % size, r, yaw, '%g' % scale if scale else '0.9', look.fmt_box(bb) if bb else '-',
            look.fmt_box(chat) if chat else '-', '; '.join(fails) or 'ok'))
    total = sum(1 for _ in cases())
    print('%d cases, %d failed' % (total, bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
