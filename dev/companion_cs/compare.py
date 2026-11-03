#!/usr/bin/env python3
"""Runs companion.py / detect.py (the reference) and TreasureRadarCompanion.exe on the same frames and compares them.

    python -B dev/companion_cs/compare.py [--frames DIR ...] [--no-cold]

Each DIR holds PNGs and a frames.txt (name<TAB>mod line<TAB>old fix line). Default: dev/companion/fixtures and
%LOCALAPPDATA%\\Temp\\treasure_radar_frames. Frames are only read and never copied.

  cold     every frame in new processes: `--shot <png> --mod "<line>" --once --log` on both sides
  warm     all frames in one process per side, the variants below too; the running loop's speed
  seq      each folder through one tracker with the level gate, in order (mouse counts, priors, the gate)
  scaled   the frames pasted into a 2560x1440 screen for a 1920x1080 mod line (fixtures only; a temp folder)

Variants: as recorded; level=? kz=0; class=?; the mod one level off; no px,py; a near prior; a far prior.
A frame agrees when its fix line (without ts) matches; "strict" also wants the log line (without the ms) to match,
which holds the notes, candidate counts and dot offsets. Exit status 1 on any how/level/V problem.
"""
import argparse
import io
import os
import random
import re
import shutil
import statistics
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEV = os.path.dirname(HERE)
EXE = os.path.join(DEV, 'build', 'companion', 'TreasureRadarCompanion.exe')
PY = os.path.join(DEV, 'companion', 'companion.py')
PYLIB = os.path.join(DEV, 'tools', '_pylib')
V_TOL = 0.5

sys.path.insert(0, PYLIB)
sys.path.insert(0, os.path.dirname(PY))
from PIL import Image  # noqa: E402
import companion  # noqa: E402

MS = re.compile(r' [0-9.]+ms ')
TS = re.compile(r' ts=[0-9.]+')
LEVEL_KZ = {'-1': '0.7805', '0': '1.4766', '1': '2.953'}


def rows(folder):
    with open(os.path.join(folder, 'frames.txt'), encoding='utf-8') as f:
        for row in f:
            c = row.rstrip('\n').split('\t')
            if len(c) >= 2 and os.path.exists(os.path.join(folder, c[0])):
                yield os.path.join(folder, c[0]), c[1]


def sub(mod, **kw):
    for k, v in kw.items():
        if v is None:
            mod = re.sub(r' %s=\S+' % k, '', mod)
        else:
            mod = re.sub(r'\b%s=\S+' % k, '%s=%s' % (k, v), mod)
    return mod


def variants(png, mod, rng):
    level = re.search(r'level=(\S+)', mod).group(1)
    yield 'recorded', png, mod, ''
    yield 'level?', png, sub(mod, level='?', kz='0'), ''
    yield 'class?', png, sub(mod, **{'class': '?'}), ''
    off = {'0': '1', '1': '0', '-1': '0'}.get(level, '0')
    yield 'level off', png, sub(mod, level=off, kz=LEVEL_KZ[off]), ''
    yield 'no pos', png, sub(mod, px=None, py=None), ''
    yield 'near prior', png, mod, '%.1f,%.1f,%.1f' % (rng.uniform(-300, 300), rng.uniform(-300, 300), rng.uniform(1, 15))
    yield 'far prior', png, mod, '%.1f,%.1f,40' % (rng.uniform(-300, 300), rng.uniform(-300, 300))


def py_batch(items, sequence):
    """(log line + fix line, or idle text) per row, plus the detector ms, in this process"""
    out, ms = [], []
    tr = companion.Tracker()
    prev, prev_seq = None, 0
    for it in items:
        png, mod, prior = it[-3], it[-2], it[-1]
        m = companion.parse_line(mod)
        if sequence:
            sq = int(float(m.get('seq', 0)))
            was_open = prev is not None and prev.get('open') == '1'
            if prev is None or sq < prev_seq or m.get('open') != '1' or not was_open:
                tr.reset()
            else:
                tr.add_counts(m, sq - prev_seq, prev)
            prev, prev_seq = m, sq
        else:
            tr.reset()
            if prior:
                p = companion.parse_prior(prior)
                tr.v = {'vx': p['vx'], 'vy': p['vy'], 'err': p['err'], 'level': None}
        why = companion.idle_reason(m)
        if why:
            tr.reset()
            out.append('idle: ' + why)
            continue
        line, fix, a, extra = companion.frame(companion.ShotGrabber(png), m, tr, gate=sequence)
        ms.append(a.ms)
        out.append('idle: ' + fix['note'] if line is None else companion.log_text(m, fix, a, extra) + '\n' + line)
    return out, ms


def cs_batch(items, sequence, tmp):
    lst = os.path.join(tmp, 'rows.txt')
    with open(lst, 'w', encoding='utf-8', newline='\n') as f:
        for it in items:
            f.write('%s\t%s\t%s\n' % (it[-3], it[-2], it[-1]))
    p = subprocess.run([EXE, '--seq' if sequence else '--batch', lst], capture_output=True, text=True, timeout=600)
    if p.returncode:
        raise SystemExit('exe failed: ' + p.stdout + p.stderr)
    out, ms, cur = [], [], None
    for row in p.stdout.splitlines():
        if row.startswith('idle: '):
            out.append(row)
        elif cur is None:
            cur = row
            ms.append(float(MS.search(row).group(0).strip()[:-2]))
        else:
            out.append(cur + '\n' + row)
            cur = None
    return out, ms


