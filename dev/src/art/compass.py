"""Textures for the compass pips (compass.lua): none since 0.8. Run: python -I dev/src/art/compass.py

0.8's compass shows each pip with its kind's own icon (icons/*), a tick drawn as a rect and the distance in the glyph
font; my waypoint uses ping/wp (ping.py). 0.7's compass/dot (the colored dots behind an edge chevron) is retired with
the chevrons, so this script only empties dev/src/textures/compass/ (one GUI texture less).

0.6's bezel/band (a ring inside the open map's rim) is gone too.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # python -I leaves the script's folder out
from lib import TEXTURES, clear  # noqa: E402


def main():
    clear('compass')
    base = os.path.join(TEXTURES, 'compass')
    if os.path.isdir(base) and not os.listdir(base):
        os.rmdir(base)
    print('0 textures (compass/dot retired)')


if __name__ == '__main__':
    main()
