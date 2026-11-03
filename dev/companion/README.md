# Treasure Radar companion

## What it does

At map zoom 0 and +1 the game centres the tactical map on its own map cursor, and no mod code can read where that
is. The companion is a small Python program that runs next to the game and fills that gap:

1. The mod writes one line saying the map is open, where the map circle is, and where you are.
2. The companion looks at the map circle on your screen and finds your own icon (the yellow dot with the view cone).
   If the icon is not visible, it uses the 65 m grid lines instead.
3. It writes the world point at the centre of the map back to the mod, about 30 times a second.
4. The mod then draws its icons in the right place at every zoom level.

It also reads the zoom level from the grid spacing. If the mod's guess disagrees, the mod takes the companion's. The
companion reports a level only after two frames in a row agree on it. This holds even when the mod has lost the
level and sends `level=?`. In that case the companion takes the scale from the level it measured. At the most
zoomed-out level that also needs the map size; without it, it waits. If the mod sends the running mouse totals
(`cmx`, `cmy`), the companion uses them, so a missed line loses no mouse movement.

## How to run it

1. Double-click `run_companion.cmd` in this folder, before or during a mission. A console window opens and says
   `waiting for the mod`.
2. Play in **borderless fullscreen** (or windowed), on any monitor. The companion (1.3) finds the game's window by
   its title and captures relative to it; the console says `capture: the game window ...` once it has found it.
3. To stop it, close the window or press Ctrl+C. You can leave it running between missions: while the map is
   closed it only checks the mod's file 10 times a second.

It needs Python 3 (tested with 3.13). Pillow is already in `dev\tools\_pylib`, and the .cmd points Python at it, so
there is nothing to install. If Windows says `'python' is not recognized`, install Python 3 from python.org and tick
"Add python.exe to PATH".

A note on the **Microsoft Store Python**: it is an app package, and Windows redirects what it writes under
`%LOCALAPPDATA%` and `%APPDATA%` into the package's own folder, where the game never looks. That is why the mod and
the companion exchange their files in `%LOCALAPPDATA%\Temp`, the one folder the redirection leaves alone. The
companion notices the Store build at startup and prints a short note; it runs all the same. If the mod's log
(`%LOCALAPPDATA%\treasure_radar.log`) shows no `companion:` lines while the companion says `active`, install Python
from python.org and start `run_companion.cmd` again.

## What it can and cannot do

**It can:**
- Find your own icon in **yellow**. This is measured and tested on your screenshots.
- Find other slot colours (orange, green, blue, pink) as a **best effort**. They count only when they show a view
  cone and sit near where the companion expects the map to be.
- Find your icon when another icon covers part of it, or when it touches a yellow objective marker (companion
  1.2). About a third of the disc and its view cone must still show.
- Keep the map tracked from the grid lines and your mouse movement when your icon goes off the visible circle. For
  this it must have seen your icon once since you opened the map or last changed zoom. Frames without a fix in
  between (the icon hidden for a moment) do not lose that.
- At the most zoomed-out level, fix the view from the grid lines alone (companion 1.2). The whole map sits on its
  centre there, so it needs neither your icon nor an earlier fix.

**It cannot:**
- Capture **exclusive fullscreen**. The capture comes back black or frozen. The console prints `black capture`, or
  (1.3) after 20 identical frames while the map is open `the capture is static: the game's window is not being
  captured (exclusive fullscreen? try borderless)`. Switch the game to borderless.
- Find the game when its window is neither titled `HELLDIVERS™ 2` nor in front with `HELLDIVERS` in its title. It
  then captures the primary screen, as 1.2 did (the console says `capture: the primary screen (no game window
  found)`).
- Find your icon while it is fully hidden under other icons, or while its view cone is. In those frames it falls
  back to the grid.
- Give a fix while the map is opening or the zoom is still moving, or when the grid lines are not visible. Those
  frames count as `none`.

**When fixes stop for a while** (mod 0.9.2): the mod keeps tracking from the last fix of this map open and moves it
with your mouse, until a new fix comes. It drops that when you close the map or zoom in from the whole map.

**While you pan or zoom** (mod 0.9.3): the icons at zoom 0 and +1 fade out, and fade back in once the map has been
still for 0.2 s and your icon has fixed the view again.

