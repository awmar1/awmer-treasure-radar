"""0.8 measurement build (Ammar Treasure Radar 0.8.0-measure): the ship with the kind that crashed the game made
fragile, then a mission, standing 40 m east of the world origin (as in the 0.7.0 run). The PLAN_0.8.md section 4
routine, with the limits pushed: F12 closed; Tab; F12; the mouse halfway right, F12; pushed into the rim and on past it,
F12; out two notches (one past the limit) and in three (one past), F12 at the bottom and the top; the mouse up-left; a
left and a right click; Tab closes it, F12. The logger may only read what the mod already has: nothing may touch the
fragile kind. Its numbers are read back from treasure_radar_measure08.txt (the path the "measure: on" line gives).

Run:  python -I dev/harness/run.py --mod <a build of builds/0.8.0-measure.json> --scenario measure08 --options core
"""
import re

FILE_RE = r"measure: on; F12 logs a snapshot \(and takes Steam's screenshot\) to (.+?); untick"
CUR_R = 0.183                   # the game's cursor stops this far from the map's centre (of the screen height)


def records(r):
    """The measure file's lines as (t, tag, {key: value}), and its '#' lines; ([], []) when it can't be read."""
    m = re.search(FILE_RE, r.log)
    if not m:
        return [], []
    try:
        with open(m.group(1), encoding='utf-8') as f:
            text = f.read()
    except OSError:
        return [], []
    recs, notes = [], []
    for ln in text.splitlines():
        if ln.startswith('#'):
            notes.append(ln)
            continue
        p = ln.split(' ')
        if len(p) < 2:
            continue
        kv = dict(x.split('=', 1) for x in p[2:] if '=' in x)
        recs.append((float(p[0]), p[1], kv))
    return recs, notes


def of(r, tag):
    return [(t, kv) for t, g, kv in records(r)[0] if g == tag]


def num(kv, key):
    return float(kv[key])


