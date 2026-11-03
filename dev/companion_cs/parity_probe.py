#!/usr/bin/env python3
"""Checks the Pil class in Detect.cs byte for byte against PIL, on random, gradient and flat images.

    PYTHONPATH=dev/tools/_pylib python -B dev/companion_cs/parity_probe.py

Builds a small probe exe in a temporary folder. Nothing stays in the repo.
"""
import os
import random
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
CSC = os.path.join(os.environ['WINDIR'], 'Microsoft.NET', 'Framework64', 'v4.0.30319', 'csc.exe')


def images(n, rng):
    yield 'noise', bytes(rng.randrange(256) for _ in range(n * n * 3))
    yield 'flat', bytes([200, 30, 90]) * (n * n)
    # saturated blocks, the case that decides the >= 254 erosion
    b = bytearray(n * n * 3)
    for _ in range(max(3, n // 8)):
        c = [rng.randrange(256) for _ in range(3)]
        x, y, w, h = rng.randrange(n), rng.randrange(n), rng.randrange(1, 40), rng.randrange(1, 40)
        for j in range(y, min(n, y + h)):
            for i in range(x, min(n, x + w)):
                b[(j * n + i) * 3:(j * n + i) * 3 + 3] = bytes(c)
    yield 'blocks', bytes(b)


def main():
    rng = random.Random(7)
    tmp = tempfile.mkdtemp(prefix='parity_')
    exe = os.path.join(tmp, 'probe.exe')
    subprocess.check_call([CSC, '/nologo', '/optimize+', '/out:' + exe, '/r:System.Numerics.dll', '/r:System.Core.dll',
                           os.path.join(HERE, 'parity_probe.cs'), os.path.join(HERE, 'Detect.cs')])
    p = lambda name: os.path.join(tmp, name)
    run = lambda *a: subprocess.check_call([exe] + [str(x) for x in a])
    read = lambda name: open(p(name), 'rb').read()
    fails = 0
    done = {}

    def check(kind, label, mine, theirs):
        nonlocal fails
        done[kind] = done.get(kind, 0) + 1
        if mine != theirs:
            fails += 1
            d = sum(x != y for x, y in zip(mine, theirs)) if len(mine) == len(theirs) else -1
            print('DIFF %s %s: %d of %d bytes' % (kind, label, d, len(theirs)))

    # every 16-bit-ish colour step for the conversions
    all_rgb = bytes(v for r in range(0, 256, 3) for g in range(0, 256, 3) for b in range(0, 256, 3) for v in (r, g, b))
    k = len(all_rgb) // 3
    open(p('c.rgb'), 'wb').write(all_rgb)
    run('hsv', p('c.rgb'), p('c.hsv'))
    check('hsv', 'cube', read('c.hsv'), Image.frombytes('RGB', (k, 1), all_rgb).convert('HSV').tobytes())
    run('l', p('c.rgb'), p('c.l'))
    check('l', 'cube', read('c.l'), Image.frombytes('RGB', (k, 1), all_rgb).convert('L').tobytes())

    for n in (5, 16, 33, 444, 593, 889):
        for label, raw in images(n, rng):
            im = Image.frombytes('RGB', (n, n), raw)
            open(p('i.rgb'), 'wb').write(raw)
            run('hsv', p('i.rgb'), p('o.hsv'))
            check('hsv', '%s %d' % (label, n), read('o.hsv'), im.convert('HSV').tobytes())
            g = im.convert('L')
            open(p('i.l'), 'wb').write(g.tobytes())
            for rad in (1, 2, 3, 4, 6, 12, 40):
                run('blur', p('i.l'), n, rad, p('o.l'))
                check('blur', '%s n=%d r=%d' % (label, n, rad), read('o.l'), g.filter(ImageFilter.BoxBlur(rad)).tobytes())
            for out in ((444, 444), (n + 1, n + 1), (max(1, n // 2), max(1, n // 2)), (n, n + 3)):
                run('resize', p('i.rgb'), n, n, out[0], out[1], p('o.rgb'))
                check('resize', '%s %d->%s' % (label, n, out), read('o.rgb'), im.resize(out, Image.BILINEAR).tobytes())

    for n in (444, 593, 889, 300, 665):
        for _ in range(60):
            r = rng.uniform(n * 0.2, n * 0.6)
            cx, cy = n / 2 + rng.uniform(-3, 3), n / 2 + rng.uniform(-3, 3)
            if rng.random() < 0.3:
                cx, cy = round(cx * 2) / 2, round(cy * 2) / 2
            box = (cx - r, cy - r, cx + r, cy + r)
            m = Image.new('L', (n, n), 0)
            ImageDraw.Draw(m).ellipse(box, fill=255)
            run('ellipse', n, *[repr(v) for v in box], p('o.l'))
            check('ellipse', 'n=%d box=%s' % (n, box), read('o.l'), m.tobytes())

    vals = [rng.uniform(-400, 400) for _ in range(4000)] + [x / 2 for x in range(-40, 40)] + [x / 20 for x in range(-200, 200)]
    vals += [0.25, 0.35, 0.05, 0.15, 2.675, 1.0005, 1793414825.0675, 1e-7, 1e12]
    open(p('v.txt'), 'w').write('\n'.join(repr(v) for v in vals) + '\n')
    run('fmt', p('v.txt'), p('o.txt'))
    mine = open(p('o.txt')).read()
    check('fmt', 'values', mine.encode(), ''.join('%.0f %.1f %.3f\n' % (v, v, v) for v in vals).encode())

    print('checks: %s; differences: %d' % (done, fails))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