**Without the companion:** the mod draws nothing tied to the world at zoom 0 and +1. Zoom -1 (the whole map) never
needed it.

## Privacy

- It reads only the pixels of the map circle: a 444 x 444 px square at 1080p, and only while the mod says the map
  is open. It keeps a few of those squares as PNG files in `%LOCALAPPDATA%\Temp\treasure_radar_frames` (the first
  three of every map open and the frames that gave no fix, 100 at most per run; the folder is emptied at every
  start) so a wrong result can be looked at later. Nothing outside the circle is ever captured or saved.
- It writes one text file, `%LOCALAPPDATA%\Temp\treasure_radar_fix.txt`, holding a single line, and its own log,
  `%LOCALAPPDATA%\Temp\treasure_radar_companion.log` (what the console shows, plus one line per map open).
- It uses no network, reads no game memory, sends no keyboard or mouse input and installs no window hooks.

## How to tell it is working

When you open the map, the console prints `active: map open ...`. After that, every 5 seconds it prints a line like
this:

    12:15:53 148 frames in 5.0 s (29.6/s): dot 140, grid 8, none 0, last: how=dot level=0 V=(115.4, 211.2) err 0.6 m

- `dot` means your icon fixed the view.
- `grid` means the grid plus your mouse movement fixed it.
- `none` means that frame gave no fix.

Other ways to check:
- `run_companion.cmd --log` prints one line per frame.
- `%LOCALAPPDATA%\Temp\treasure_radar_fix.txt` changes about 30 times a second while the map is open.
- The mod's log, `%LOCALAPPDATA%\treasure_radar.log`, says `companion: mod line -> ...` once per game session and
  `companion: first fix read (seq N)` the first time a fix arrives.

If it keeps saying `idle: no mod file`, the mod is not writing `treasure_radar_mod.txt`. The installed mod must be a
version that talks to the companion (0.9.1 or later for the Temp folder).

## If icons are wrong

When the icons sit in the wrong place, or the companion says `none` for most frames, send these three things:

- the folder `%LOCALAPPDATA%\Temp\treasure_radar_frames` (the recorded map circles and `frames.txt`, which names
  the mod line and the fix line of each),
- `%LOCALAPPDATA%\Temp\treasure_radar_companion.log`,
- `%LOCALAPPDATA%\treasure_radar.log` (the mod's log).

Each recorded frame can be replayed by hand: take its line from `frames.txt`, and give the PNG and the mod line
(the second column) to the companion:

    run_companion.cmd --shot "%LOCALAPPDATA%\Temp\treasure_radar_frames\181107.512_seq0421_L0_none.png" --mod "seq=421 t=1107.512 open=1 level=0 class=small w=1920 h=1080 cx=1674.0 cy=819.5 rim=222.0 kz=1.4766 px=114.2 py=-210.0 mx=0 my=0 cmx=0 cmy=0 end" --once

It prints the fix line it would have written (the third column of `frames.txt`).

## For developers

- `detect.py` is the detector: the icon, the grid, and V.
- `companion.py` is the loop and the file protocol. The protocol is defined in `dev\docs\COMPANION_INTERFACE.md`.
- `test_detect.py` is the test suite: the screenshots table, the file protocol, and (1.2) the recorded frames in
  `fixtures\` (PNGs from the 2026-10-27 mission, with their mod and fix lines in `fixtures\frames.txt`):

      set PYTHONPATH=<repo>\dev\tools\_pylib
      python dev\companion\test_detect.py

- One detection on a screenshot, which prints the fix line (the shot may be a full screen or a recorded frame from
  `treasure_radar_frames`, the 444 x 444 circle box itself):

      run_companion.cmd --shot <screenshot.jpg> --mod "seq=1 t=0 open=1 level=0 class=small w=1920 h=1080 cx=1674.0 cy=819.5 rim=222.0 kz=1.4766 px=114.2 py=-210.0 mx=0 my=0 end" --log

- `--dir <folder>` uses another folder instead of `%LOCALAPPDATA%\Temp` (the two files, the companion log and the
  `treasure_radar_frames` folder all go there).
- `--once` runs a single cycle.