def fields(text):
    last = text.splitlines()[-1]
    if last.startswith('idle'):
        return {'idle': last}
    return {k: v for k, v in (t.split('=', 1) for t in last.split() if '=' in t) if k != 'ts'}


class Tally:
    def __init__(self):
        self.n = self.same = self.strict = self.problems = 0
        self.how = {}
        self.worst = 0.0

    def add(self, label, a, b):
        self.n += 1
        fa, fb = fields(a), fields(b)
        self.how[fa.get('how', 'idle')] = self.how.get(fa.get('how', 'idle'), 0) + 1
        if fa == fb:
            self.same += 1
        norm = lambda s: TS.sub('', MS.sub(' ', s))
        if norm(a) == norm(b):
            self.strict += 1
        elif fa == fb:
            print('  log differs: %s\n    py %s\n    cs %s' % (label, norm(a).splitlines()[0], norm(b).splitlines()[0]))
        if 'vx' in fa and 'vx' in fb:
            self.worst = max(self.worst, abs(float(fa['vx']) - float(fb['vx'])), abs(float(fa['vy']) - float(fb['vy'])))
        bad = (fa.get('how') != fb.get('how') or fa.get('level') != fb.get('level') or fa.get('idle') != fb.get('idle')
               or ('vx' in fa and 'vx' in fb and (abs(float(fa['vx']) - float(fb['vx'])) > V_TOL
                                                  or abs(float(fa['vy']) - float(fb['vy'])) > V_TOL)))
        if bad:
            self.problems += 1
        if fa != fb:
            print('  %s %s\n    py %s\n    cs %s' % ('PROBLEM' if bad else 'differs', label, a, b))

    def __str__(self):
        return ('%d frames: fix lines identical %d, log lines identical %d, how/level/V problems %d, largest V '
                'difference %.1f m; python how %s' % (self.n, self.same, self.strict, self.problems, self.worst, self.how))


def med(v):
    return '%.1f mean, %.1f median, %.1f max' % (statistics.mean(v), statistics.median(v), max(v)) if v else '-'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--frames', action='append')
    ap.add_argument('--no-cold', action='store_true')
    a = ap.parse_args()
    temp = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Temp', 'treasure_radar_frames')
    env = dict(os.environ, PYTHONPATH=PYLIB, PYTHONIOENCODING='utf-8')
    tmp = tempfile.mkdtemp(prefix='compare_')
    problems = 0
    for folder in a.frames or [os.path.join(DEV, 'companion', 'fixtures'), temp]:
        if not os.path.isdir(folder):
            print('%s: not there, skipped' % folder)
            continue
        print(folder)
        items = list(rows(folder))

        if not a.no_cold:
            t = Tally()
            pm, cm = [], []
            for png, mod in items:
                po = subprocess.run([sys.executable, '-B', PY, '--shot', png, '--mod', mod, '--once', '--log'],
                                    capture_output=True, text=True, env=env, timeout=120).stdout
                co = subprocess.run([EXE, '--shot', png, '--mod', mod, '--once', '--log'],
                                    capture_output=True, text=True, timeout=120).stdout
                t.add('cold ' + os.path.basename(png), po, co)
                for o, l in ((po, pm), (co, cm)):
                    m = MS.search(o)
                    if m:
                        l.append(float(m.group(0).strip()[:-2]))
            print(' cold   %s\n        detector ms: python %s; C# %s' % (t, med(pm), med(cm)))
            problems += t.problems

        rng = random.Random(11)
        rows_v = [v for png, mod in items for v in variants(png, mod, rng)]
        t = Tally()
        po, pm = py_batch(rows_v, False)
        co, cm = cs_batch(rows_v, False, tmp)
        for it, x, y in zip(rows_v, po, co):
            t.add('%s %s' % (it[0], os.path.basename(it[1])), x, y)
        if len(po) != len(co):
            print('  row counts differ', len(po), len(co))
            t.problems += 1
        print(' warm   %s\n        detector ms: python %s; C# %s' % (t, med(pm), med(cm)))
        problems += t.problems

        seq_rows = [(png, mod, '') for png, mod in items]
        t = Tally()
        po, _ = py_batch(seq_rows, True)
        co, _ = cs_batch(seq_rows, True, tmp)
        for it, x, y in zip(seq_rows, po, co):
            t.add('seq ' + os.path.basename(it[0]), x, y)
        print(' seq    %s' % t)
        problems += t.problems

        if folder == (a.frames or [os.path.join(DEV, 'companion', 'fixtures')])[0]:
            shots = []
            for i, (png, mod) in enumerate(items):
                geo = companion.detect.Geo.from_mod(companion.parse_line(mod))
                sx, sy = 2560 / 1920, 1440 / 1080
                im = Image.open(png).convert('RGB')
                box = (round(geo.box[0] * sx), round(geo.box[1] * sy), round(geo.box[2] * sx), round(geo.box[3] * sy))
                screen = Image.new('RGB', (2560, 1440))
                screen.paste(im.resize((box[2] - box[0], box[3] - box[1]), Image.LANCZOS), box[:2])
                name = os.path.join(tmp, 'screen%d.png' % i)
                screen.save(name)
                shots.append((name, mod, ''))
            t = Tally()
            po, _ = py_batch(shots, False)
            co, _ = cs_batch(shots, False, tmp)
            for it, x, y in zip(shots, po, co):
                t.add('scaled ' + os.path.basename(it[0]), x, y)
            print(' scaled %s' % t)
            problems += t.problems
            for s in shots:
                os.remove(s[0])
    shutil.rmtree(tmp, ignore_errors=True)
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
