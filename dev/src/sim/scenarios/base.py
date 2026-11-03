"""Base scenarios. A scenario is a dict; every field is optional:

  about       one line for --list
  size        (w, h) screen pixels, default (1920, 1080)
  fov         vertical field of view in degrees (default 70)
  frames, dt  how many frames to run, seconds per frame (default 240, 1/60)
  render      frame numbers to render (default: the last)
  options     chef.options (the Arsenal options files merged); {} = a plain install, everything on but the overlay
  hud         hud_* settings over the player's own (sim.HUD_DEFAULT)
  camera      [(t, x, y, z, yaw_deg, pitch_deg)] keyframes, linear; yaw 0 = north, clockwise; z is the eye height
  units       [(kind id or 16-hex unit kind, x, y, z[, t when picked up / destroyed])]
  map_open    [(t0, t1)] the game's map is open (the loader sees a second world)
  worlds      how many engine worlds Application.worlds lists all the time (default 1: 'world:main', then
              'world:2'...); 2 or more also means the map is open, as map_open does (0.9.2: the line probe)
  ship        [(t0, t1)] not in a mission
  new_world   [t] a new mission starts (the watches empty)
  press       [(t, key)] one-frame key presses (chef.key_pressed, also down that frame)
  hold        [(t0, t1, key)] keys held (chef.key_down)
  mouse       [(t0, t1, button)] mouse buttons held (chef.mouse_down: 'left', 'right')
  cursor      [(t, x, y)] keyframes, window pixels from the TOP-left (chef.cursor; the engine's origin is a guess)
  wheel       [(t, amount)] wheel steps in one frame (chef.wheel)
  raw_mouse   [(t0, t1, dx, dy)] raw mouse movement, in counts every frame from t0 to t1 (Mouse.axis of 'mouse')
  nocam       [(t0, t1)] frames without a camera (chef.camera() is nil: a loading screen, a cutscene)
  background  a PNG to draw on instead of the procedural ground
  backdrop    a game screenshot (read only) to draw over, with no compass or map stand-ins (sim.py --backdrop)
  checks      check(sim, frame) -> [(ok, message)], run on every rendered frame: checks.txt; a failure exits 1
  lua         Lua source run once after the modules load (globals T, chef, SIM): stand-ins for modules not
              written yet, e.g. T.mod.objectives = { marks = {...} } or T.mod.pings = { waypoints = {...}, icon = ... }
              (stand-ins aren't in main's PIPE: they get no update/draw calls, the views just read them)
"""

# loot spread around the start point (0, 0): near, mid and far, in every direction
LOOT = [
    ('medal', 5, 25, 0), ('medal', 5.6, 25.4, 0), ('medal', 1, 10, 0, 2.5),
    ('common', -30, 60, 0), ('common', -29.5, 60.5, 0), ('common', 40, -20, 0),
    ('rare', 80, 90, 3), ('super', -120, 40, 5),
    ('requisition', 15, 12, 0.5), ('credit', -8, 18, 0.5),
    ('ammo', 3, 8, 0), ('ammo', 3.5, 8, 0), ('stim', -4, 6, 0), ('grenade', -60, -70, 0),
]

SCENARIOS = {
    'walk': {
        'about': 'walk north 20 m past loot; a medal picked up at 2.5 s; map open 3-4.5 s',
        'frames': 330, 'render': [60, 200, 320],
        'camera': [(0, 0, 0, 1.6, 0, -6), (5.5, 0, 20, 1.6, 30, -6)],
        'units': LOOT,
        'map_open': [(3.0, 4.5)],
    },
    'turn': {
        'about': 'stand still and turn a full circle in 6 s (compass, radar rotation)',
        'frames': 360, 'render': [0, 90, 180, 270],
        'camera': [(0, 0, 0, 1.6, 0, -6), (6, 0, 0, 1.6, 360, -6)],
        'units': LOOT,
    },
    'map': {
        'about': 'the map open the whole time, the cursor drifting over it',
        'frames': 180, 'render': [30, 170],
        'camera': [(0, 0, 0, 1.6, 20, -6)],
        'units': LOOT,
        'map_open': [(0.0, 99)],
        'cursor': [(0, 1500, 800), (3, 1600, 700)],
    },
    'hidden': {
        'about': 'F7 at 1 s hides the mod HUD, F8 at 2 s hides world markers',
        'frames': 180, 'render': [30, 90, 170],
        'camera': [(0, 0, 0, 1.6, 0, -6)],
        'units': LOOT,
        'press': [(1.0, 'f7'), (2.0, 'f8')],
    },
    'missions': {
        'about': 'the ship (no mission) for 1 s, a mission, then a new mission at 3 s',
        'frames': 300, 'render': [120, 290],
        'camera': [(0, 0, 0, 1.6, 0, -6)],
        'units': LOOT,
        'ship': [(0, 1.0)],
        'new_world': [3.0],
    },
}
SCENARIOS['walk_1440'] = dict(SCENARIOS['walk'], about='walk at 2560x1440', size=(2560, 1440))
