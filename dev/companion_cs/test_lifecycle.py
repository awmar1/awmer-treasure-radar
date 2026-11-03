#!/usr/bin/env python3
"""Runs TreasureRadarCompanion.exe through its release behaviour, against a fake mod in a temporary folder. The game is
not started, and must not be running: the exit tests would wait for it.

    python -B dev/companion_cs/test_lifecycle.py

The live test captures the map-circle box of the primary screen into memory (no game window). Nothing is recorded,
except by the --record test, which uses a screenshot from dev/companion/fixtures. The folder is deleted at the end.
"""
import ctypes
import ctypes.wintypes as wt
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DEV = os.path.dirname(HERE)
EXE = os.path.join(DEV, 'build', 'companion', 'TreasureRadarCompanion.exe')
PY = os.path.join(DEV, 'companion', 'companion.py')
PYLIB = os.path.join(DEV, 'tools', '_pylib')
FIXTURES = os.path.join(DEV, 'companion', 'fixtures')
sys.path.insert(0, PYLIB)
from PIL import Image  # noqa: E402

MOD = ('seq=%d t=93.751 open=%d level=0 class=small w=1920 h=1080 cx=1674.0 cy=819.5 rim=222.0 kz=1.4766 '
       'px=22.0 py=27.0 mx=0 my=0 cmx=0 cmy=0 end\n')
fails = []


def check(what, ok, detail=''):
    print('%s  %s%s' % ('ok  ' if ok else 'FAIL', what, ' (%s)' % detail if detail else ''))
    if not ok:
        fails.append(what)


def write_mod(folder, seq, opened=1):
    path = os.path.join(folder, 'treasure_radar_mod.txt')
    with open(path, 'w', encoding='ascii', newline='\n') as f:
        f.write(MOD % (seq, opened))


class Writer(threading.Thread):
    """The mod: a new line at 30 Hz, for as long as it runs"""

    def __init__(self, folder, opened):
        super().__init__(daemon=True)
        self.folder, self.opened, self.seq, self.stop_it = folder, opened, 1, False

    def run(self):
        while not self.stop_it:
            try:
                write_mod(self.folder, self.seq, self.opened)
            except OSError:
                pass
            self.seq += 1
            time.sleep(1 / 30)


class PMC(ctypes.Structure):
    _fields_ = [('cb', wt.DWORD), ('faults', wt.DWORD)] + [(n, ctypes.c_size_t) for n in (
        'peak_ws', 'ws', 'a', 'b', 'c', 'd', 'e', 'f')]


def usage(p):
    c, e, k, u = wt.FILETIME(), wt.FILETIME(), wt.FILETIME(), wt.FILETIME()
    ctypes.windll.kernel32.GetProcessTimes(int(p._handle), ctypes.byref(c), ctypes.byref(e), ctypes.byref(k), ctypes.byref(u))
    t = lambda f: (f.dwHighDateTime << 32 | f.dwLowDateTime) / 1e7
    m = PMC()
    m.cb = ctypes.sizeof(PMC)
    ctypes.windll.psapi.GetProcessMemoryInfo(int(p._handle), ctypes.byref(m), m.cb)
    return t(k) + t(u), m.peak_ws / 1e6


def cpu_share(p, seconds):
    a = usage(p)[0]
    t = time.perf_counter()
    time.sleep(seconds)
    return 100 * (usage(p)[0] - a) / (time.perf_counter() - t)


def log_of(folder):
    with open(os.path.join(folder, 'treasure_radar_companion.log'), encoding='utf-8') as f:
        return f.read()


def wait_exit(p, limit):
    t = time.perf_counter()
    try:
        p.wait(limit)
        return time.perf_counter() - t
    except subprocess.TimeoutExpired:
        p.kill()
        p.wait()
        return None