def build(s):
    s.screen(1920, 1080).run(seconds=15, fps=30)
    s.world('ship', at=0.0, until=3.0, filler=2250, spread=150, seed=5)
    s.kind('ship_fragile', '46cab355bd8d4d37', group='ship')
    s.fragile('ship_fragile')
    s.unit('ship_fragile', 1, 3, world='ship', label='the kind that crashed the game')

    s.world('mission', at=3.0, filler=6000, spread=450, seed=7)
    s.world('hud_a', at=3.0, main=False)
    s.kind('fabricator', 'a57ae2a703c02899', group='structure')
    s.kind('bug_hole_medium', 'a83587cbff25c79e', group='nest')
    s.unit('fabricator', -40, -30)
    s.unit('bug_hole_medium', -50, 60)
    s.unit('medal', 46, 28)
    s.unit('rare', 65, 10)
    s.ring('common', 3, 1.0, cx=70, cy=45)

    s.camera(0.0, 40, 0, 1.8, yaw=20, pitch=-6)
    s.camera(15.0, 40, 0, 1.8, yaw=20, pitch=-6)
    s.cursor(0.0, 960, 540)

    s.press('f12', 2.0)          # on the ship: idle, nothing logged
    s.press('f12', 6.5)          # the mission (it counts as one from 6 s), the map closed
    s.map_open(7.0, 12.0)        # Tab at 7 and 12
    s.press('f12', 7.3)          # 1. open, unpanned
    s.raw_mouse(7.5, 8.0, 30, 0)     # 2. halfway right: 450 counts (95 px at 0.21)
    s.press('f12', 8.1)
    s.raw_mouse(8.2, 9.0, 40, 0)     # 3. into the rim and on: 960 more counts, the cursor stops at 0.183 h
    s.press('f12', 9.05)
    s.wheel(9.3, -1)             # 5. out to -1, then once more (stays at -1)
    s.wheel(9.6, -1)
    s.press('f12', 9.75)
    s.wheel(9.9, 1)              # in to 0, +1, then once more (stays at +1)
    s.wheel(10.2, 1)
    s.wheel(10.5, 1)
    s.press('f12', 10.65)
    s.raw_mouse(10.8, 11.2, -30, -20)  # up-left, off the rim
    s.click('left', 11.4)        # 6. the clicks
    s.click('right', 11.6)
    s.press('f12', 12.4)         # closed again
    s.render_frames('6.9s', '7.6s', '9.5s', '13.0s')

    s.check('the loader started the addon', lambda r: r.log_has(r'started mods/chef/treasure_radar 0\.8\.\d'))
    s.check('the logger is on, with its file', lambda r: (r.log_has(FILE_RE), '; '.join(r.log_lines(r'measure: on'))))
    s.check('no engine crash (the fragile kind untouched)',
            lambda r: (r.crashed is None, str(r.crashed and r.crashed['message'])))
    s.check('no frame errors', lambda r: not r.log_has(r'frame error|ERROR in'))
    s.check('nothing logged on the ship', lambda r: (not r.log_has(r'measure: SNAPSHOT \d+ at [0-5]\.'),
                                                     '; '.join(r.log_lines(r'SNAPSHOT'))))
    s.check('the mission header: screen and map circle',
            lambda r: r.log_has(r'measure: new mission') and r.log_has(r'measure:   screen 1920x1080; the map circle'))
    s.check('seven snapshots in the mission', lambda r: (len(r.log_lines(r'measure: SNAPSHOT \d+')) == 7,
                                                         '; '.join(r.log_lines(r'SNAPSHOT'))))
    s.check('Tab opens the map (key mode)', lambda r: r.log_has(r'measure: map open at [\d.]+ s \(open 1, key mode\)'))
    s.check('five notches, clamped to -1..+1',
            lambda r: (re.findall(r'measure: zoom ([+-]1) notch -> level ([+-]?\d+)', r.log) ==
                       [('-1', '-1'), ('-1', '-1'), ('+1', '+0'), ('+1', '+1'), ('+1', '+1')],
                       '; '.join(r.log_lines(r'measure: zoom'))))
    s.check('the close line', lambda r: (r.log_has(r'measure: map closed after [\d.]+ s: \+1 notches, level \+1'),
                                         '; '.join(r.log_lines(r'map closed'))))

    # the file
    def header(r):
        recs, notes = records(r)
        m = of(r, 'mission')
        ok = bool(notes) and re.match(r'# Ammar Treasure Radar 0\.8\.\d\S* measure log, format 1', notes[0]) \
            and len(m) == 1 and m[0][1]['w'] == '1920' and m[0][1]['h'] == '1080'
        return bool(ok), '%d records; %s; %s' % (len(recs), notes[:1], m[:1])
    s.check('the file: its header and one mission line', header)

    def path(r):
        p = of(r, 'path')
        t = [x[0] for x in p]
        opened = [kv for _, kv in p if kv['open'] == '1']
        ok = len(p) >= 60 and min(t) >= 6.0 and 40 <= len(opened) <= 55 \
            and all(abs(num(kv, 'x') - 40) < 0.01 for _, kv in p)
        return ok, '%d path lines from %.2f to %.2f s, %d with the map open' % (len(p), min(t or [0]), max(t or [0]),
                                                                              len(opened))
    s.check('the file: the path at 10 Hz from the mission on', path)

    def open_close(r):
        o, c = of(r, 'open'), of(r, 'close')
        ok = len(o) == 1 and len(c) == 1 and o[0][1]['n'] == '1' and o[0][1]['lv'] == '0' \
            and c[0][1]['notches'] == '1' and c[0][1]['lv'] == '1' and num(c[0][1], 'mx') == 1410 - 360 \
            and num(c[0][1], 'my') == -240 and abs(num(c[0][1], 'dur') - 5.0) < 0.1
        return ok, 'open %s; close %s' % (o, c)
    s.check('the file: the open and close lines (1410 counts right, then 360 left and 240 up)', open_close)

    def zoom(r):
        z = [(kv['d'], kv['mlv']) for _, kv in of(r, 'zoom')]
        return z == [('-1', '-1'), ('-1', '-1'), ('+1', '0'), ('+1', '1'), ('+1', '1')], str(z)
    s.check('the file: the notches, its own level clamped', zoom)

    def cursor(r):
        o = of(r, 'open')
        ms = [(t, kv) for t, kv in of(r, 'mouse')]
        if not o or not ms:
            return False, 'no open or mouse lines'
        cx, cy = num(o[0][1], 'cx'), num(o[0][1], 'cy')
        stop = CUR_R * 1080
        push = [num(kv, 'curx') - cx for t, kv in ms if 8.2 <= t <= 9.05]
        half = [num(kv, 'curx') - cx for t, kv in ms if 8.0 <= t <= 8.15]
        last = ms[-1][1]
        ux, uy = num(last, 'curx') - cx, num(last, 'cury') - cy
        ok = bool(push) and bool(half) and abs(max(push) - stop) < 1.0 and abs(push[-1] - stop) < 1.0 \
            and 80 < half[-1] < 110 and ux < stop - 50 and uy > 30
        return ok, 'halfway %+.1f px, pushed %+.1f px (stop %.1f), after up-left %+.1f,%+.1f px; %d mouse lines' % (
            half[-1] if half else 0, max(push or [0]), stop, ux, uy, len(ms))
    s.check('the file: the cursor model moves, stops at 0.183 h, and comes back (up is +y)', cursor)

    def clicks(r):
        c = [(kv['b'], kv['down']) for _, kv in of(r, 'click')]
        return c == [('left', '1'), ('left', '0'), ('right', '1'), ('right', '0')], str(c)
    s.check('the file: both clicks, down and up', clicks)

    def snaps(r):
        sn = of(r, 'snap')
        me = of(r, 'snap.me')
        loot = of(r, 'snap.loot')
        lv = [(kv['open'], kv['lv']) for _, kv in sn]
        m = of(r, 'mission')
        ok = len(sn) == 7 and len(me) == 7 and bool(m) and abs(num(sn[0][1], 'cx') - num(m[0][1], 'cx')) < 0.1             and num(m[0][1], 'cx') > 1000 and len(loot) >= 7 and min(t for t, _ in sn) >= 6.0 \
            and [o for o, _ in lv] == ['0', '1', '1', '1', '1', '1', '0'] and lv[4][1] == '-1' and lv[5][1] == '1' \
            and len(set(kv['n'] for _, kv in sn)) == 7
        return ok, '%d snaps (open, lv) %s; %d me, %d loot lines' % (len(sn), lv, len(me), len(loot))
    s.check('the file: seven snapshots with me and the loot', snaps)

    def snap_spot(r):
        # unpanned at level 0: the model puts me 40 m east of the centre, 1.4766 px/m
        sn = dict((kv['n'], kv) for _, kv in of(r, 'snap'))
        me = [kv for _, kv in of(r, 'snap.me')]
        if len(me) < 2:
            return False, 'no snap.me lines'
        kv, s0 = me[1], sn.get(me[1]['n'], {})
        dx = num(kv, 'sx') - num(s0, 'cx')
        dy = num(kv, 'sy') - num(s0, 'cy')
        return abs(dx - 40 * 1.4766) < 1.0 and abs(dy) < 0.5, 'me at %+.1f,%+.1f px from the centre' % (dx, dy)
    s.check('the file: the open snapshot puts me 59 px right of the centre', snap_spot)

    # the drawing (the loader puts layer TOP + n at n + 1000 in the top world)
    def ring(r):
        ring_n = r.count('7.6s', world='top', layer=(1950, 1950))
        cross_n = r.count('7.6s', world='top', layer=(1951, 1951))
        closed = r.count('13.0s', world='top', layer=(1950, 1959))
        main = r.count('13.0s', world='main', layer=(1950, 1959))
        return bool(ring_n) and cross_n == 4 and not closed and not main, \
            'open: ring %s, cross %s; closed: %s top, %s main' % (ring_n, cross_n, closed, main)
    s.check('the ring and the cross on the open map only', ring)

    def note(r):
        n = r.count('6.9s', world='main', layer=(995, 995))
        top = r.count('9.5s', world='top', layer=(1979, 1979))
        after = r.count('13.0s', world='main', layer=(995, 995))
        return bool(n) and bool(top) and bool(after), 'note draws: closed %s, open %s, closed again %s' % (n, top,
                                                                                                         after)
    s.check('the MEASURE n LOGGED note shows, on the open map too', note)
