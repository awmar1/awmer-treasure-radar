# Module simulator

Runs the addon's modules straight from `dev/src/addon` against a fake Chef Loader (`chef_sim.lua`) and renders what
they draw. It's for building and checking views quickly; the full pipeline test (bundle, patch, the real loader in the
harness) is `dev/harness`.

```
python -I dev/src/sim/sim.py --list
python -I dev/src/sim/sim.py walk
python -I dev/src/sim/sim.py map --frames 30,170 --options "{\"overlay\": true}" --hits
python -I dev/src/sim/sim.py walk --size 2560x1440 --out some/dir
```

Output in `dev/out/sim/<scenario>/`: `frame_NNNN.png`, `map_NNNN.png` (open map, 2x), `top_NNNN.png` (compass band,
2x), `sheet.png`, `log.txt`, `warnings.txt`, `stats.txt`.

- Modules load in `modules.txt` order; any other `.lua` in `src/addon` loads just before `main`, so a new module runs
  without editing `modules.txt`.
- Textures: every PNG under `dev/src/textures` (`T.TEX[name] = name`).
- Scenarios: `SCENARIOS` dicts in `scenarios/*.py`; the fields are listed in `scenarios/base.py`. Add your own file
  rather than editing someone else's.
- The HUD settings file `hud.lua` reads is written under `<out>/appdata` from the player's own settings
  (`sim.HUD_DEFAULT`), overridable per scenario (`hud`).
- `%LOCALAPPDATA%` is `<out>/localappdata` (with a `Temp` subfolder, where the companion's two files go since 0.9.1),
  emptied of `treasure_radar*` files at the start of every run, so the radar's zoom file and the companion files
  never reach the player's own folders.
- The raw mouse axis (`Mouse.axis_index('mouse')`, `Mouse.axis`) gives the scenario's `raw_mouse` movement.
- Warnings it catches: colors used in a later frame than made (they draw white in game), top-layer draws while the
  map is closed (the loader drops them), bitmaps of unknown textures, draws without a color.
- Stand-ins (not the game's real look or geometry): the background, the game's open map (a disk at `hud.map`), the
  game's compass (a tick band at the top center), the loader's pixel font.
- `chef.world_to_screen` is a pinhole projection with the scenario's `fov` (vertical, default 70 degrees) and the
  real loader's "behind me" rule (`dot(v, f) <= 0.5` is nil).
- `chef.watch` lists finish 4 frames after they start, every `every` s, like the loader's spread-out scans.
- Script use: `import sim; s = sim.Sim(scenario_dict); s.run([frames])`, or `s.step(f)` then `s.render(f, draws)`.

## Stand-ins for modules that aren't written yet

A scenario's `lua` field is Lua run once after the modules load, with `T`, `chef` and `SIM` in scope. Use it to set
`T.mod.objectives = { marks = { ... } }` or `T.mod.pings = { waypoints = { ... }, icon = function(cx, cy, size, alpha,
layer) ... end }` so a view can be checked before the real module exists. Stand-ins get no update/draw calls.
