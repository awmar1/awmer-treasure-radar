# Map research (2026-10-27): what the map is, what Lua can see, how 0.9 should place things

Written after the 0.8.3 run. Inputs: the five screenshots of 10:32-10:36 (worlds 4 and 7), the older measured shots
(005421, 0027xx-0032xx), the 0.8.3 log, and three web research passes (HellForge and the data tools; every open-source
HD2 Lua mod that could be found, including the dead memory-era ones; the Stingray engine's Lua API). Nothing was
downloaded or run; sources are in section 8.

## 1. In short

- The map has three zoom levels on every map, big ones included. Level -1 is "the whole map in the circle", levels 0
  and +1 are fixed scales that do not depend on the map's size. A bigger map therefore shows more metres at -1 and
  the same 300 m / 150 m window at 0 / +1. 0.8.3's big-map model (extra levels, a pin at -3) was wrong; the five
  extra down-notches did nothing in the game.
- The conversion rate is one table (section 3): pixels per metre = Z(level, map size) x screen height / 1080. The
  circle's radius is 0.2056 screen heights at any HUD scale. That is all the "resolution" there is.
- At -1 the view is always centred on the map's origin, so placement needs only the scale. That is why -1 works.
- At 0 and +1 the view is centred on the map cursor, and nothing in Lua can read where that cursor is. The map is
  native C++ (the game ships 11 engine Lua scripts and no HUD Lua); the one mod that ever placed icons on it, the
  memory-era Treasure Map, read the HUD manager's memory, which no Lua 5.1 mod can do since game version 7.2.0.
  Dead-reckoning the cursor from the mouse (what 0.8 does) works to about 2% once the start point is known; the
  start point is the part that cannot be learned cheaply (section 5).
- So the efficient build is: draw the world icons at -1 only, where they are exact on every map size, with the
  scale picked by the map's size class; keep the compass and the legend at 0 / +1; drop the cursor model, the
  clicks, the trust maths and the "open rule" (section 7). Most of view.lua goes away.

## 2. What the shots say

Measured with a grid-period script (the game's grid lines are 65 m apart, anchored on the origin), 1920x1080,
HUD Scale 0.9. "cell" = pixels per 65 m grid cell.

| shot | world | map | time in log | cell (px) | px/m | level |
|---|---|---|---|---|---|---|
| 20261027103215_1 | 4 (5987 units) | small | open 15, 445-464 s | 96 | 1.477 | 0 |
| 20261027103219_1 | 4 | small | open 15 | 96 | 1.477 | 0 |
| 20261027103227_1 | 4 | small | open 15 | 96 | 1.477 | 0 |
| 20261027103607_1 | 7 (13697 units, loot 366 m out) | big | about 684 s | 36 | 0.554 | whole map |
| 20261027103618_1 | 7 | big | about 695 s, after the "pin" | 36 | 0.554 | whole map |
| 20261027005421_1 (0.8.2 run) | 12 (15640 units, loot 360 m out) | big | 4022 s | 36 | 0.554 | whole map |

Two big maps, three shots, the same 0.554 px/m. The 0.8.3 "pin at -3 after 5 down-notches" drew at 0.554 by
construction, which is why the icons in 103618 sat on the right spots: the game was at its bottom level (-1) the
whole time, and the model's -3 happened to carry the right number.

Levels 0 and +1 on big maps were not in today's shots. The 0.8.1 run measured the same 96 px cell at level 0 on a
big map (memory note), and the memory-era Always-On Map mod exposes exactly three fixed map zooms, "Whole map,
x1.5, x3" (source 8.5). 1.4766 / 1.5 = 0.984 and 2.953 / 3 = 0.984: the game's level 0 and +1 are a x1.5 and a x3
of one base scale, and +1 is exactly twice level 0. The whole-map level is a fit (rim / map radius), not a fixed
factor: 0.7805 / 0.984 = 0.79 on the small map, 0.554 / 0.984 = 0.56 on the big one.

## 3. The conversion rate

Everything is in screen heights, so one table serves every resolution; multiply by h / 1080 for pixels.

| level | what it shows | px per m at 1080p | per 65 m cell | window radius |
|---|---|---|---|---|
| -1, small map (R about 285 m) | the whole map, centred on the origin | 0.7805 | 50.7 px | the map |
| -1, big map (R about 401 m) | the whole map, centred on the origin | 0.554 | 36.0 px | the map |
| 0 | a window centred on the map cursor | 1.4766 | 96.0 px | 150 m |
| +1 | a window centred on the map cursor | 2.953 | 192.0 px | 75 m |

- Circle: centre as hud.lua already places it (from hud_offset, hud_scale, hud_map_position), radius 0.2056 h. The
  rim does not change with HUD Scale (hud.lua), so the px/m above do not either. 1440p: x1.333; 4K: x2.
- Screen = circle centre + (world - origin) x px/m at -1, with y flipped as draw.lua does now. Icons past the rim
  are clipped by the circle, not clamped (the memory-era mod skipped them too).
- Map size class. Only two have been measured. Unit counts from the log's "world N: mission (K units)" line:

| class | whole-map px/m (1080p) | unit count seen | farthest loot seen |
|---|---|---|---|
| small | 0.7805 | 5274-9029 (24 mission lines, 0.6.0 and later) | under 295 m |
| big | 0.554 | 13264-21114 (6 lines: worlds 7, 10, 13, 18 in 0.8.1; 12 in 0.8.2; 7 in 0.8.3) | 298-366 m; the player stood 390 m out on world 12 |

  Pick the class by unit count (threshold 11000: the gap between 9029 and 13264 is wide) and log the pick with the
  count and the loot extent. Only sessions from 0.6.0 on count the same way; the 0.5.1-era lines (15000-26500 units
  on maps that looked small) came from that mod's own census and do not compare. Mission types not yet played with
  0.6 or later (eradicate / defence arenas, anything far above 21114 units) are unmeasured: a count below 4000 or
  above 24000 draws nothing at -1 and logs "map size not measured (K units)". One screenshot at the whole-map level
  calibrates a new class: the cell width in pixels / 65 is its px/m.

## 4. What the research found

HellForge (SkyeShade; source 8.1). An offline, LAN-only way to run the game against a local backend, with a C mod
SDK, an in-game editor and a Lua bridge for old HD2Runtime / Bingus mods. It blocks the game's network and is not
a loader for the live game. Its docs say nothing about the tactical map, zoom, scale or the cursor. It does name the
UI / stratagem icon archive (007e093ca718ca1a) and says its editor's weapon silhouettes are "the game's HUD sprites".
Not useful for placement; possibly useful later for icon textures (DSAR reading is a separate problem).

Data tools (8.2). Filediver reads the current slim bundles (DSAR, LZ4 chunks, bundles.NN.nxa index) and ships a hash
list; hd2-srkit is a small Python reader/writer tested on the current build. No tool names the game's Lua scripts
or the map's icon textures. There is no Stingray-specific Lua decompiler; since build 25988413 the game runs stock
PUC Lua 5.1.4, so ordinary 5.1 tools would apply if there were HUD Lua to decompile. There is not: boot-mod-loader
states the game ships only 11 Lua scripts, all engine plumbing (wwise, animation, gwnav), and the public hash list
has no hud_map, tactical_map, minimap, marker or ping script. The HUD and the map are C++.

Mods that touched the map (8.3, 8.4). Exactly one ever read the map's state: Treasure Map 1.x (Bingus loader,
LuaJIT ffi + ReadProcessMemory). Its body.lua is public and gives the map's shape: inside the HUD manager, a view
block with center x/y, pan x/y, one zoom float and an open flag; a frame block with size, shown, scale and screen
x/y; and a flat affine projection

    left = center - pan;  screen = frame centre + (world - left) x zoom x frame scale

with no camera matrix and the comment that the map "follows your helldiver, or you pan it". That is the same model
0.8 fits from the mouse: a centre point, a pan vector, a scale per level. Every other post-7.2 mod (Treasure Radar
0.6/0.7, Objective Tracker, the chat and loadout mods) stays off the map; the Chef loader's docs say outright that
nothing readable reveals the map's open state, and the loader scans units for cameras, mouse axes ('mouse', 'wheel',
'cursor') and draws with World.create_screen_gui, which is what this mod uses.

