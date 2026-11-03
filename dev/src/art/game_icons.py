"""The game's own icons, sized for the mod: replaces the drawn textures of icons.py and map_icons.py that have one.

Reads dev/src/art/game_icons/{icons,map}/<id>.png (cut from the game's archives; SOURCES.txt says which resource each
came from and how sure the match is). Writes dev/src/textures/icons/<kind id>.png (colored by the kind with a thin dark
outline, as icons.py's: the addon draws them with a white tint; the medal keeps its gold) and
dev/src/textures/map/<id>.png (white, tinted at draw). icons.py and map_icons.py call this at their end.
Textures have no mips, so each is shrunk here with its alpha premultiplied (no light fringe) to SIZE.
Run: python -I dev/src/art/game_icons.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # python -I leaves the script's folder out
from lib import Image, ImageFilter, save

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'game_icons')
SIZE = 48                  # texture size in pixels
PAD = 3                    # transparent margin the outline grows into
EDGE_ALPHA = 235
DARK = (11, 13, 14)
# kinds.lua's rgb; a kind not here keeps the source's colors
TINT = {
    'credit': (115, 233, 242), 'common': (69, 255, 141), 'rare': (255, 129, 41), 'super': (255, 114, 211),
    'requisition': (255, 233, 0), 'ammo': (255, 234, 128), 'grenade': (135, 170, 45), 'stim': (60, 140, 255),
}
TILT = {'stim': 45}        # stored flat and thin: at 45 degrees it fills the square and reads at icon size


def premultiplied_resize(img, size):
    """img shrunk to size (w, h) with colors weighted by alpha."""
    r, g, b, a = img.split()
    rgb = Image.merge('RGB', (r, g, b))
    black = Image.new('RGB', img.size, (0, 0, 0))
    pre = Image.composite(rgb, black, a).resize(size, Image.LANCZOS)
    a2 = a.resize(size, Image.LANCZOS)
    def undo(c):
        return Image.frombytes('L', size, bytes(min(255, v * 255 // m) if m else 0 for v, m in zip(c.tobytes(), a2.tobytes())))
    return Image.merge('RGBA', tuple(undo(c) for c in pre.split()) + (a2,))


def fit(img, box):
    """img trimmed to its visible pixels and shrunk (never grown) to fit a box x box square, centered, transparent."""
    img = img.crop(img.getchannel('A').getbbox())
    k = min(1.0, box / float(max(img.size)))
    img = premultiplied_resize(img, (max(1, round(img.width * k)), max(1, round(img.height * k))))
    out = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    out.paste(img, ((SIZE - img.width) // 2, (SIZE - img.height) // 2))
    return out


def tint(img, rgb):
    """rgb in the source's light, for white-on-transparent art: a source gray stays darker than its white."""
    r, g, b, a = img.split()
    v = img.convert('L')
    return Image.merge('RGBA', tuple(v.point(lambda p, c=c: p * c // 255) for c in rgb) + (a,))


def outline(img):
    """A thin dark edge under img, so it reads on any ground."""
    a = img.getchannel('A').filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(0.5))
    under = Image.new('RGBA', img.size, DARK + (0,))
    under.putalpha(a.point(lambda v: v * EDGE_ALPHA // 255))
    return Image.alpha_composite(under, img)


def load(folder, name):
    img = Image.open(os.path.join(SRC, folder, name)).convert('RGBA')
    if name[:-4] in TILT:
        img = img.crop(img.getchannel('A').getbbox()).rotate(TILT[name[:-4]], Image.BICUBIC, expand=True)
    return img


def fit_to(img, size, rgb=None):
    """img at size px (grown too, for the larger pictures), outlined, tinted rgb if given"""
    img = img.crop(img.getchannel('A').getbbox())
    k = (size - 2 * PAD) / float(max(img.size))
    img = premultiplied_resize(img, (max(1, round(img.width * k)), max(1, round(img.height * k))))
    out = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    out.paste(img, ((size - img.width) // 2, (size - img.height) // 2))
    return outline(tint(out, rgb) if rgb else out)


def main():
    n = 0
    for name in sorted(os.listdir(os.path.join(SRC, 'icons'))):
        kind = name[:-4]
        img = fit(load('icons', name), SIZE - 2 * PAD)
        if kind in TINT:
            img = tint(img, TINT[kind])
        save(outline(img), 'icons/' + kind)
        n += 1
    for name in sorted(os.listdir(os.path.join(SRC, 'map'))):
        save(fit(load('map', name), SIZE - 2 * PAD), 'map/' + name[:-4])
        n += 1
    print('%d game icons written (%d px)' % (n, SIZE))


if __name__ == '__main__':
    main()
