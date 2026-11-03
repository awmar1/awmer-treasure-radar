"""The map-open detector (mapview.lua): the world list, the Map key (default Tab, Press) as a toggle, and doubt.

  python -I dev/src/sim/sim.py mapview_list   case A: a second world comes and goes with the map. A Tab press just
                                              before it proves list mode; Esc hides the views while the world stays;
                                              a camera jump (respawn) hides them; F7 hides the mod's HUD
  python -I dev/src/sim/sim.py mapview_key    case B (the game): a second world all the time. Closed until the first
                                              Tab press (0.6 showed the views from the start); then Tab toggles, Esc
                                              closes, and a new mission starts closed
  python -I dev/src/sim/sim.py mapview_desync key mode when the game ignores a Map press: an ignored Tab hides the
                                              radar until I look around (the camera turns with the mouse); an
                                              ignored Tab on the open map shows it until the mouse moves with the
                                              camera still; after Esc the mouse opens nothing
The bezel draws on the open map, so frames show plainly whether S.map_open is on. Both press Tab themselves
('map_key': False: the sim doesn't add its own presses).
"""
# the base scenarios' loot (scenarios load as separate files, so it's copied)
LOOT = [
    ('medal', 5, 25, 0), ('medal', 5.6, 25.4, 0), ('common', -30, 60, 0), ('common', 40, -20, 0),
    ('rare', 80, 90, 3), ('super', -120, 40, 5), ('requisition', 15, 12, 0.5), ('credit', -8, 18, 0.5),
    ('ammo', 3, 8, 0), ('stim', -4, 6, 0), ('grenade', -60, -70, 0),
]

SCENARIOS = {
    'mapview_list': {
        'about': 'list mode: Tab + world opens, Esc hides, world goes; reopen, a camera jump hides; reopen, F7',
        'frames': 600, 'render': [90, 150, 270, 330, 450, 520],
        'options': {},
        'camera': [(0, 0, 0, 1.6, 20, -6), (5.0, 0, 0, 1.6, 20, -6), (5.02, 0, 40, 1.6, 20, -6)],
        'units': LOOT,
        'map_open': [(1.0, 3.0), (4.0, 6.0), (7.0, 9.5)], 'map_key': False,
        'press': [(0.98, 'tab'), (2.0, 'esc'), (2.98, 'tab'), (3.98, 'tab'), (6.98, 'tab'), (8.0, 'f7')],
    },
    'mapview_key': {
        'about': 'key mode: a second world all the time, closed until Tab; Tab toggles; Esc closes; a new mission starts closed',
        'frames': 540, 'render': [40, 130, 200, 280, 320, 400, 450, 500],
        'options': {},
        'camera': [(0, 0, 0, 1.6, 20, -6)],
        'units': LOOT,
        'map_open': [(0.0, 99)], 'map_key': False,
        'press': [(1.0, 'tab'), (3.0, 'tab'), (4.0, 'tab'), (5.0, 'esc'), (6.0, 'tab'), (8.0, 'tab')],
        'new_world': [7.0],
    },
    'mapview_desync': {
        'about': 'key mode, ignored Map presses: the mouse and the camera set the toggle right; Esc stops it',
        'frames': 660, 'render': [90, 168, 258, 318, 348, 432, 498, 612],
        'options': {},
        'camera': [(0, 0, 0, 1.6, 20, -6), (1.0, 0, 0, 1.6, 20, -6), (1.5, 0, 0, 1.6, 60, -6),
                   (3.5, 0, 0, 1.6, 60, -6), (4.0, 0, 0, 1.6, 100, -6)],
        'units': LOOT,
        'map_open': [(0.0, 99)], 'map_key': False,
        'raw_mouse': [(1.0, 1.5, 6, 0), (3.5, 4.0, 6, 0), (6.0, 7.0, 10, 2), (9.0, 9.9, 10, 0)],
        'press': [(2.5, 'tab'), (5.0, 'tab'), (5.5, 'tab'), (8.0, 'tab'), (8.5, 'esc')],
    },
}