The engine's Lua API (8.6). Stock Stingray has no way to enumerate cameras, GUIs or materials, and no getters on
Gui, Material or Viewport. The only read-backs are World.debug_camera_pose (the pose of the last camera that
rendered a world), Unit.camera on units that carry one, and Application.main_world. In Fatshark's Stingray games
the map-like views are Lua tables plus a Camera; in Helldivers 2 the zoom and pan are floats in a C++ struct, so no
Camera object carries them. One cheap probe remains and is worth a single build: read World.debug_camera_pose on
each world while the map is open and see whether any pose changes with the wheel or the mouse. If one does, the map
is rendered through a camera and its pose is the cursor; if none does (likely: a 2D GUI of a 2048x2048 texture,
see minimap_resolution in the user settings), the matter is closed.
Done (0.9.0, 2026-10-27): the probe found one static top-down camera at (0, 0, 501) on world 5 and nothing that follows
the map at any level or mouse move, so the matter is closed; 0.9.1 removed the probe.

## 5. The open point at 0 and +1

The 0.8.2 review's evidence stands: the cursor opened on a stored point, near the origin early in a mission, on the
player's spot by world 6's eighth open, and still on that spot at world 9's first open 160 m from the player. The
memory-era layout explains it: the game keeps a "center" (which it sets to the helldiver's position, the "follows
your helldiver" of its comment, evidently not at every open) and a "pan" (the mouse), and the cursor is
center - pan. A new mission does not necessarily reset center (world 9), and pan carries across closes.

What this means for dead reckoning: the mod can integrate pan from the mouse (gains measured, error 0.3% of the
trip) but it cannot see when the game rewrites center, and it cannot see center's starting value. Each guess
(origin, last marker, player, carry) was tried or examined in 0.8.0-0.8.3 and each is wrong some of the time, with
icons 100-300 px off when it is. The cursor label ("NE (48 deg) 35 meters") measures from the open point and would
settle it, but it is drawn by the game and unreadable. The section 7 test in REVIEW_0.8.2.md would pin the rule in
one mission; the player has said that test is not viable for them, and even with the rule known, a stale center
(world 9) stays undetectable. Conclusion: 0 and +1 cannot be made reliable without a read of the HUD's memory,
which the anti-cheat rules out.

## 6. What 0.8.3 got wrong

- Big maps have three levels, not "unknown, at least -3". NB, PIN_NOTCHES, the -1 / -2 "scale not measured" holes
  and the "level pinned at the bottom (-3)" line all go.
- The 'unknown' open rule hid the icons at 0 / +1 on purpose and lost T at every open; the alternative rules
  ('marker', 'player') are both contradicted by shots. None of the three is a product.
- The level tracker is right in principle (one step per frame, the wheel stops at both ends) and stays; with three
  levels it is sure as soon as the wheel hits an end, which on a big map is the first thing the player does.

## 7. Proposal for 0.9: the whole-map radar

Build:
1. view.lua: three levels on every map. Scale table from section 3, times S.h / 1080. Level -1 draws the world
   icons centred on the origin; levels 0 and +1 draw none (the legend stays, and the compass strip keeps pointing
   at the nearest loot while the map is open, as it does now). No T, no trust, no err, no open rule, no clicks.
2. Map size class from the world's unit count at the mission line (threshold 11000; both classes' scales from
   section 3), logged once per mission as "map: K units, loot N m out: big map, whole map at 0.554 px/m". Unmeasured
   class: nothing at -1, one log line, one screenshot calibrates it.
