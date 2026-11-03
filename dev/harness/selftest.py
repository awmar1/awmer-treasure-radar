"""Checks the harness itself (not a mod): the fake engine's sharp edges and the runner's crash handling, with a tiny
fake mod built in a temp folder. Run:  python -I dev/harness/selftest.py      (exit code 0 = all passed)
"""
import math
import os
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'tools', '_pylib'))
sys.path.insert(0, HERE)

from lupa import lua51  # noqa: E402

import archive  # noqa: E402
import render  # noqa: E402
import runner  # noqa: E402
from scenario import Scenario  # noqa: E402

results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print('[%s] %s%s' % ('ok' if ok else 'FAIL', name, (': ' + str(detail)) if detail else ''))


def engine():
    L = lua51.LuaRuntime(unpack_returned_tuples=True)
    return L, runner.load_engine(L)


def test_engine():
    L, E = engine()
    E.w, E.h = 1920, 1080
    E.new_world('a', True)
    E.begin_frame(1 / 30)
    run = L.eval
    # projection: the same as render.Cam's
    E.set_camera(3, -4, 1.8, 35, -10, 50)
    sx, sy, depth = E.project(20, 30, 0)
    cam = render.Cam(3, -4, 1.8, 35, -10, 50, 1920, 1080)
    ix, iy, zc = cam.project(20, 30, 0)
    check('world_to_screen matches the renderer (bottom-left origin)',
          abs(sx - ix) < 1e-6 and abs(sy - (1080 - iy)) < 1e-6 and abs(depth - zc) < 1e-6,
          '%.2f,%.2f vs %.2f,%.2f' % (sx, sy, ix, 1080 - iy))
    yaw, pitch = math.radians(35), math.radians(-10)
    ahead = (3 + 10 * math.sin(yaw) * math.cos(pitch), -4 + 10 * math.cos(yaw) * math.cos(pitch), 1.8 + 10 * math.sin(pitch))
    cx, cy, _ = E.project(*ahead)
    check('a point straight ahead (yaw clockwise from north, pitch down) lands at the screen center',
          abs(cx - 960) < 1e-6 and abs(cy - 540) < 1e-6, '%.3f, %.3f' % (cx, cy))
    # a stake to my right (east of me facing north) is right of the center
    E.set_camera(0, 0, 1.8, 0, 0, 50)
    check('east is to the right facing north; up is up', E.project(5, 20, 1.8)[0] > 960 and E.project(0, 20, 5)[1] > 540)
    E.set_camera(3, -4, 1.8, 35, -10, 50)
    # unknown functions are nil (and listed)
    check('an unknown engine function is nil', run('stingray.Gui.text') is None and 'Gui.text' in (E.dump_missing() or ''))
    # a stale Color draws white with a warning
    L.execute("""
      local S = stingray
      HW = S.Application.main_world()
      HG = S.World.create_screen_gui(HW, 'immediate')
      OLD = S.Color(255, 255, 0, 0)
    """)
    E.begin_frame(1 / 30)
    L.execute("stingray.Gui.rect(HG, stingray.Vector3(1, 2, 3), stingray.Vector2(4, 5), OLD)")
    d = runner.parse_dump(E.dump())
    check('a stale Color draws white, with a warning', d and d[0][1][6] == (255, 255, 255, 255) and 'stale Color' in E.dump_warnings(),
          d and d[0][1][6])
    # a value from an earlier frame is flagged
    L.execute("OLDV = stingray.Vector3(1, 2, 3)")
    E.begin_frame(1 / 30)
    L.execute("stingray.Gui.rect(HG, OLDV, stingray.Vector2(4, 5), stingray.Color(255, 1, 2, 3))")
    check('a stale Vector3 is flagged', 'stale Vector3' in E.dump_warnings())
    # a GUI used after its world went away crashes
    E.new_world('b', True)              # the old main world is destroyed
    ok = L.execute("return pcall(stingray.Gui.rect, HG, stingray.Vector3(1, 2, 3), stingray.Vector2(4, 5))")
    check('a GUI used after its world went away is a crash', E.crashed and 'went away' in E.crashed, E.crashed)
    check('every engine call fails after a crash', not L.execute("return (pcall(stingray.Application.main_world))"))


BOOT_CRASH = r"""
local S = rawget(_G, 'stingray')
local first_world, gui
function init() end
function update(dt)
  local w = S.Application.main_world()
  if w and not gui then first_world, gui = w, S.World.create_screen_gui(w, 'immediate') end
  if gui then S.Gui.rect(gui, S.Vector3(10, 10, 100), S.Vector2(80, 40), S.Color(255, 200, 40, 40)) end
end
function shutdown() end
"""


def test_runner_crash():
    tmp = tempfile.mkdtemp(prefix='harness_selftest_')
    try:
        os.makedirs(os.path.join(tmp, 'mod', 'core'))
        archive.write_lua_patch(os.path.join(tmp, 'mod', 'core', runner.PATCH_NAME + '0'), [(runner.BOOT_ID, BOOT_CRASH)])
        s = Scenario('selftest_crash')
        s.screen(640, 360).run(seconds=3, fps=10)
        s.world('first', at=0.0, filler=10)
        s.world('second', at=1.5, filler=10)     # the first world goes away: the boot's GUI is now dangling
        s.render_frames(5)
        r = runner.Runner(os.path.join(tmp, 'mod'), ['core'], s, os.path.join(tmp, 'out'), verbose=False)
        res, rep = r.run()
        check('the runner aborts on a crash, in the right frame', rep['aborted'] and rep['crash'] and rep['crash']['frame'] == 15,
              rep['aborted'])
        check('drawing worked before it', rep['counts'][4][rep['counts_keys'].index('main_rect') + 1] == 1)
        check('the crash comes with a Lua traceback', 'boot:8' in (rep['crash'] or {}).get('traceback', ''),
              (rep['crash'] or {}).get('traceback', '').replace(chr(10), ' | '))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    test_engine()
    test_runner_crash()
    bad = [n for n, ok in results if not ok]
    print('%d/%d passed' % (len(results) - len(bad), len(results)))
    sys.exit(1 if bad else 0)
