"""Treasure Radar companion: the map-circle detector.

Pixels only. The input is a PIL RGB image of the square [cx - rim, cy - rim, cx + rim, cy + rim] of the screen
(crop_box) plus the geometry the mod sends in its line (dev/docs/COMPANION_INTERFACE.md). It produces:

- find_dots(): the solid map discs in the slot colours. The player's own icon is a yellow disc, 12-13 px across at
  1080p, with a dark outline and a translucent view cone in the same colour. Each candidate gets a shape test and a
  cone test. 1.2: a yellow blob that fails the shape test (the disc partly under another icon, or merged with a
  yellow one) gets a fixed-radius circle fit, and the cone test at the fitted centre.
- measure_grid(): the 65 m grid's cell (px) and phase on both axes, and so the zoom level.
- solve(): the view centre V. It comes from the dot (the mod knows the player's world position), refined by the grid
  phase, or else from the grid phase unwrapped around a prior prediction. It carries an error estimate in metres.

Only PIL and the standard library. PIL's C code does the heavy lifting (HSV, point tables, BoxBlur, channel
maths). The Python loops touch only the few hundred pixels of each candidate and the 1-D grid profiles.
"""
import math
import re
import time
from array import array

from PIL import Image, ImageChops, ImageDraw, ImageFilter

GRID_M = 65.0
# px per metre at 1080p with the HUD the mod lays out for (rim 222 px); dev/docs/RESEARCH_MAP.md
KZ_1080 = {(-1, 'small'): 0.7805, (-1, 'big'): 0.554, (0, None): 1.4766, (1, None): 2.953}
GAIN = {-1: 0.269, 0: 0.246, 1: 0.123}            # metres per raw mouse count (the interface)
R_MAP = {'small': 285.3, 'big': 400.7}            # map radius in metres (the view clamps at R - rim/kz per axis)
RIM_1080 = 222.0
# the grid cells the game shows, 1080p px: (cell, level, class)
CELLS_1080 = [(GRID_M * 0.554, -1, 'big'), (GRID_M * 0.7805, -1, 'small'),
              (GRID_M * 1.4766, 0, None), (GRID_M * 2.953, 1, None)]

# Slot colours, PIL HSV (all 0..255): name, hue lo, hue hi, S min, V min, prior weight.
# Yellow is measured on the user's screenshots (the own icon is about #ffe600: H 38, S 255, V 255). The others are
# best effort (teammate discs were seen in orange, green and blue). They are only taken with a view cone, which
# teammates do not show, and only near the prior prediction.
BANDS = [
    ('yellow', 30, 46, 170, 200, 1.0),
    ('orange', 14, 27, 170, 200, 0.35),
    ('green', 62, 110, 120, 160, 0.35),
    ('blue', 118, 175, 120, 160, 0.35),
    ('pink', 195, 245, 100, 170, 0.35),
]
CONE_S_MIN, CONE_V = 90, (40, 199)    # cone pixels: the band's hue +- CONE_HUE_PAD, S >= 90, 40 <= V <= 199
# 1.2: the cone's hue is the band's own. 1.1 widened it by 4, and the orange terrain of the 2026-10-27 mission
# (H 24-26, S 231-255, V 100-110) then filled every sector round the disc: the cone's concentration fell to
# 0.01-0.41 and the test threw the player's icon away on 14 of the recorded frames. With no widening those frames
# measure 0.90-0.93 and the screenshot table 0.79-0.95 (it was 0.72-0.94); the cone over that terrain is H 37-38
CONE_HUE_PAD = 0
DOT_D_1080 = 12.5                     # the icon's diameter, px at 1080p
# 1.2, the partial disc: a yellow blob that fails the shape test but holds at least PART_MIN of the disc's area is
# fitted with a circle of the icon's radius (votes from its edge pixels); the fit counts when at least PART_EDGE of
# that circle's rim is on the blob's edge and the view cone is at the fitted centre. Its fix carries PART_ERR m
PART_MIN, PART_EDGE, PART_ERR = 0.30, 0.30, 2.5


def _odd(v):
    v = int(round(v))
    return v if v % 2 else v + 1


def crop_box(cx, cy, rim):
    """The capture square in integer screen px: (x0, y0, x1, y1), with x1 and y1 exclusive."""
    n = int(math.floor(2 * rim + 0.5))
    x0 = int(math.floor(cx - rim + 0.5))
    y0 = int(math.floor(cy - rim + 0.5))
    return (x0, y0, x0 + n, y0 + n)


def kz_theory(level, cls, sc):
    """px/m for a level (and the class at -1) at pixel scale sc (= rim / 222)."""
    k = KZ_1080.get((level, cls if level == -1 else None))
    return k * sc if k else None