3. Keep: the open / closed tracking in mapview.lua (Tab toggle, world-list veto, the camera-versus-mouse corrections
   for ignored presses); the wheel-notch level tracker with its "sure once the wheel hits an end" rule; the compass,
   legend, markers, pings as they are.
4. Drop (move to dev/src/retired): T and its doubt model, place() / pinged() trust gates, the click handling, the
   open rules and C.OPEN_RULE, the big-map pin, take-back reasons about T. The hover label and click-to-waypoint
   were already off by default and go with T.
5. One probe line, off in normal play: World.debug_camera_pose per world while the map is open, logged once a
   second for one mission, to close the camera question of section 4. If a pose follows the wheel, 0.10 can place
   icons at 0 / +1 from it. (Done in 0.9.0: a static camera at (0, 0, 501) on world 5, nothing follows the map;
   the probe is gone in 0.9.1.)
6. Sim and harness: scenarios for the three levels on both classes, a 2-notch frame, an ignored Tab, a 1440p and a
   4K run of the scale table; the harness's map08big scenario rewritten for three levels.

Not building: any per-player calibration, extra keys or dropdowns, anything that reads or writes game memory,
input injection, auto-pings.

Risks: a third map class appears (hidden until one shot, as above); a HUD Scale other than 0.9 shifts the circle
(hud.lua's model covers it, measured at 0.75 / 0.85 / 1.25); a resolution that is not 16:9 (the circle's position
comes from hud_offset; the scale is per screen height, unaffected).

