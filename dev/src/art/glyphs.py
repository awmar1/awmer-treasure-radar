"""The mod's text font: a condensed, squared, chamfered stencil-like face drawn from strokes (no font file needed).

Writes dev/src/textures/glyphs/<cap>/<byte>.png (white ink, thin dark edge) and dev/src/addon/glyphs.lua (the
metrics draw.lua reads). Glyphs are centerline strokes on a grid: x from 0 to the glyph's width W, y from 0 (baseline)
to 10 (cap height), y up; the stroke's outer edge lands exactly on the baseline and the cap line.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # python -I leaves the script's folder out
from lib import ADDON, Canvas, clear, contact_sheet, save  # noqa: E402

CAPS = (12, 18, 27)        # cap heights in pixels: ~1080p, ~1440p, ~4K label sizes (draw.lua scales between them)
WEIGHT = 0.135             # stroke width in cap heights
GAP, SPACE = 0.16, 0.42    # between letters / a space, in cap heights
c = 1.6                    # corner chamfer, grid units

def box(W, x0=0, y0=0, y1=10, ch=c):
    return [(x0 + ch, y0), (W - ch, y0), (W, y0 + ch), (W, y1 - ch), (W - ch, y1), (x0 + ch, y1), (x0, y1 - ch),
            (x0, y0 + ch), (x0 + ch, y0)]

def six(W):
    return [(W - 0.4, 10), (c, 10), (0, 10 - c), (0, c), (c, 0), (W - c, 0), (W, c), (W, 4.0), (W - c, 5.6), (0, 5.6)]

G = {}
# (width, [polylines]); a polyline of one point is a square dot
W = 5.6
G['0'] = (W, [box(W), [(W - 1.2, 8.2), (1.2, 1.8)]])
G['1'] = (2.6, [[(0, 8.4), (1.6, 10), (1.6, 0)]])
G['2'] = (W, [[(0, 8.4), (c, 10), (W - c, 10), (W, 8.4), (W, 6.4), (0, 0.6), (0, 0), (W, 0)]])
G['3'] = (W, [[(0, 10), (W - c, 10), (W, 10 - c), (W, 6.6), (W - c, 5.2), (W, 3.8), (W, c), (W - c, 0), (0, 0)],
              [(1.6, 5.2), (W - c, 5.2)]])
G['4'] = (W, [[(4.0, 0), (4.0, 10), (0, 3.4), (0, 3.0), (W, 3.0)]])
G['5'] = (W, [[(W, 10), (0.2, 10), (0.2, 5.8), (W - c, 5.8), (W, 4.2), (W, c), (W - c, 0), (0, 0)]])
G['6'] = (W, [six(W)])
G['7'] = (W, [[(0, 10), (W, 10), (W, 8.6), (1.8, 0)]])
G['8'] = (W, [[(c, 0), (W - c, 0), (W, c), (W, 3.8), (W - 1.1, 5.2), (W, 6.6), (W, 10 - c), (W - c, 10), (c, 10),
               (0, 10 - c), (0, 6.6), (1.1, 5.2), (0, 3.8), (0, c), (c, 0)], [(1.1, 5.2), (W - 1.1, 5.2)]])
G['9'] = (W, [[(W - x, 10 - y) for x, y in six(W)]])

W = 6.0
G['A'] = (W, [[(0, 0), (0, 10 - c), (c, 10), (W - c, 10), (W, 10 - c), (W, 0)], [(0, 4.4), (W, 4.4)]])
G['B'] = (W, [[(0, 0), (0, 10), (W - c, 10), (W, 10 - c), (W, 6.6), (W - 1.2, 5.2), (W, 3.8), (W, c), (W - c, 0),
               (0, 0)], [(0, 5.2), (W - 1.2, 5.2)]])
G['C'] = (5.6, [[(5.6, 10), (c, 10), (0, 10 - c), (0, c), (c, 0), (5.6, 0)]])
G['D'] = (W, [[(0, 0), (0, 10), (W - 2.2, 10), (W, 7.8), (W, 2.2), (W - 2.2, 0), (0, 0)]])
G['E'] = (5.0, [[(5.0, 10), (0, 10), (0, 0), (5.0, 0)], [(0, 5.2), (4.0, 5.2)]])
G['F'] = (5.0, [[(5.0, 10), (0, 10), (0, 0)], [(0, 5.2), (4.0, 5.2)]])
G['G'] = (W, [[(W, 10), (c, 10), (0, 10 - c), (0, c), (c, 0), (W, 0), (W, 5.0), (3.0, 5.0)]])
G['H'] = (W, [[(0, 0), (0, 10)], [(W, 0), (W, 10)], [(0, 5.2), (W, 5.2)]])
G['I'] = (0, [[(0, 0), (0, 10)]])
G['J'] = (5.0, [[(5.0, 10), (5.0, c), (5.0 - c, 0), (c, 0), (0, c), (0, 2.6)]])
G['K'] = (W, [[(0, 0), (0, 10)], [(W, 10), (0, 4.0)], [(2.0, 5.9), (W, 0)]])
G['L'] = (5.0, [[(0, 10), (0, 0), (5.0, 0)]])
G['M'] = (7.4, [[(0, 0), (0, 10), (3.7, 4.6), (7.4, 10), (7.4, 0)]])
G['N'] = (W, [[(0, 0), (0, 10), (W, 0), (W, 10)]])
G['O'] = (6.4, [box(6.4)])
G['P'] = (W, [[(0, 0), (0, 10), (W - c, 10), (W, 10 - c), (W, 6.2), (W - c, 4.6), (0, 4.6)]])
G['Q'] = (6.4, [box(6.4), [(4.0, 2.4), (6.6, -0.3)]])
G['R'] = (W, [[(0, 0), (0, 10), (W - c, 10), (W, 10 - c), (W, 6.2), (W - c, 4.6), (0, 4.6)], [(W - 2.6, 4.6), (W, 0)]])
G['S'] = (W, [[(W, 10), (c, 10), (0, 10 - c), (0, 6.8), (c, 5.2), (W - c, 5.2), (W, 3.6), (W, c), (W - c, 0), (0, 0)]])
G['T'] = (W, [[(0, 10), (W, 10)], [(W / 2, 10), (W / 2, 0)]])
G['U'] = (W, [[(0, 10), (0, c), (c, 0), (W - c, 0), (W, c), (W, 10)]])
G['V'] = (6.4, [[(0, 10), (3.2, 0), (6.4, 10)]])
G['W'] = (8.6, [[(0, 10), (1.9, 0), (4.3, 7.0), (6.7, 0), (8.6, 10)]])
G['X'] = (W, [[(0, 10), (W, 0)], [(0, 0), (W, 10)]])
G['Y'] = (W, [[(0, 10), (W / 2, 5.0), (W, 10)], [(W / 2, 5.0), (W / 2, 0)]])
G['Z'] = (W, [[(0, 10), (W, 10), (W, 9.4), (0, 0.6), (0, 0), (W, 0)]])

G['.'] = (0, [[(0, 0)]])
G[','] = (0.8, [[(0.8, 0.6), (0, -1.0)]])
G[':'] = (0, [[(0, 0)], [(0, 6.4)]])
G['/'] = (4.0, [[(0, 0), (4.0, 10)]])
G['-'] = (3.4, [[(0, 4.8), (3.4, 4.8)]])
G['+'] = (5.0, [[(0, 4.8), (5.0, 4.8)], [(2.5, 2.3), (2.5, 7.3)]])
G['%'] = (7.0, [[(0, 0), (7.0, 10)], [(0, 10), (2.0, 10), (2.0, 7.6), (0, 7.6), (0, 10)],
                [(5.0, 2.4), (7.0, 2.4), (7.0, 0), (5.0, 0), (5.0, 2.4)]])
G["'"] = (0, [[(0, 10), (0, 7.4)]])
G['('] = (1.8, [[(1.8, 10), (0, 8.2), (0, 1.8), (1.8, 0)]])
G[')'] = (1.8, [[(0, 10), (1.8, 8.2), (1.8, 1.8), (0, 0)]])
G['?'] = (5.4, [[(0, 8.4), (c, 10), (5.4 - c, 10), (5.4, 8.4), (5.4, 6.6), (2.7, 4.6), (2.7, 3.0)], [(2.7, 0)]])
G['!'] = (0, [[(0, 10), (0, 3.0)], [(0, 0)]])
G['#'] = (6.0, [[(1.6, 0), (2.4, 10)], [(3.6, 0), (4.4, 10)], [(0, 6.6), (6.0, 6.6)], [(0, 3.4), (6.0, 3.4)]])
G['<'] = (4.4, [[(4.4, 8.6), (0, 5.0), (4.4, 1.4)]])
G['>'] = (4.4, [[(0, 8.6), (4.4, 5.0), (0, 1.4)]])
# two Latin-1 bytes (write them as "" and "83" in Lua): a pile's count ("2" = x2) and a separator
G[chr(215)] = (4.4, [[(0, 1.6), (4.4, 6.0)], [(0, 6.0), (4.4, 1.6)]])     # multiplication sign, x-height
G[chr(183)] = (0, [[(0, 4.8)]])                                           # middle dot


def render(ch, cap):
    W, lines = G[ch]
    sw = WEIGHT * cap
    edge = max(0.8, cap / 14)
    pad = int(math.ceil(edge)) + 1
    k = (cap - sw) / 10
    ink_w = sw + W * k
    tw = int(math.ceil(ink_w + 2 * pad))
    th = cap + 2 * pad

    def P(x, y):
        return (pad + sw / 2 + x * k, th - pad - (sw / 2 + y * k))

    cv = Canvas(tw, th)
    for pl in lines:
        cv.stroke([P(x, y) for x, y in pl], sw, (255, 255, 255, 255), closed=len(pl) > 2 and pl[0] == pl[-1])
    return cv.finish(edge=edge, edge_alpha=150), ink_w / cap, tw, th, pad


def main():
    clear('glyphs')
    sets = []
    names = []
    for cap in CAPS:
        chars = {}
        pad = None
        for ch in sorted(G):
            img, adv, tw, th, pad = render(ch, cap)
            b = ord(ch)
            save(img, 'glyphs/%d/%d' % (cap, b))
            names.append('glyphs/%d/%d' % (cap, b))
            chars[b] = (adv, tw, th)
        sets.append((cap, pad, chars))
    out = ['local T, chef = ...',
           '-- Generated by dev/src/art/glyphs.py: the glyph textures\' metrics (see draw.lua). Do not edit by hand.',
           'return { gap = %g, space = %g, sets = {' % (GAP, SPACE)]
    for cap, pad, chars in sets:
        out.append('  { cap = %d, pad = %d, chars = {' % (cap, pad))
        row = []
        for b in sorted(chars):
            adv, tw, th = chars[b]
            row.append('[%d] = { %.4f, %d, %d }' % (b, adv, tw, th))
        for i in range(0, len(row), 6):
            out.append('    ' + ', '.join(row[i:i + 6]) + ',')
        out.append('  } },')
    out.append('} }')
    with open(os.path.join(ADDON, 'glyphs.lua'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(out) + '\n')
    print('glyphs: %d chars x %d sizes' % (len(G), len(CAPS)))
    return names


if __name__ == '__main__':
    main()