class Geo:
    """The mod line's geometry, plus what the detector derives from it."""

    def __init__(self, cx, cy, rim, h=1080, kz=0.0, level=None, cls=None):
        self.cx, self.cy, self.rim, self.h = float(cx), float(cy), float(rim), float(h)
        self.kz, self.level, self.cls = float(kz or 0), level, cls
        self.box = crop_box(self.cx, self.cy, self.rim)
        self.x0, self.y0 = self.box[0], self.box[1]
        self.n = self.box[2] - self.box[0]
        self.sc = self.rim / RIM_1080 if self.rim > 0 else self.h / 1080.0
        self.ccx = self.cx - self.x0          # the circle centre inside the crop
        self.ccy = self.cy - self.y0

    @classmethod
    def from_mod(cls, m):
        def num(k, d=0.0):
            try:
                return float(m.get(k, d))
            except (TypeError, ValueError):
                return d
        lv = m.get('level')
        lv = int(lv) if lv in ('-1', '0', '1') else None
        c = m.get('class')
        c = c if c in ('small', 'big') else None
        return cls(num('cx'), num('cy'), num('rim'), num('h', 1080), num('kz'), lv, c)


# ---------------------------------------------------------------------------------------------------- caches
_cache = {}


def _lut_band(lo, hi, val=255):
    return [val if lo <= v <= hi else 0 for v in range(256)]


def _lut_ge(t):
    return [255 if v >= t else 0 for v in range(256)]


def _lut_range(lo, hi):
    return [255 if lo <= v <= hi else 0 for v in range(256)]


def _group_luts(strict):
    """One mask per threshold group: H -> band code, S >= smin, V >= vmin (the strict group is yellow and orange)."""
    key = ('group', strict)
    luts = _cache.get(key)
    if luts is None:
        hl = [0] * 256
        smin = vmin = 255
        for i, (_name, lo, hi, s, v, _w) in enumerate(BANDS):
            if (s >= 170) != strict:
                continue
            for h in range(max(0, lo), min(255, hi) + 1):
                hl[h] = 40 * (i + 1)
            smin, vmin = min(smin, s), min(vmin, v)
        luts = (hl, _lut_ge(smin), _lut_ge(vmin))
        _cache[key] = luts
    return luts


def _cone_luts(i):
    luts = _cache.get(('cone', i))
    if luts is None:
        _name, lo, hi, _s, _v, _w = BANDS[i]
        luts = (_lut_band(lo - CONE_HUE_PAD, hi + CONE_HUE_PAD), _lut_ge(CONE_S_MIN), _lut_range(*CONE_V))
        _cache[('cone', i)] = luts
    return luts


def _circle_mask(n, ccx, ccy, r):
    key = ('circ', n, round(ccx, 2), round(ccy, 2), round(r, 2))
    m = _cache.get(key)
    if m is None:
        m = Image.new('L', (n, n), 0)
        ImageDraw.Draw(m).ellipse((ccx - r, ccy - r, ccx + r, ccy + r), fill=255)
        _cache[key] = m
    return m


# ---------------------------------------------------------------------------------------------------- dots
class Dot:
    # fit: 'whole' (passed the shape test; x, y the blob's centroid), 'part' (failed it, but a circle of the icon's
    # radius fits part of its edge; x, y the fitted centre, edge the share of that circle's rim found), or None
    __slots__ = ('band', 'prior', 'x', 'y', 'dx', 'dy', 'r', 'n', 'bw', 'bh', 'fill', 'core', 'cone', 'conc',
                 'cone_dir', 'shape_ok', 'why', 'score', 'fit', 'edge')

    def __repr__(self):
        fit = (' part %.0f%%' % (100 * self.edge)) if self.fit == 'part' else ''
        return ('Dot(%s %+.1f,%+.1f n=%d %dx%d fill=%.2f core=%d cone=%d/%.2f %s%s)'
                % (self.band, self.dx, self.dy, self.n, self.bw, self.bh, self.fill, self.core, self.cone, self.conc,
                   'ok' if self.shape_ok else self.why, fit))


def _flood(p0, code, cd, seen, n, limit):
    """The 8-connected pixels of one band code from p0 (at most limit kept). Returns (pixels, too_big)."""
    stack = [p0]
    seen[p0] = 1
    comp = []
    nn = n * n
    last = n - 1
    while stack:
        q = stack.pop()
        if len(comp) < limit:
            comp.append(q)
        qx = q % n
        if qx == 0:
            nb = (q - n, q + n, q - n + 1, q + 1, q + n + 1)
        elif qx == last:
            nb = (q - n, q + n, q - n - 1, q - 1, q + n - 1)
        else:
            nb = (q - n, q + n, q - n - 1, q - 1, q + n - 1, q - n + 1, q + 1, q + n + 1)
        for r in nb:
            if 0 <= r < nn and not seen[r] and cd[r] == code:
                seen[r] = 1
                stack.append(r)
    return comp, len(comp) >= limit