## 8. Sources (read-only web, 2026-10-27)

1. HellForge: https://github.com/SkyeShade/HellForge , https://hf-mod.com/ (v0.3.0-beta, 26 Oct 2026); docs/modding/data.md, docs/internals.md.
2. Filediver https://github.com/xypwn/filediver (v0.7.64, slim support since Dec 2025; DSAR / DSAA layout in its pkg.go.dev docs); hd2-srkit https://github.com/deepseekv41flash/hd2-srkit ; HD2SDK CE https://github.com/Boxofbiscuits97/HD2SDK-CommunityEdition ; Hellextractor https://github.com/Xaymar/Hellextractor (archived, name lists); Helldivers2-Hashlist https://github.com/HW12Dev/Helldivers2-Hashlist ; boot-mod-loader https://github.com/pat-pat-patrick/boot-mod-loader (11 Lua scripts; stock Lua 5.1.4 since build 25988413).
3. Treasure Map (memory era, the map's layout and projection): https://github.com/Th3chef/Treasure-Map/blob/main/src/lua/body.lua ; the Chef loader's modding notes https://github.com/Th3chef/Chef-Shared-Loader ; Treasure Radar 0.6 / 0.7 https://github.com/Th3chef/Treasure-Radar .
4. Post-7.2 probe log of what crashes and what works: https://github.com/MrChengl11/hd2-lua-mod-skill/issues/1 ; Bingus loader docs https://github.com/CowboyBingus/BingusSharedLoader ; HD2Runtime https://github.com/SkyeShade/HD2Runtime .
5. Always-On Map (three fixed map zooms "Whole map, x1.5, x3"): https://www.nexusmods.com/helldivers2/mods/16680 (page body blocked to fetchers; the zoom list is in its snippet).
6. Stingray Lua reference: World, Unit, Camera, Application, Viewport, Gui, Material, Window pages under https://help.autodesk.com/cloudhelp/ENU/Stingray-Help/lua_ref/ ; Fatshark's public Stingray Lua for how map-like views are built on this engine: https://github.com/Aussiemon/Darktide-Source-Code (scripts/foundation/utilities/script_world.lua, scripts/managers/camera/camera_manager.lua, hud_element_tactical_overlay.lua).

## 9. Other routes for 0 / +1, weighed (asked after the write-up)

What the mod can read while the map is open: raw mouse counts and wheel notches, mouse buttons and keys, the camera
pose, the player's position, every loot / objective unit, the world list, and any file through io. What it cannot:
the map cursor, the marker (a click puts a marker at T, and nothing readable says where T was: view.lua's header),
the cursor label, the hover highlight, pixels.

| route | what it would give | what it costs | verdict |
|---|---|---|---|
| Marker / ping anchoring | T exact at each click | nothing readable: the marker's position is not exposed | dead |
| Edge-slam anchoring: a hard flick to one side pins the cursor at the rim (the view clamps, then the cursor stops 0.183 h out), so one flick per open sets T; dead reckoning carries it (0.3% of the trip) until the game moves its own centre | T within a few m after each flick | a gesture per open; one shot to measure the pin point per level; drifts whenever the game rewrites its centre, which the mod cannot see | works, finicky, a ritual |
| Passive version of the same: re-anchor whenever the mouse travels more than the map's width one way | occasional free anchors | nothing, but rare in normal play | a bonus, not a product |
| The other map navigation mode (hud_map_navigation_mode 0): the cursor may move over a view that pans only at the edge, so the view's start might be deterministic | maybe a known start point | a game setting change and one measuring mission; the web says nothing about the modes | unknown |
| World.debug_camera_pose while the map is open | the view's pose, if the map renders through a camera | one probe line in a build | done in 0.9.0: nothing (a static camera at (0, 0, 501) on world 5) |
| A companion program outside the game that captures the game window as streaming software does, finds the yellow player dot (the mod knows the player's world position, so one dot fixes T) or the 65 m grid phase when the dot is off-screen, and hands T to the mod through a small file the mod reads with io | T exact, every frame, both levels | a second program running beside the game, 20-50 ms of lag, a detector that must survive HUD scale and resolution, and the player's own call on running a screen reader next to an anti-cheat (no memory, no input, but still a helper) | the only exact route; a project of its own |
| Any read of the HUD's memory | everything | the anti-cheat; ruled out | no |

## 10. 0.9.2 (2026-10-27): the hold, more fixes, a line probe

- **Companion 1.2** (dev/companion/): a dot partly under an icon or the frame's edge still fixes (30% of its disc,
  err hypot(grid, 2.5)), the cone no longer pads the dot's hue, -1 gets a grid fix within 8 m of the origin, and the
  last dot is kept as the grid's prior. 16 of the 74 recorded 'none' frames now fix; the open animation's frames stay
  none (COMPANION_INTERFACE.md, v1.2 behaviour; fixtures in dev/companion/fixtures/).
- **The hold** (view.lua, CONTRACT.md): a fix is fresh for 45 writes of a 128-write ring (0.9.1: 15 of 32), the
  distance gate is gone, and a fix from before a write at -1 is refused. When fixes pause, the last fix's V is carried
  on by the mouse counts (section 9's dead reckoning, 0.3% of the trip), clamped where the game stops the view and the
  cursor (R_map - rim / k, then 0.183 h px more). It drops at the close, a new mission, out of a mission, when its
  writes leave the ring, and at a zoom in from -1.
- **The line probe** (lineprobe.lua, one mission, then removed): section 4 found the open map in a world of its own
  (world 5's static camera at (0, 0, 501)). Can a line object made in that world draw on the map? Every mission frame
  the probe dispatches into each world but the main one, through a line object of its own, a yellow circle around the
  player, 2 m up, with a north tick and a cross; a 3 m circle through the loader's own line object is the control. A
  world's radius is 10 + 10 i m, i its place in the list it came in (the next 10 m up if a listed world has that one),
  kept while it stays listed. The worlds that leave the list (the open map's own comes and goes with every open) are
  forgotten untouched, without World.destroy_line_object, which the loader never calls; one that comes back gets a new
  line object. What to look for, map open at -1, 0 and +1 plus one shot with it closed: the 3 m circle at the feet (the
  line path works at all); any yellow circle on the map (its radius names the world in the log's list lines; whether it
  sits on the player's dot and scales with the level says whether that world shares the game's coordinates); or
  nothing. The log's `lineprobe:` lines list the worlds with their radii (the first 20 lists) and, every 30 s, the radii
  dispatched to and the line objects made; `off:` says why it stopped (a missing function, 10 errors, 500 made). If a
  circle lands on the map at the player's spot, 0.10 can draw at 0 / +1 in the map's own world without a companion; if
  not, the route is closed and the companion stays the only one.
- **Field test 2026-10-28** (one small-map mission, 6 min, the companion running, the game on the second monitor): the user saw the yellow circle at
  their feet in 3D, no circle on the tactical map or the minimap at any level, and the world icons at -1 only.
  - *The line probe: the route is closed.* The mission ran with 7 engine worlds (8 at the last, cold open: the loader's
    top world), the probe dispatched its circle into every one but the main world every frame (radii 30-90 m, 6-7 line
    objects made, 0 errors, `stopped (out of a mission)` at the end), the map was opened 8 times at -1, 0 and +1, and
    the 7 screenshots of the minimap at all three levels show no yellow circle while the 3 m control circle through the
    loader's line path drew (the yellow line across the ground in every screenshot). No world a Lua line object can
    reach is rendered onto the map, the loader's own top world included. Remove lineprobe.lua in the next build; the
    companion stays the only route to 0 / +1.
  - *0 / +1 stayed blank because the companion never saw the game.* The link worked (the mod logged the two paths and
    `first fix read (seq 1)`; the companion followed every open with the right level and class, 2,700 frames at 28/s),
    but every frame came back `how=none`, no dot and no grid. The 100 recorded frames are two distinct images, both a
    dark desktop window (a chat-style panel with a close cross and a microphone button) where the map circle should be:
    the companion captures the primary screen, and this mission was played on the second monitor, so the box held
    a window on screen 1 and never the game (on 2026-10-27 the game was on screen 1 and the same capture saw it). Its
    only sanity check is for a black capture, so it reported nothing. With no fix ever read, the hold had nothing to
    hold: FRESH 45, the dropped gate and the dead reckoning were not exercised, neither proven nor disproven. A
    mission on screen 1 with 0.9.2 as it is tests them without a new build.
  - *Next build (0.9.3):* drop lineprobe.lua; find the game's window and capture relative to it (offset the box by
    the window's origin on the virtual screen, so the game on any monitor is seen) instead of assuming the primary
    screen; and refuse a static capture: many identical frames while the mod says the map is open means the capture
    does not see the game, and the console should say so.
- **Field test 2026-10-28, second mission** (small map, world 4, 7 min, the game on screen 1, 0.9.2 as it is; log
  lines 8413-8647, companion log 08:54-09:00, 61 recorded frames, 6 screenshots 085803-085838). The pipeline works:
  8 opens, every one got a dot fix within 0.3-0.5 s when the player stood still (err 0.5-0.7 m; V 0.9, 0.1 at
  open 1 with the player 10 m off the centre), the level came from the fix twice ("the mod had 1", "the mod had -1"),
  the hold carried V for 5-443 writes and up to 264 m of pan, and the icons were "super accurate" when they showed.
  The user's three complaints, all at 0 / +1, and what the data says:
  - *Icons never show while moving.* Opens 6 and 7 were made while walking (px moving 1-2 m/s), at level 0: 12 and
    19 frames, every one `none`, nothing drawn; open 7 then zoomed out to -1 and got 31 dot fixes at once while still
    walking. The recorded frames (085908.139/.242, 085951.608) show the full map at level 0, the cursor bracket at
    the centre, the readout "0-2 meters" (the cursor on the player), and **no yellow disc anywhere near the centre**,
    where open 1's frame (standing, "1 m") has the disc and its cone right by the bracket. So at the zoomed levels the
    game does not draw the own marker (or not yet, within the 0.5-1.1 s these opens lasted) while the player moves;
    the dot detector has nothing to find, the grid alone gives V modulo 65 m with no prior, and the hold is dropped
    at every close, so a short open made on the move at 0 / +1 draws nothing. At -1 V is the origin and the icons
    always draw.
  - *Jitter at 0 / +1 while the mouse moves.* V is the last fix's V plus GAIN times the counts of the writes after
    it, and every new fix (every 3-7 writes, 15-20 fixes/s) snaps V to its own value. A fix's seq is the mod line the
    companion read just before the capture, but the pixels hold whatever the game had applied by then (its own input
    latency and pan easing), so each fix carries a timing error of up to about one frame of mouse motion: at a brisk
    pan of 1,000 counts/s that is 50 counts = 12 m = 18 px at level 0, and the icons jump by that on every fix, in
    both directions. Grid fixes (open 5: 267 of 812 frames, err 3.5-18 m = 5-27 px) and the dot/grid/hold switching
    add jumps of their own. The jitter is the sampling, not a bug in one constant: no filter on the fixes was
    written (0.9.2 takes each fix as is).
  - *Misplaced after a pan.* Three sources seen: (1) grid fixes resting on a wrong prior, several with V on the
    view's stop on both axes (-135.2, -135.3; -135.3, -134.7: the clamp corner, 285.3 - 222 / 1.4766 = 135 m), i.e.
    the prior was pushed into the corner and the grid phase kept it there; (2) the player out of the window: at
    "200-304 meters" (screenshots 085825-085838) the own disc is outside the 222 px rim (150 m at level 0, 75 m at
    +1), so only grid fixes come, with the prior's error; open 5's level +1 stretch was 88 of 89 frames `none`;
    (3) the level: for up to ADOPT_QUIET after a notch the mod draws at its own level, and twice this mission it
    had the wrong one until the fix corrected it (icons at 2x the right distance from the centre). A hypothesis not
    yet tested: the game's view follows the player while the cursor is pinned to them (no mouse since the open),
    which the hold (mouse counts only) would miss by the player's displacement (open 5: 33 m of walking = 49 px).
    One log line comparing a fresh fix's V with the previous one while mx = my = 0 and the player moves settles it.
  - *Verdict.* At 0 / +1 the game owns the view (cursor-centred, mouse-driven with its own easing, pinned to a
    moving player, stopped at the edge) and tells the mod nothing; a screen read at 15-20 fps with a frame of lag
    can only estimate it, and it loses the anchor whenever the own disc is not drawn or not in the window. The
    icons there will always be a sampled, lagging estimate. Plan: dev/docs/PLAN_0.9.3.md.

## 11. 0.9.3 (2026-10-28): B, settle-and-show, and the mod complete without the companion

Built from the brief in dev/docs/PLAN_0.9.3.md (section "The build"), verified offline, not yet field-tested.

- Without the companion the mod is complete: the whole-map level (-1) draws every icon at its exact spot from the
  manager alone, at any resolution (sizes in screen heights, HUD offsets from the game's settings). At 0 / +1 nothing
  world-anchored draws, the legend and compass stay, and the log says once per session "no companion fix this
  session: world icons at the whole-map zoom only". The companion is optional and nothing else needs running.
- With the companion, 0 / +1 use direction B: icons hide while the view moves (mouse counts or a wheel notch within
  0.2 s) and come back after a dot fix of a later write, with the level sure; grid fixes count only within 32 m of
  the hold, never on the view's stop, never before an open's first dot fix; fixes ease into place (1.5 m dead band,
  0.1 s, snap beyond 25 m) instead of snapping. Calm, not glued: the ceiling named in section 10 stands.
- Companion 1.3 captures relative to the game's window (FindWindowW, client rect, per-monitor DPI), so any monitor
  works; 20 identical frames while the map is open print a static-capture warning. Interface v1.2 unchanged.
- lineprobe.lua retired to dev/src/retired/ (section 10: the line-object route is closed).
- Menu: Outside the Map (radar + compass / no radar / map only), Legend (with the map / always / off), 14 tick boxes
  for the loot kinds and the map categories (none ticked in a group = all shown), Corner Radar Size.