def main():
    if subprocess.run(['tasklist', '/fi', 'imagename eq helldivers2.exe'], capture_output=True, text=True).stdout.lower().count('helldivers2'):
        raise SystemExit('the game is running: this test needs it gone')
    root = tempfile.mkdtemp(prefix='companion_test_')
    png = os.path.join(FIXTURES, sorted(n for n in os.listdir(FIXTURES) if n.endswith('.png'))[0])
    try:
        # one file cycle, the screenshot as the screen
        d = os.path.join(root, 'once')
        os.mkdir(d)
        write_mod(d, 7)
        r = subprocess.run([EXE, '--shot', png, '--dir', d, '--once'], capture_output=True, text=True, timeout=60)
        fix = os.path.join(d, 'treasure_radar_fix.txt')
        raw = open(fix, 'rb').read() if os.path.exists(fix) else b''
        check('--once writes one fix line, ASCII, \\n only', raw.startswith(b'seq=7 ts=') and raw.endswith(b' end\n') and raw.count(b'\n') == 1 and b'\r' not in raw, raw.decode('ascii', 'replace').strip())
        check('no .tmp left behind', not os.path.exists(fix + '.tmp'))
        check('no frames folder without --record', not os.path.exists(os.path.join(d, 'treasure_radar_frames')))
        check('the log says frames are not recorded', 'frames: not recorded' in log_of(d))

        # --record, and that the PNG holds the capture's exact pixels
        d = os.path.join(root, 'record')
        os.mkdir(d)
        write_mod(d, 8)
        subprocess.run([EXE, '--shot', png, '--dir', d, '--once', '--record'], capture_output=True, text=True, timeout=60)
        fd = os.path.join(d, 'treasure_radar_frames')
        saved = [n for n in os.listdir(fd) if n.endswith('.png')] if os.path.isdir(fd) else []
        check('--record keeps the frame', len(saved) == 1, ', '.join(saved))
        if saved:
            a = Image.open(os.path.join(fd, saved[0])).convert('RGB')
            b = Image.open(png).convert('RGB')
            check('the recorded PNG is the same pixels', a.size == b.size and a.tobytes() == b.tobytes())
            row = open(os.path.join(fd, 'frames.txt'), encoding='utf-8').read().rstrip('\n').split('\t')
            check('frames.txt: name, mod line, fix line', len(row) == 3 and row[0] == saved[0] and row[1] == (MOD % (8, 1)).strip() and row[2].startswith('seq=8 '))

        # a stale leftover file gets no frame
        d = os.path.join(root, 'stale')
        os.mkdir(d)
        write_mod(d, 9)
        os.utime(os.path.join(d, 'treasure_radar_mod.txt'), (time.time() - 3600, time.time() - 3600))
        subprocess.run([EXE, '--shot', png, '--dir', d, '--once'], capture_output=True, text=True, timeout=60)
        check('an hour-old mod file counts as stale', 'mod line stale' in log_of(d) and not os.path.exists(os.path.join(d, 'treasure_radar_fix.txt')))

        # the game never appears
        d = os.path.join(root, 'nogame')
        os.mkdir(d)
        p = subprocess.Popen([EXE, '--dir', d, '--grace-start', '3', '--grace-gone', '2'])
        t = wait_exit(p, 20)
        check('exits when the game does not appear (grace 3 s)', t is not None and 2.5 < t < 6, 'after %s s' % (t and round(t, 1)))
        check('... and says why', 'the game did not appear' in log_of(d))

        # the live loop: active, a second instance, closing the map, the mod stopping
        d = os.path.join(root, 'live')
        os.mkdir(d)
        w = Writer(d, 1)
        w.start()
        p = subprocess.Popen([EXE, '--dir', d, '--grace-start', '60', '--grace-gone', '3'])
        time.sleep(2)
        fix = os.path.join(d, 'treasure_radar_fix.txt')
        seqs, torn = [], 0
        t0 = time.perf_counter()
        last = None
        while time.perf_counter() - t0 < 4:
            try:
                s = open(fix, encoding='ascii').read()
                if s != last:
                    last = s
                    if s.endswith(' end\n'):
                        seqs.append(int(s.split()[0][4:]))
                    else:
                        torn += 1
            except OSError:
                pass
            time.sleep(0.003)
        rate = len(seqs) / 4
        check('fixes follow the mod while open', rate > 15 and seqs and w.seq - seqs[-1] < 15, '%.1f fixes/s, mod at seq %d, last fix %d' % (rate, w.seq, seqs[-1] if seqs else -1))
        check('no partial fix file seen', torn == 0, '%d torn' % torn)
        cpu = cpu_share(p, 5)
        active_mem = usage(p)[1]
        print('      active, capturing at 30 Hz: %.1f%% of one core, peak working set %.0f MB' % (cpu, active_mem))
        q = subprocess.Popen([EXE, '--dir', d, '--grace-start', '60'])
        t = wait_exit(q, 10)
        check('a second instance leaves at once', t is not None and t < 3 and q.returncode == 0, 'after %s s' % (t and round(t, 2)))
        check('... and the first one still runs', p.poll() is None)
        check('... with its log kept', 'waiting for the mod' in log_of(d))
        w.opened = 0
        time.sleep(0.5)
        before = os.path.getmtime(fix)
        time.sleep(2)
        check('no capture and no fix while the map is closed', os.path.getmtime(fix) == before)
        cpu = cpu_share(p, 8)
        print('      idle (map closed, mod writing): %.2f%% of one core' % cpu)
        w.stop_it = True
        w.join()
        t = wait_exit(p, 30)
        check('exits when the game has gone (grace 3 s)', t is not None and t < 12, 'after %s s' % (t and round(t, 1)))
        text = log_of(d)
        check('the log holds the map-open summary and the reason', 'map open done' in text and 'the game has been gone' in text)
        print('      the log, %d bytes:\n%s' % (len(text), ''.join('        ' + x + '\n' for x in text.splitlines())), end='')
        check('the folder holds only the expected files', sorted(os.listdir(d)) == ['treasure_radar_companion.log', 'treasure_radar_fix.txt', 'treasure_radar_mod.txt'], ', '.join(sorted(os.listdir(d))))

        # the same two numbers for the Python companion, whose frames go to this temporary folder
        d = os.path.join(root, 'python')
        os.mkdir(d)
        w = Writer(d, 1)
        w.start()
        env = dict(os.environ, PYTHONPATH=PYLIB)
        p = subprocess.Popen([sys.executable, '-B', PY, '--dir', d], env=env, stdout=subprocess.DEVNULL)
        time.sleep(3)
        cpu = cpu_share(p, 5)
        print('      python, active: %.1f%% of one core, peak working set %.0f MB' % (cpu, usage(p)[1]))
        w.opened = 0
        time.sleep(1)
        print('      python, idle: %.2f%% of one core' % cpu_share(p, 8))
        w.stop_it = True
        w.join()
        p.terminate()
        p.wait()
    finally:
        shutil.rmtree(root, ignore_errors=True)
    print('failed: %s' % fails if fails else 'all passed')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
