# Treasure Radar build tools (`dev/tools`)

These tools take a packaged Treasure Radar apart, put it back together byte for byte, and package new versions
from source (`dev/src`). You don't need the game for any of it, and nothing here ever writes into the mod folder
itself. Output goes to `dev/build/` (or to a folder outside the mod folder with `--force`).

| file | what it does |
|---|---|
| `patchlib.py` | Reads and writes Stingray patch archives (main file, `.gpu_resources` and `.stream`), plus murmur64a ids |
| `tex.py` | Converts PNG to and from a texture resource (uncompressed RGBA8, the form 0.5.1 ships) |
| `extract.py` | Dumps every resource of a mod folder: Lua as `.lua`, textures as `.png`, plus `index.json` |
| `luatools.py` | Lua 5.1 compile checks, and runs the loader's own discovery code on built archives |
| `bundle.py` | Joins the modules listed in `dev/src/addon/modules.txt` into the one addon Lua resource, with a line map |
| `build.py` | Packages a whole mod folder from a JSON build description |
| `builds/0.5.1.json` | Rebuilds the shipped 0.5.1 byte for byte (from the `extract.py` output) |
| `builds/0.6.0.json` | The 0.6.0 build: 0.5.1's loader renamed, the bundle and textures from `dev/src`, 40 option folders, images from `dev/src/images` |
| `builds/0.6.1.json` | 0.6.0 with the Tester probe's crash fix, its own version and Guid |
| `builds/0.7.0.json` | 0.7.0: everything on by default, five dropdowns (loot, objectives, radar, pins, opacity), 19 folders with core; no Tester |
| `builds/0.7.0-measure.json` | 0.7.0 plus the measuring logger (`measure.lua` in the bundle, on with `measure = true`; F12), for one mission |
| `builds/0.7.1.json` | 0.7.1: the radar turns with my view by default, a sixth dropdown (Radar Facing: `facing_turn`, `facing_north`), 21 folders with core; the map toggle kept in step by the mouse |
| `builds/0.7.1-measure.json` | 0.7.1 plus the measuring logger, for testing (`measure07`) |
| `test_roundtrip.py` | End-to-end checks (see [Tests](#tests)) |
| `_pylib/` | Third-party libraries: Pillow, and lupa with a real Lua 5.1. Nothing else gets installed |

Always run Python as `python -I -B`. `-I` (isolated mode) ignores the environment and the user site. `-B`
keeps `__pycache__` out of the tree. Each tool puts `_pylib` on its own path, so no setup is needed.

## Quick start (in `dev/tools`)

```sh
# 1. take 0.5.1 apart (already done: dev/reference/0.5.1/resources)
python -I -B extract.py ../.. ../reference/0.5.1/resources

# 2. rebuild 0.5.1 (proves the tools) -> dev/build/Treasure-Radar-0.5.1 and .meta
python -I -B build.py builds/0.5.1.json

# 3. build the new version -> dev/build/Treasure-Radar-0.7.1 and dev/build/Treasure-Radar-0.7.1.meta
python -I -B build.py builds/0.7.1.json
python -I -B build.py builds/0.7.1-measure.json        # the measurement build, for one mission

# only the addon bundle (no archive), e.g. while working on dev/src/addon
python -I -B bundle.py --version 0.7.1                 # -> dev/build/bundle/treasure_radar.lua + .map.txt
python -I -B bundle.py --where 345                     # bundle line 345 -> 'hud.lua:120' (uses dev/build/bundle/treasure_radar.map.txt)
python -I -B bundle.py --where 345 ../build/Treasure-Radar-0.6.0.meta/core.mods.chef.treasure_radar.map.txt   # a build's map

# 4. everything at once
python -I -B test_roundtrip.py
```

Other commands:

```sh
python -I -B patchlib.py info ../../core                 # list an archive's types and resources
python -I -B patchlib.py check ../..                     # parse + rewrite every archive, compare bytes
python -I -B tex.py info some.png | some.toc
python -I -B tex.py encode in.png out.toc out.gpu        # the two parts of a texture resource
python -I -B tex.py decode in.toc in.gpu out.png
python -I -B tex.py selftest
python -I -B luatools.py compile a.lua b.lua             # Lua 5.1 syntax check
python -I -B luatools.py discover <loader.lua> <option folder>...   # what the loader finds, deployed in that order
```

## How the mod reaches the game (what the tools assume)

* The mod folder is what Arsenal installs. It holds `manifest.json`, `thumbnail.png`, `images/`, and one
  folder per manifest option (29 in 0.5.1). Each option folder holds one patch archive,
  `9ba626afa44a3aa3.patch_0`, with its `.gpu_resources` and `.stream` files.
* Arsenal deploys every ticked option's archive as `data/9ba626afa44a3aa3.patch_<N>`, N = 0, 1, 2, ...
  **Assumed, not observed:** the numbering follows the manifest order. The build's discovery check deploys in
  that order. The loader doesn't depend on the order, except that the options are merged in it, last one wins.
* Patch resources replace game resources with the same id. The `core` option carries the loader under the id of
  the game's `boot` script (`f476df93691895fa`), so the game runs the loader. The loader then scans
  `data/9ba626afa44a3aa3.patch_0` to `_4095`, giving up after more than 40 missing numbers in a row. In each file it looks at
  every Lua resource:
  - The size field must be 8 to 4 MiB (8 bytes of prefix plus the text), and the flag must be 2.
  - The text's first 112 bytes must match `^-- HD2-(%a+): ([%w_/%.%-]+)`.
  - The path must match `ALLOW = '^mods/chef/treasure_radar'`.

  It collects `Addon` and `Options` resources and sorts the addons by name. When two addons share a name, the
  second is skipped. Each addon runs with `loadstring(src, '@' .. name)`, so runtime errors read
  `mods/chef/treasure_radar:<line>:`. It gets the options of every `Options` resource with the same path,
  merged one level deep: tables merge key by key, anything else is replaced.

  None of this uses resource ids or names. `luatools.loader_discover` runs exactly this code (cut out of the
  loader's source) under Lua 5.1.

## Patch archive format (all little-endian)

Worked out from all 29 archives of 0.5.1. `patchlib` writes exactly this layout, and parsing then writing gives
back the same bytes for every one of them, for all three files.

### Main file

**Header, 72 bytes**

| offset | type | value |
|---|---|---|
| 0x00 | u32 | magic `0xF0000011` |
| 0x04 | u32 | number of type rows |
| 0x08 | u32 | number of entries |
| 0x0C | u32 | unknown, always 0 |
| 0x10 | 56 bytes | unknown: all zero except u32 `0x7BEA` (31722) at file offset 0x20. Same in every archive; kept verbatim (`header_extra`) |

**Type rows, 32 bytes each.** One row per resource type, in ascending order of type id. The entries are grouped
in the same order.

| offset | type | value |
|---|---|---|
| 0x00 | u64 | unknown, 0 |
| 0x08 | u64 | type id: murmur64a of the type name. `lua` = `a14e8dfa2cd117e2`, `texture` = `cd4238c6a0c69e32` |
| 0x10 | u64 | number of entries of this type |
| 0x18 | u32 | 16 |
| 0x1C | u32 | **64 if the archive has any GPU or stream data, else 16** (the same as entry +0x48) |

**Entries, 80 bytes each.** Grouped by type. Within a type they keep build order, so the loader comes first in
`core`.

| offset | type | value |
|---|---|---|
| 0x00 | u64 | resource id: murmur64a of the resource name |
| 0x08 | u64 | type id |
| 0x10 | u64 | offset of the main part in the main file |
| 0x18 | u64 | offset in `.stream` (0 if there is no stream part) |
| 0x20 | u64 | offset in `.gpu_resources` (0 if there is no GPU part) |
| 0x28 | u64 | unknown, 0 |
| 0x30 | u64 | unknown, 0 |
| 0x38 | u32 | size of the main part |
| 0x3C | u32 | size of the stream part |
| 0x40 | u32 | size of the GPU part |
| 0x44 | u32 | 16 |
| 0x48 | u32 | 64 if the archive has GPU or stream data, else 16 |
| 0x4C | u32 | the entry's index: 0, 1, 2, ... |

**Data.** Main parts follow the table of contents. The first starts at the end of the TOC rounded up to 16, and
each next one at the previous end rounded up to 16. The gaps are zero bytes.

**End of the main file.** In the Lua-only archives (28 of them) it is padded with zeros to a multiple of 16. In
`core`, which has GPU data, it is not padded: it ends 4 bytes past a multiple of 16, right after the last
texture header. The writer's rule is "pad unless there is GPU or stream data". The 0.5.1 data can't tell that
apart from "pad when the last entry is Lua". `"archive": {"pad_main_end": true|false}` in a build description
forces it either way.

### `.gpu_resources`

GPU parts sit at multiples of 64, with zeros in between. This is observable: 29 of the 151 texture sizes are not
multiples of 64. The file ends padded to 64. That end padding is **not observable** in 0.5.1, because core's last
texture is already a multiple of 64 long. 0.5.1's `core` file is 19,430,784 bytes.

### `.stream`

Empty in every 0.5.1 archive, but always written, even when empty. Alignment 64 is assumed by analogy.

### Lua resource (main part only)

`u32 length of the text`, then `u32 flag` (2 = source text), then the text: no terminator, no BOM. The loader
uses only flag 2.

### Texture resource

The main part is 340 (0x154) bytes:

| offset | value |
|---|---|
| 0x000 | u32 0, u32 0, u32 `0xFFFFFFFF` |
| 0x00C | 15 × 12 bytes of stream mip table (u32 offset, u32 size, u16 height, u16 width), all zero |
| 0x0C0 | DDS header with DX10 extension: `'DDS '`, size 124, flags `0x100F`, height, width, pitch = width × 4, depth 0, mips 1, 11 × 0, pixel format {32, flags 4 = FOURCC, `'DX10'`, 5 × 0}, caps `0x1000`, 0, 0, 0, 0; DX10 {dxgi 28 = R8G8B8A8_UNORM, dimension 3, misc 0, array 1, misc2 0} |

The GPU part is the pixels: width × height × 4 bytes, rows top to bottom, in RGBA order, with no row padding and
one mip level.

All 151 textures of 0.5.1 are exactly this. Only the width, height and pitch vary: 49 different sizes, from 9×18
to 512×512, many of them not powers of two.

## Ids and names

An archive stores only 64-bit ids: `murmur64a(name, seed 0)` (`patchlib.resource_id`). The names the tools use:

| resource | name |
|---|---|
| the loader | `boot` (the game's boot script id, `f476df93691895fa`) |
| the addon | its header path, `mods/chef/treasure_radar` |
| an options file | `mods/chef/treasure_radar/options/<option folder>` |
| 0.5.1 textures | `<mod>/<field>` (`TEXTURES.disc`), `<mod>/sweep_<n-1>` (`TEXTURES.sweep[n]`), `<mod>/glyph<cap>_<byte>` |
| 0.5.1's 9 kind icons | **unknown.** They hash to none of these names, so `builds/0.5.1.json` gives their ids |
| bundle textures (new) | `treasure_radar/<path under dev/src/textures without .png>`, for example `treasure_radar/glyphs/12/48` |

`extract.py` keeps a name only after checking that it hashes to the id. 173 of the 182 resources in 0.5.1 have a
name.

A new texture id must never equal a 0.5.1 id or the loader's id. `bundle.py` and `build.py` check every new
texture id against every id in `dev/reference/0.5.1/resources/index.json` and against the archives in the mod
folder.

## The bundle (`bundle.py`)

`dev/src/addon/modules.txt` lists one module per line, as a path relative to the file, with or without `.lua`.
Lines starting with `#` are comments. A module may read `T.mod.<x>` at load time only if `x` is listed earlier.
The output has exactly this shape:

```lua
-- HD2-Addon: mods/chef/treasure_radar
-- Treasure Radar 0.6.0 (built from 8 modules)
local chef = ...
local T = { chef = chef, mod = {}, version = '0.6.0', TEX = {} }
T.TEX['glyphs/12/48'] = '1f0c...'           -- one line per PNG under dev/src/textures, sorted by name
T.mod['config'] = (function(...)
<config.lua, verbatim>
end)(T, chef)
...                                         -- one block per module, in modules.txt order
return T.mod['main']
```

Each module starts with `local T, chef = ...`; the bundle warns when it doesn't.

**The `.map.txt` file.** Rows have the form `b1-b2 <TAB> file-or-what <TAB> f1-f2|-`, mapping bundle lines to
module lines. `--where <line>` translates a game error line.

**Checks:**

* Every module, and then the whole bundle, must compile with Lua 5.1's `loadstring`. That catches `goto`, `//`,
  and other syntax from Lua 5.2 and later.
* A UTF-8 BOM is an error.
* `main` must exist.
* The bundle must be no larger than 4 MiB − 8 bytes.
* Texture names may use only `A-Z a-z 0-9 _ . - /`, and their ids must be unique and not reserved.
* These are warnings, not errors:
  - CR characters: the bundle keeps them. Lua 5.1 counts `\r\n` as one line, so the map stays right.
  - A `.PNG` written in upper case: the file is ignored.
  - A `.lua` file next to `modules.txt` that isn't listed.
  - A listed module that is missing. `--strict`, which is also the default inside `build.py`, makes this an
    error.

## Build descriptions (`build.py`)

```sh
python -I -B build.py <build.json> [--out DIR] [--force] [--no-discovery]
```

**Output.** The default is `dev/build/<"Treasure-Radar">-<version>/`:

* `manifest.json`
* the copied `files`
* one folder per option, each holding its three archive files

Next to it, `<out>.meta/` holds:

* each bundle and its map: `<folder>.<addon path with dots>.lua` and `.map.txt`, for example
  `core.mods.chef.treasure_radar.map.txt`
* `ids.json`: every resource, with its folder, kind, type, id, name, sizes and source
* `discovery.txt`: what the loader's own discovery code finds in the build

An earlier build in `dev/build` is replaced. If the build fails after that point (manifest or discovery check),
the output is left incomplete: don't ship it. Outside `dev/build`, a folder is deleted only if it holds a
`manifest.json` (or `ids.json`) from an earlier build. The mod folder is never written, even with `--force`.

### Schema `treasure-radar-build/1`

Paths are relative to the JSON file. Every string may use `{version}`, `{mod}` and `{title}`.

| key | meaning |
|---|---|
| `schema` | `"treasure-radar-build/1"` (required) |
| `version` | for example `"0.6.0"` (required; letters, digits, `. _ + -`) |
| `mod` | the addon path, default `"mods/chef/treasure_radar"` |
| `title` | default `"Treasure Radar"` |
| `out` | output folder (default `dev/build/Treasure-Radar-{version}`) |
| `manifest` | `{"template": path, "set": {key: value}, "options": [...], "add_options": [...], "ascii": true}`. It starts from the template, sets top-level keys, and replaces or extends `Options`. It is written as `json.dumps(indent=2)` with no newline at the end, the way 0.5.1's manifest is |
| `files` | `{"dest in the build": "source file or folder"}`, for example `images/` and `thumbnail.png` |
| `options` | Option folder names use `A-Z a-z 0-9 _ . -` and may not be `images` or `dev`. `{"<option folder>": [resources...]}`, or `{"<folder>": {"resources": [...], "archive": {"pad_main_end": bool, "header_extra": "<112 hex digits>"}}}` |
| `allow_reserved_ids` | `true` only to rebuild 0.5.1 itself: it allows texture ids that equal 0.5.1 ids |
| `comment` | free text (`"//"` works too, at the top level, in `manifest` and in any resource) |

**Resource kinds.** A resource is an object with a `kind`; a `comment` key is allowed on any of them.

| kind | keys | resource |
|---|---|---|
| `loader` | `file` or `text`, `set`, `replace` | Lua, id `boot`. Compile-checked; its discovery code is used for the check |
| `bundle` | `modules` (`dev/src/addon/modules.txt`), `textures` (`dev/src/textures`), `texture_prefix` (`treasure_radar/`), `name` (`{mod}`), `title`, `include_textures` (true), `strict` (true), `set`, `replace` | `bundle.py`'s output as the addon. It also adds a texture resource for each PNG, unless `include_textures` is false |
| `addon` | `file` or `text`, `name` (default: the header path), `set`, `replace` | Lua that must start with `-- HD2-Addon: <path>` |
| `lua` | `file` or `text`, `name` (required), `set`, `replace` | any other Lua resource |
| `options` | `value` or `text` or `file`, `for` (`{mod}`), `name` (`<for>/options/<folder>`) | An options file. `value` writes the 0.5.1 form: `-- HD2-Options: <for>`, a comment line, then `return <value>` |
| `texture` | `png`, `name` or `id`, `dxgi` (28) | one texture |
| `textures` | `dir`, `prefix` (`treasure_radar/`), `dxgi` | every PNG under `dir`, named `<prefix><path without .png>` |
| `raw` | `type` (`lua`, `texture` or a hex id), `name` or `id`, `main`, `gpu`, `stream` (files) | any resource, as stored |

**`set` and `replace`.**

* `"set": {"LOADER": "..."}` rewrites the one line that ends in `--@@LOADER@@`. That line has the form
  `local X = <old>  --@@LOADER@@`, and the value is written as a Lua literal. The 0.5.1 loader has `LOADER`,
  `FILES` and `ALLOW` markers.
* `"replace": [[old, new], [old, new, count]]` is a plain text replacement. It is an error if `old` is missing,
  or if it occurs a different number of times than `count`.

**What fails the build (exit code 1):**

* Lua that doesn't compile under Lua 5.1.
* An options file that doesn't return a table when run the loader's way (no globals, under `pcall`).
* A missing or wrong `-- HD2-Addon:` / `-- HD2-Options:` header.
* An id used twice anywhere in the build.
* A texture id that is reserved for 0.5.1 or the loader.
* A manifest `Include`, `Image` or `IconPath` that the build doesn't produce.
* A missing file, a bad id, or a JSON error.
* An addon or options resource that the loader's discovery doesn't find. The check runs twice:
  - with every option folder deployed in manifest order;
  - with only the loader's folder deployed (only if the build has a loader).

  It uses the build's own loader, or the 0.5.1 loader if the build has none.

The finished manifest must have `Guid`, `Name` and `Options`. Warnings, not errors: an option folder that no
manifest option includes, and more than one folder carrying the loader.

**Example.** A two-option build of the current source. It was checked to build, with `"strict": false` added to the
bundle while `dev/src/addon/structures.lua` is missing; as written (strict) it fails until that file exists:

```json
{
  "schema": "treasure-radar-build/1",
  "version": "0.6.0",
  "manifest": {
    "template": "../../../manifest.json",
    "set": {"Name": "{title} {version}"},
    "options": [
      {"Name": "Treasure Radar (core)", "Image": "images/core.png", "Include": ["core"]},
      {"Name": "Loot Ledger", "Image": "images/ledger.png", "Include": ["ledger"]}
    ]
  },
  "files": {"images": "../../../images", "thumbnail.png": "../../../thumbnail.png"},
  "options": {
    "core": [
      {"kind": "loader", "file": "../../reference/0.5.1/loader.lua",
       "set": {"LOADER": "{title} {version}: Chef Loader"}},
      {"kind": "bundle", "modules": "../../src/addon/modules.txt", "textures": "../../src/textures"},
      {"kind": "options", "value": "{ radar = true }"}
    ],
    "ledger": [
      {"kind": "options", "value": "{ ledger = true }"}
    ]
  }
}
```

`builds/0.5.1.json` uses every kind except `bundle` and `raw`. `builds/0.6.0.json` builds 0.6.0 (`builds/0.6.1.json` is
the same with the probe's crash fix, its own version and its own manifest Guid):
* The loader is 0.5.1's with its name changed.
* `core` holds the bundle (the modules in `dev/src/addon/modules.txt`, every PNG under `dev/src/textures`) and sets
  no feature key, so Radar Off's `radar = false` wins in any order.
* One folder per feature (`ledger`, `compass`, `bezel`, `pings`, `overlay`, `rotate`, `radar_off`), per map kind
  (`map_objective`, `map_side`, `map_nest`, `map_structure`, `map_poi`) and per loot kind, plus 0.5.1's opacity, size,
  marker and range choices: 40 folders, 27 manifest entries.
* `tester` adds a second addon (`dev/src/probe/treasure_radar_probe.lua`) and `{ calibrate = true, structures_all =
  true }`.
* The option images come from `dev/src/images` (made by `option_images.py`); the thumbnail is 0.5.1's.

`builds/0.7.0.json` keeps `core` and replaces the rest. Everything is on by default (`config.lua`); each dropdown's
folders set one key, only to change a default: `loot_<all|valuables|samples>` (`loot`), `extras_<all|objectives|off>`
(`extras`), `radar_<medium|large|small|off>` (`radar`), `markers_<50|25|100|off>` (`markers`, 0 = off) and
`opacity_<n>`. Calibration is gone: the compass geometry is measured (`compass.lua`) and the map circle was right.
`builds/0.7.1.json` adds `facing_<turn|north>` (`rotate`; on unless North Up is picked) after the radar's list.
`builds/0.7.0-measure.json` is one entry, `core`, whose options are `{ core = true, measure = true, structures_all =
true }` (a folder holds one options resource), with its own Guid.
The logger is `dev/src/addon/measure.lua`, in every bundle and nil unless `measure` is set: a module, not a second
addon, because each addon runs in its own environment and could not read the others' `T`. 0.6's Tester
(`dev/src/probe/treasure_radar_probe.lua`) is only in 0.6.x.

## `extract.py` output

`python -I -B extract.py <mod folder> <out>` writes:

* `<out>/<option>/<label>.lua`: the Lua texts, byte for byte. The label is the last part of the name: `boot.lua`,
  `treasure_radar.lua`, `<option>.lua`.
* `<out>/<option>/textures/<label>.png`, where the label is `credit`, `sweep_0`, `glyph14_48`, and so on.
* `<out>/<option>/raw/<id>.main` (and `.gpu` / `.stream` when not empty) for anything that isn't flag-2 Lua or
  a texture `tex.py` can read (none in 0.5.1).
* `<out>/index.json`, which holds:
  - the manifest's sha256, Guid, Name and Version;
  - for each option, the archive's file sizes and sha256s, whether it is canonical, any deviations, the header
    and type-row fields, and `pad_main_end`;
  - for each resource: index, id, type, sizes, sha256, the name (only if proven), `lua_ref` (where the addon
    uses a texture id), the file, the Lua flag, the header kind and path, the first line, and the texture size,
    format and canonical flag.

It refuses to write inside a mod folder except under `dev/`. It refuses to clear a non-empty folder that has no
`index.json`.

## Tests

```sh
python -I -B test_roundtrip.py [--tmp DIR] [--keep] [--only ids,a,b,c,bundle,build]
```

| test | checks |
|---|---|
| `ids` | murmur64a gives the known type, loader and resource ids, and every named 0.5.1 resource hashes to its id |
| `a` | All 29 archives: parse → write is byte-identical (main, `.gpu_resources`, `.stream`) with no deviations. It is also identical when written from the resources alone, with no field read from the file. An edited archive stays stable through parse/write |
| `b` | `build.py builds/0.5.1.json` gives a file list and bytes identical to the mod folder (122 files, 20.5 MB). The shipped loader's own discovery, under Lua 5.1, finds the same result in the build as in the shipped mod: 1 addon that compiles, 29 options files, the same merged options |
| `c` | `tex.selftest()`: random sizes, every 8-bit PNG color type, and the refusals. Every 0.5.1 texture goes texture → PNG → texture byte-identical, and each extracted PNG encodes to the shipped bytes |
| `bundle` | A made-up module tree gives an exact, hand-written expected bundle. The map is right for every line. A runtime error raised in the running bundle maps back to `util.lua:4`. Refused: strict missing module, `goto`, `//`, BOM, no `main`, a 0.5.1 id, a duplicate id, bad `modules.txt`. The CLI incl. `--where` works |
| `build` | A made-up build has a loader with `set`, a bundle, options, and a probe addon `mods/chef/treasure_radar_probe` in a second folder. Discovery finds both addons and merges both folders' options. The output is canonical and deterministic. 16 kinds of bad description are refused, and nothing is ever written into the mod folder |

Scratch output goes to `dev/build/_test_tmp`. It is deleted afterwards unless `--keep` is given or a test
failed.

## Limits and risks

* **Unobservable details.** The GPU-file end padding and the `.stream` alignment are assumptions: 0.5.1 can't
  show them. The main-file end-padding rule fits the data, but so does another rule. If the game ever rejects
  a build, try `"pad_main_end"` first.
* **Unknown fields.** `0x7BEA` in the header, and the 16 / 64 fields, are reproduced, not understood.
* **Textures** are uncompressed RGBA8 with one mip, so a 512×512 texture costs 1 MiB. No BC or DXT compression,
  no mips, no streaming. `dxgi` 29 (sRGB) is untested in the game.
* **Icon names.** 0.5.1's 9 icon names are unknown, so a build can carry those textures only by id.
* **Deploy order.** The manifest order of deployment (`patch_<N>`) is an assumption about Arsenal. It only
  matters for which options file wins a merge.
* **Name collisions.** A resource id equal to a game resource's id would replace that resource in the game. Only
  `boot` is replaced on purpose. The tools check new ids only against 0.5.1, not against the game.
* **The loader** is checked by running its discovery code under Lua 5.1 (lupa). The game's runtime (Lua 5.1 or
  LuaJIT, its `io` and the Arsenal deployment) isn't run.
