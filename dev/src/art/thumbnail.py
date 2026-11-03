"""The mod's thumbnail: the game's loot icons around a radar sweep, on the mod's dark ground.

Writes dev/src/images/thumbnail.png (512 px).
Run: python -I dev/src/art/thumbnail.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # python -I leaves the script's folder out
from lib import Image, ImageDraw, ROOT
import game_icons

N, K = 512, 3                                   # size, supersampling
GROUND, RIM, SWEEP = (18, 21, 20), (201, 197, 170), (255, 233, 0)
RING = ['credit', 'common', 'ammo', 'rare', 'grenade', 'super', 'stim', 'requisition']


def main():
    big = Image.new('RGBA', (N * K, N * K), GROUND + (255,))
    d = ImageDraw.Draw(big, 'RGBA')
    c = N * K / 2
    for r, a in ((236, 255), (168, 90), (100, 90)):
        d.ellipse((c - r * K, c - r * K, c + r * K, c + r * K), outline=RIM + (a,), width=2 * K)
    for i in range(60):
        d.pieslice((c - 236 * K, c - 236 * K, c + 236 * K, c + 236 * K), -90 - i, -89 - i, fill=SWEEP + (70 - i,))
    im = big.resize((N, N), Image.LANCZOS)
    for i, kind in enumerate(RING):
        a = math.radians(i * 45 - 90)
        ic = game_icons.load('icons', kind + '.png')
        ic = game_icons.fit_to(ic, 92, game_icons.TINT.get(kind))
        im.alpha_composite(ic, (int(N / 2 + 172 * math.cos(a) - ic.width / 2), int(N / 2 + 172 * math.sin(a) - ic.height / 2)))
    ic = game_icons.fit_to(game_icons.load('icons', 'medal.png'), 190)
    im.alpha_composite(ic, ((N - ic.width) // 2, (N - ic.height) // 2))
    im.convert('RGB').save(os.path.join(ROOT, 'images', 'thumbnail.png'))
    print('wrote thumbnail.png')


if __name__ == '__main__':
    main()