def find_dots(img, geo, hsv=None):
    """Solid discs in the slot colours, as a list of Dot (shape_ok says whether it passed the shape test)."""
    n, sc = geo.n, geo.sc
    if hsv is None:
        hsv = img.convert('HSV')
    H, S, V = hsv.split()
    D = DOT_D_1080 * sc
    area = math.pi / 4 * D * D
    coded = None
    for strict in (True, False):
        hl, sl, vl = _group_luts(strict)
        mb = ImageChops.multiply(H.point(hl), ImageChops.multiply(S.point(sl), V.point(vl)))
        coded = mb if coded is None else ImageChops.lighter(coded, mb)   # band code where in a band, else 0
    # erosion: keep a pixel whose whole k x k box is in some band (a 5x5 core survives in the disc at 1080p)
    k = max(3, _odd(5 * sc))
    nz = _cache.get('nz')
    if nz is None:
        nz = _cache['nz'] = [0] + [255] * 255
        _cache['full'] = _lut_ge(254)
    er = coded.point(nz).filter(ImageFilter.BoxBlur(k // 2)).point(_cache['full'])
    if er.getbbox() is None:
        return []
    ed = er.tobytes()
    cd = coded.tobytes()
    seen = bytearray(n * n)
    limit = int(3 * area) + 20
    cone_masks = {}
    out = []
    for mt in re.finditer(rb'[^\x00]', ed):
        p0 = mt.start()
        if seen[p0]:
            continue
        code = cd[p0]
        comp, big = _flood(p0, code, cd, seen, n, limit)
        if big:
            continue
        bi = code // 40 - 1
        xs = [q % n for q in comp]
        ys = [q // n for q in comp]
        d = Dot()
        d.band, d.prior = BANDS[bi][0], BANDS[bi][5]
        d.n = len(comp)
        d.bw = max(xs) - min(xs) + 1
        d.bh = max(ys) - min(ys) + 1
        d.fill = d.n / float(d.bw * d.bh)
        d.core = sum(1 for q in comp if ed[q])
        mx = sum(xs) / float(d.n)
        my = sum(ys) / float(d.n)
        d.x, d.y = geo.x0 + mx, geo.y0 + my
        d.dx, d.dy = d.x - geo.cx, d.y - geo.cy
        d.r = math.hypot(d.dx, d.dy)
        d.cone, d.conc, d.cone_dir, d.score = 0, 0.0, 0.0, 0.0
        why = []
        if not 0.75 <= d.n / area <= 1.2:
            why.append('area')
        if not (0.8 * D <= d.bw <= 1.2 * D and 0.8 * D <= d.bh <= 1.2 * D):
            why.append('size')
        if max(d.bw, d.bh) > 1.3 * min(d.bw, d.bh):
            why.append('aspect')
        if not 0.6 <= d.fill <= 0.93:
            why.append('fill')
        if d.core < 8 * sc * sc:
            why.append('core')
        if d.r > geo.rim - 0.6 * D - 2:
            why.append('rim')                       # clipped by the circle: the centroid would be off
        d.shape_ok = not why
        d.why = ','.join(why)
        d.fit, d.edge = None, 0.0
        cx_ = cy_ = None
        if d.shape_ok:
            d.fit, cx_, cy_ = 'whole', mx, my
        elif d.band == 'yellow' and 'rim' not in why and d.n >= PART_MIN * area:
            pf = _disc_fit(comp, n, D)
            if pf is not None:
                fx, fy, edge, inside = pf
                fr = math.hypot(geo.x0 + fx - geo.cx, geo.y0 + fy - geo.cy)
                if edge >= PART_EDGE and inside >= PART_MIN * area and fr <= geo.rim - 0.6 * D - 2:
                    d.fit, d.edge, cx_, cy_ = 'part', edge, fx, fy
                    d.x, d.y = geo.x0 + fx, geo.y0 + fy
                    d.dx, d.dy = d.x - geo.cx, d.y - geo.cy
                    d.r = fr
        if d.fit is not None:
            cm = cone_masks.get(bi)
            if cm is None:
                hl, sl, vl = _cone_luts(bi)
                cm = ImageChops.multiply(H.point(hl), ImageChops.multiply(S.point(sl), V.point(vl)))
                cone_masks[bi] = cm
            _cone(d, cm, cx_, cy_, D)
        out.append(d)
    return out


def _disc_fit(comp, n, D):
    """A circle of the icon's diameter D fitted to one blob (pixel indices in an n-wide crop) that failed the shape
    test: the disc partly under another icon, or merged with a yellow one. Each edge pixel (one with a 4-neighbour
    outside the blob) votes for the points at the disc's radius from it, the peak is refined by least squares on the
    edge pixels within 1.5 px of that circle. Returns (x, y, rim share, blob pixels inside the circle) in crop px,
    or None. The rim share is the edge pixels on the circle over its circumference, capped at 1 (a 4-connected
    outline has more pixels than the circumference, about 1.1x on a whole disc)."""
    inb = set(comp)
    Rv = D / 2.0 - 0.5                  # edge pixel centres sit half a pixel inside the disc's outline
    edge = []
    for q in comp:
        if (q - 1) not in inb or (q + 1) not in inb or (q - n) not in inb or (q + n) not in inb:
            edge.append((q % n, q // n))
    if len(edge) < 6:
        return None
    steps = max(24, int(2 * math.pi * Rv / 0.5))
    ring = [(Rv * math.cos(2 * math.pi * i / steps), Rv * math.sin(2 * math.pi * i / steps)) for i in range(steps)]
    acc = {}
    for ex, ey in edge:
        for ox, oy in ring:
            k = (int(round(ex + ox)), int(round(ey + oy)))
            acc[k] = acc.get(k, 0) + 1
    if not acc:
        return None
    (bx, by), _v = max(acc.items(), key=lambda kv: kv[1])
    cx, cy = float(bx), float(by)
    on = []
    for _ in range(4):
        on = []
        sx = sy = 0.0
        for ex, ey in edge:
            dx, dy = ex - cx, ey - cy
            r = math.hypot(dx, dy)
            if r > 1e-6 and abs(r - Rv) <= 1.5:
                on.append((ex, ey))
                sx += ex - Rv * dx / r
                sy += ey - Rv * dy / r
        if not on:
            return None
        cx, cy = sx / len(on), sy / len(on)
    rr = (D / 2.0 + 0.5) ** 2
    inside = sum(1 for q in comp if (q % n - cx) ** 2 + (q // n - cy) ** 2 <= rr)
    return cx, cy, min(1.0, len(on) / (2 * math.pi * Rv)), inside


SECTORS = 8


def _sectors(half, r0, r1):
    """The annulus r0 <= r <= r1 in a (2 half + 1)^2 window, cut into SECTORS masks, with their unit vectors."""
    key = ('sect', half, round(r0, 2), round(r1, 2))
    a = _cache.get(key)
    if a is None:
        size = 2 * half + 1
        masks = []
        for s in range(SECTORS):
            m = Image.new('L', (size, size), 0)
            px = m.load()
            for y in range(size):
                for x in range(size):
                    dx, dy = x - half, y - half
                    r = math.hypot(dx, dy)
                    sec = int((math.atan2(dy, dx) % (2 * math.pi)) / (2 * math.pi) * SECTORS) % SECTORS
                    if r0 <= r <= r1 and sec == s:
                        px[x, y] = 255
            ang = (s + 0.5) / SECTORS * 2 * math.pi
            masks.append((m, math.cos(ang), math.sin(ang)))
        a = _cache[key] = masks
    return a


def _cone(d, cm, mx, my, D):
    """The translucent view cone: same hue, darker, gathered in one direction around the disc."""
    half = int(round(3.2 * D))
    cxp, cyp = int(round(mx)), int(round(my))
    win = cm.crop((cxp - half, cyp - half, cxp + half + 1, cyp + half + 1))
    sx = sy = 0.0
    cnt = 0
    for m, c, s in _sectors(half, 0.72 * D, 3.2 * D):
        k = ImageChops.multiply(win, m).histogram()[255]
        cnt += k
        sx += k * c
        sy += k * s
    d.cone = cnt
    if cnt:
        d.conc = math.hypot(sx, sy) / cnt
        d.cone_dir = math.degrees(math.atan2(sy, sx))


def has_cone(d, sc):
    """A cone: enough cone pixels, mostly on one side (a yellowish background spreads all round)."""
    return d.cone >= 150 * sc * sc and d.conc >= 0.5


# ---------------------------------------------------------------------------------------------------- grid
class Grid:
    __slots__ = ('cell', 'level', 'cls', 'fx', 'fy', 'err_px', 'contrast', 'scores', 'teeth', 'cover', 'ok', 'why')

    def __repr__(self):
        if not self.ok:
            return 'Grid(none: %s)' % self.why
        return ('Grid(cell=%.2f level=%s/%s line x=%.2f y=%.2f err=%.2fpx c=%.1f teeth=%d)'
                % (self.cell, self.level, self.cls, self.fx, self.fy, self.err_px, self.contrast, self.teeth))


def _profiles(gray, geo):
    """High-passed column and row means over the inner disc: lists (None outside), [1 2 1] smoothed."""
    n, sc = geo.n, geo.sc
    rr = geo.rim - 14 * sc
    mask = _circle_mask(n, geo.ccx, geo.ccy, rr)
    key = ('wts', n, round(geo.ccx, 2), round(geo.ccy, 2), round(rr, 2))
    wts = _cache.get(key)
    if wts is None:
        mf = mask.convert('F')
        wts = (array('f', mf.reduce((1, n)).tobytes()), array('f', mf.reduce((n, 1)).tobytes()))
        _cache[key] = wts
    lut = _cache.get('clamp')
    if lut is None:
        c = 12                                       # icons and text are clamped so the faint lines count
        lut = _cache['clamp'] = [min(max(v, 128 - c), 128 + c) for v in range(256)]
    grey = _cache.get(('grey', n))
    if grey is None:
        grey = _cache[('grey', n)] = Image.new('L', (n, n), 128)
    rad = max(2, int(round(3 * sc)))
    hp = ImageChops.subtract(gray, gray.filter(ImageFilter.BoxBlur(rad)), 1, 128).point(lut)
    hp = Image.composite(hp, grey, mask).convert('F')
    col = array('f', hp.reduce((1, n)).tobytes())
    row = array('f', hp.reduce((n, 1)).tobytes())
    out = []
    for prof, w in ((col, wts[0]), (row, wts[1])):
        p = [((c - 128.0) * 255.0 / ww if ww > 40 else None) for c, ww in zip(prof, w)]
        q = [None] * n
        for i in range(n):
            if p[i] is None:
                continue
            a = p[i - 1] if i > 0 and p[i - 1] is not None else p[i]
            b = p[i + 1] if i + 1 < n and p[i + 1] is not None else p[i]
            q[i] = 0.25 * a + 0.5 * p[i] + 0.25 * b
        out.append(q)
    return out


def _fold(q, P):
    """The profile folded at period P into B ~ P bins of about 1 px (linear splat): per bin the weighted sum and
    the sum of squared weights (the matched filter's noise is sigma * sqrt(that))."""
    B = max(12, 2 * int(round(P / 2)))
    acc = [0.0] * B
    wsq = [0.0] * B
    for i, v in enumerate(q):
        if v is None:
            continue
        f = (i % P) / P * B
        b = int(f)
        t = f - b
        b %= B
        b2 = (b + 1) % B
        acc[b] += v * (1 - t)
        wsq[b] += (1 - t) * (1 - t)
        acc[b2] += v * t
        wsq[b2] += t * t
    return acc, wsq, B


def _comb(q, P):
    """The half-period comb of period P on one profile: for the best phase, (sum on the teeth minus sum half a
    period away, its noise weight, phase in px).

    A comb is a matched filter: its score in noise units grows with the square root of the teeth it hits, so a long
    period that lands one tooth on a line by chance scores low. The half-period difference gives the double period
    zero (both halves sit on lines) and half the true period a sqrt(2) lower score (every other tooth misses).

    The phase returned is the peak of the folded profile itself, not of the difference: the high-pass leaves a dark
    lobe beside each line, and the difference can score as high half a period away from that lobe as on the line."""
    acc, wsq, B = _fold(q, P)
    h = B // 2
    best, bk, bw = -1e18, 0, 1.0
    for b in range(B):
        o = (b + h) % B
        w = wsq[b] + wsq[o]
        if w <= 0:
            continue
        c = acc[b] - acc[o]
        z = c / math.sqrt(w)
        if z > best:
            best, bk, bw = z, b, w
    o = (bk + h) % B
    c = acc[bk] - acc[o]
    sm = [0.25 * acc[b - 1] + 0.5 * acc[b] + 0.25 * acc[(b + 1) % B] for b in range(B)]
    pk = max(range(B), key=lambda b: sm[b])
    # sub-bin refinement of the phase (parabola on the smoothed sums)
    s0, s1, s2 = sm[pk - 1], sm[pk], sm[(pk + 1) % B]
    den = s0 - 2 * s1 + s2
    off = 0.5 * (s0 - s2) / den if den < 0 else 0.0
    return c, bw, ((pk + max(-0.5, min(0.5, off))) * P / B) % P


def _teeth(q, P, phase):
    """Sub-pixel peaks near phase + k P: a list of (k, position, strength)."""
    n = len(q)
    w = max(3, int(round(0.15 * P)))
    out = []
    k = int(math.ceil(-phase / P))
    while phase + k * P <= n:
        t = phase + k * P
        best, bi = None, None
        for i in range(max(1, int(math.floor(t - w))), min(n - 1, int(math.ceil(t + w)) + 1)):
            v = q[i]
            if v is None or q[i - 1] is None or q[i + 1] is None:
                continue
            if v >= q[i - 1] and v >= q[i + 1] and (best is None or v > best):
                best, bi = v, i
        if bi is not None:
            a, b0, c = q[bi - 1], q[bi], q[bi + 1]
            den = a - 2 * b0 + c
            off = 0.5 * (a - c) / den if den < 0 else 0.0
            out.append((k, bi + max(-0.5, min(0.5, off)), best))
        k += 1
    return out


# thresholds on the comb score (both axes, then each axis) and on its margin over the next period; calibrated on
# the user's screenshots (map frames score 6.3-11.3, frames without the map at most 3.9)
GRID_MIN_SCORE, GRID_MIN_AXIS, GRID_MIN_MARGIN = 5.0, 2.5, 1.15
# a real grid has a line at (nearly) every place its period puts one in the middle of the circle; a zoom step in
# progress can line up a few lines of another cell with a level's period (every 4th line of a magnified level-0
# grid fits the -1 big cell). Coverage = lines found / lines predicted within GRID_COVER_R rim of the centre. The
# user's map frames cover 0.72-1.0, the simulated zoom steps (a level-0 frame magnified 1.02-1.98) 0.22-0.50.
# The lines must also sit on the fitted period: the user's frames fit to 0.3 px rms, a zoom step that passes the
# coverage to 2.2 px
GRID_MIN_COVER, GRID_COVER_R, GRID_MAX_RMS = 0.6, 0.7, 1.2
# a measured cell names a level only within this of the level's cell. The user's map frames measure within 0.5 %;
# a zoom animation passes through every cell in between (a level-0 grid magnified 2 % fits twice the cell to 2 %)
LEVEL_TOL = 0.015


def measure_grid(img, geo, gray=None):
    """The 65 m grid: the cell (px), the level, a line position on each axis (crop px), and its error (px)."""
    g = Grid()
    g.ok, g.why = False, ''
    g.cell, g.level, g.cls, g.fx, g.fy, g.err_px, g.contrast, g.teeth = 0.0, None, None, 0.0, 0.0, 0.0, 0.0, 0
    g.cover = 0.0
    if gray is None:
        gray = img.convert('L')
    qx, qy = _profiles(gray, geo)
    vals = [v for v in qx + qy if v is not None]
    if len(vals) < 50:
        g.why = 'no profile'
        return g
    sigma = math.sqrt(sum(v * v for v in vals) / len(vals)) or 1.0
    scores = []
    for cell, lv, cl in CELLS_1080:
        P = cell * geo.sc
        c1, w1, px_ = _comb(qx, P)
        c2, w2, py_ = _comb(qy, P)
        z = (c1 + c2) / math.sqrt(w1 + w2) / sigma
        zmin = min(c1 / math.sqrt(w1), c2 / math.sqrt(w2)) / sigma
        scores.append((z, zmin, P, lv, cl, px_, py_))
    g.scores = [(round(s[2], 1), round(s[0], 2), round(s[1], 2)) for s in scores]
    scores.sort(key=lambda s: -s[0])
    tot, mn, P, lv, cl, px_, py_ = scores[0]
    g.contrast = tot
    margin = tot / scores[1][0] if scores[1][0] > 0 else 9.9
    if tot < GRID_MIN_SCORE or mn < GRID_MIN_AXIS:
        g.why = 'weak %.1f/%.1f' % (tot, mn)
        return g
    if margin < GRID_MIN_MARGIN:
        g.why = 'ambiguous %.1f vs %.1f' % (scores[0][2], scores[1][2])
        return g
    keep = []
    n_pred = n_hit = 0
    rr = GRID_COVER_R * geo.rim
    for ph0, cc, tt in ((px_, geo.ccx, _teeth(qx, P, px_)), (py_, geo.ccy, _teeth(qy, P, py_))):
        smax = max([s for _, _, s in tt] or [0])
        kept = [(k, p, s) for k, p, s in tt if s >= 0.35 * smax and s > 1.0]
        keep.append(kept)
        ks = set(k for k, _, _ in kept)
        k = int(math.ceil((cc - rr - ph0) / P))
        while ph0 + k * P <= cc + rr:
            n_pred += 1
            n_hit += k in ks
            k += 1
    g.cover = n_hit / float(n_pred) if n_pred else 0.0
    if not keep[0] or not keep[1]:
        g.why = 'teeth'
        return g
    if g.cover < GRID_MIN_COVER:
        # lines missing where this period puts them: a zoom step in progress that lines up with a level by chance
        g.why = 'lines %d of %d' % (n_hit, n_pred)
        return g
    # joint least squares: position = phase_axis + k P, with P shared by the axes
    num = den = 0.0
    for tt in keep:
        kb = sum(k for k, _, _ in tt) / len(tt)
        pb = sum(p for _, p, _ in tt) / len(tt)
        for k, p, _ in tt:
            num += (k - kb) * (p - pb)
            den += (k - kb) ** 2
    if den <= 0:
        g.why = 'one line per axis'
        return g
    Pm = num / den
    if abs(Pm / P - 1) > 0.03:
        # the lines are not where this period puts them: a zoom step in progress (the cell between two levels)
        g.why = 'period fit %.1f vs %.1f' % (Pm, P)
        return g
    ph, res = [], []
    for tt in keep:
        f = sum(p - k * Pm for k, p, _ in tt) / len(tt)
        ph.append(f)
        res += [p - k * Pm - f for k, p, _ in tt]
    nt = len(res)
    rms = math.sqrt(sum(r * r for r in res) / nt)
    if rms > GRID_MAX_RMS * geo.sc:
        g.why = 'lines off the period by %.1f px rms' % rms
        return g
    # the line nearest the circle centre on each axis (crop px)
    g.fx = ph[0] + Pm * round((geo.ccx - ph[0]) / Pm)
    g.fy = ph[1] + Pm * round((geo.ccy - ph[1]) / Pm)
    g.cell, g.teeth = Pm, nt
    g.err_px = math.sqrt(0.3 ** 2 + rms ** 2)
    best = min(CELLS_1080, key=lambda c: abs(math.log(Pm / (c[0] * geo.sc))))
    if abs(Pm / (best[0] * geo.sc) - 1) <= LEVEL_TOL:
        g.level, g.cls = best[1], best[2]
    g.ok = True
    return g


# ---------------------------------------------------------------------------------------------------- frame
class Analysis:
    __slots__ = ('dots', 'grid', 'geo', 'ms', 'img')     # img: the capture analysed (1.1: recorded)


def analyse(img, geo):
    """All the measurements of one capture (img is the crop_box square, RGB)."""
    t0 = time.perf_counter()
    if img.mode != 'RGB':
        img = img.convert('RGB')
    if img.size != (geo.n, geo.n):
        img = img.resize((geo.n, geo.n))
    a = Analysis()
    a.geo = geo
    a.img = img
    a.dots = find_dots(img, geo)
    a.grid = measure_grid(img, geo)
    a.ms = (time.perf_counter() - t0) * 1000
    return a


def _circ(d):
    """d modulo 65 m, into [-32.5, 32.5)."""
    return (d + GRID_M / 2) % GRID_M - GRID_M / 2


def view_limit(cls, kz, rim):
    """How far V can go from the origin on each axis (the game clamps the view), or None when unknown."""
    R = R_MAP.get(cls)
    if R is None or not kz:
        return None
    return max(0.0, R - rim / kz)


DOT_GRID_MAX = 8.0     # m per axis: a dot whose V is further than this from the grid's phase is not used


def solve(a, mod, prior=None):
    """The fix for one analysed frame.

    mod: the parsed mod line (a dict of strings). prior: None, or a dict {vx, vy, err} with the companion's
    prediction of V for this frame (its last fix advanced by the mouse counts since). Returns a dict with the fix
    fields (how, vx, vy, err, level, cell) plus 'kz' (the scale used), 'gain_level', 'dot' (the Dot used, or None)
    and 'note'.

    Every fix needs the grid: its period names the level (so the scale), its phase gives V modulo 65 m on each
    axis to a fraction of a pixel. The player's icon then picks the 65 m cell (how=dot); without a usable icon the
    prior picks it (how=grid). A frame without a grid that names a level gives no fix: that is a zoom step in
    progress or no map at all, and there the mod's scale does not hold either.

    1.2: the icon may be a partial disc (Dot.fit 'part': a circle fit on a blob the shape test refused, with the
    view cone at the fitted centre); it ranks below a whole one and its fix carries PART_ERR. At level -1 with the
    map's class known the whole map sits on the origin, so a grid whose phase is within DOT_GRID_MAX of it and no
    usable icon give how=grid vx=0 vy=0 (no prior needed).
    """
    geo, g, sc = a.geo, a.grid, a.geo.sc
    level, cls, kz = geo.level, geo.cls, geo.kz
    note = []
    if g.ok and g.level is not None:
        # the grid period is a direct measurement: its level sets the scale (and at -1 its class, when the mod
        # knows the map's class at all; with class=? level -1 has no scale)
        new_cls = g.cls if (g.level == -1 and g.cls and cls) else cls
        if level is None or not kz:
            # the mod lost its level (it then sends level=? kz=0): kz from the level's 1080p value times h/1080
            k = kz_theory(g.level, new_cls, geo.h / 1080.0) if (g.level != -1 or new_cls) else None
            kz = k or 0.0
            note.append(('level %s->%s, kz from the grid' % ('?' if level is None else level, g.level)) if k
                        else 'level -1 with the map class unknown: no scale')
        elif g.level != level or new_cls != cls:
            k_mod = kz_theory(level, cls, sc)
            k_new = kz_theory(g.level, new_cls, sc)
            kz = k_new * (kz / k_mod if k_mod else 1.0) if k_new else 0.0
            note.append('level %s->%s' % (level, g.level))
        level, cls = g.level, new_cls
    fix = {'how': 'none', 'err': 0.0, 'level': g.level if g.ok and g.level is not None else '?',
           'cell': g.cell if g.ok else 0.0, 'dot': None, 'note': '', 'kz': kz, 'gain_level': level}
    if not g.ok:
        fix['note'] = 'no grid (%s)' % g.why
        return fix
    if g.level is None:
        # a grid whose period matches no level: the zoom is animating, so neither the scale nor the phase holds
        fix['note'] = 'grid cell %.1f px matches no level (zooming?)' % g.cell
        return fix
    if not kz:
        fix['note'] = '; '.join(note + ['no scale'])
        return fix
    try:
        px, py = float(mod.get('px')), float(mod.get('py'))
    except (TypeError, ValueError):
        px = py = None
    gvx = (geo.cx - (geo.x0 + g.fx)) / kz        # the grid's V, modulo 65 m on each axis
    gvy = ((geo.y0 + g.fy) - geo.cy) / kz
    g_err = g.err_px / kz
    have_prior = prior is not None and prior.get('vx') is not None
    best = None
    off_grid = []
    if px is not None:
        for d in a.dots:
            if not (d.shape_ok or d.fit == 'part') or not has_cone(d, sc):
                continue                         # only the own icon has a view cone (teammates, the mod's own
                                                 # drawings and yellow objective marks do not)
            vx = px - d.dx / kz
            vy = py + d.dy / kz
            ex, ey = _circ(vx - gvx), _circ(vy - gvy)
            if abs(ex) > DOT_GRID_MAX or abs(ey) > DOT_GRID_MAX:
                off_grid.append('%s off the grid by %+.1f,%+.1f m' % (d.band, ex, ey))
                continue
            s = d.prior + 1.0 + 0.6 * math.exp(-(math.hypot(ex, ey) / 6.0) ** 2)
            if d.fit == 'part':
                s -= 0.5                         # a whole disc with a cone wins over a fitted one
            if have_prior:
                pe = max(3.0, float(prior.get('err', 10)))
                dist = math.hypot(vx - prior['vx'], vy - prior['vy'])
                s += math.exp(-(dist / (2 * pe + 5)) ** 2)
                if d.band != 'yellow' and dist > 3 * pe + 10:
                    continue                     # a disc in another colour counts only near the prediction
            elif d.band != 'yellow':
                continue
            d.score = s
            if best is None or s > best[0]:
                best = (s, d, vx - ex, vy - ey, ex, ey)
    note += off_grid
    if best is not None:
        _s, d, vx, vy, ex, ey = best
        # the grid is exact on the map; the dot (2-3 m from the camera point the mod sends) only picks the cell
        part = d.fit == 'part'
        fix.update(how='dot', vx=vx, vy=vy, err=math.hypot(g_err, PART_ERR if part else 0.5), dot=d)
        note.append('dot+grid %+.1f,%+.1f' % (ex, ey)
                    + ((' (partial disc, %.0f%% of its rim)' % (100 * d.edge)) if part else ''))
    elif level == -1 and cls:
        # level -1 shows the whole map on the origin (the game's own clamp): V is (0, 0) by the map's class, the grid
        # only has to agree
        ex, ey = _circ(gvx), _circ(gvy)
        if max(abs(ex), abs(ey)) > DOT_GRID_MAX:
            note.append('level -1 but the grid is %+.1f,%+.1f m off the origin' % (ex, ey))
        else:
            fix.update(how='grid', vx=0.0, vy=0.0, err=math.hypot(g_err, 0.5))
            note.append('level -1: the whole map on the origin (grid %+.1f,%+.1f m)' % (ex, ey))
    elif have_prior:
        pvx, pvy, perr = float(prior['vx']), float(prior['vy']), float(prior.get('err', 10))
        vx = gvx + GRID_M * round((pvx - gvx) / GRID_M)
        vy = gvy + GRID_M * round((pvy - gvy) / GRID_M)
        jx, jy = vx - pvx, vy - pvy
        if perr > 20.0 or max(abs(jx), abs(jy)) > 26.0:
            note.append('grid, prior too vague (err %.1f, jump %+.1f,%+.1f)' % (perr, jx, jy))
        else:
            fix.update(how='grid', vx=vx, vy=vy, err=math.hypot(perr * 0.5 + 0.5 * max(abs(jx), abs(jy)), g_err))
            note.append('grid jump %+.1f,%+.1f' % (jx, jy))
    else:
        note.append('no dot, no prior')
    fix['note'] = '; '.join(note)
    return fix
