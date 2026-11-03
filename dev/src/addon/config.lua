local T, chef = ...
-- Options (Arsenal) and the shared look.
-- Everything is on by default. The manager's dropdowns each set one key, only to change a default; a key that's
-- missing (the dropdown left unticked, or a plain test install with no options at all) is the default:
--   mode    = 'all' | 'no_radar' | 'map_only'           outside the map: radar, compass pips and pins (default all);
--                                                       no_radar: no corner radar; map_only: none of the three
--   legend  = 'map' | 'always' | 'off'                  the legend while the map is open (default), always, or off
--   radar   = 'medium' | 'large' | 'small' | 'off'      the corner radar's size (default medium; off: for the sim)
--   rotate  = true | false                              the radar turns with my view, or north up (default true)
--   markers = 50 | 25 | 100 | 0                         world markers' range in meters, 0 = off (default 50)
--   opacity = 0..1                                      panels' opacity (default: the game's HUD Background Opacity)
--   map_opacity = 0..1                                  the open map's world icons, rings and chevron (default 1)
--   marker_opacity = 0..1                               the pins over loot, waypoint pins too (default 1)
--   helper  = 'auto' | 'off'                            start the companion with the game, or not (default auto)
--   mod_folder = <folder name>                          core's: this build's folder under the manager's Mods
--   kinds   = { <loot kind> = true, ... }               0.9.3's tick boxes (one per kind; they merge): only the listed
--   map_kinds = { <cat> = true, ... }                   loot kinds / map kinds show; no box ticked (no table) = all
-- Lower level keys (kept for the sim): loot = 'all' | 'valuables' | 'samples' and extras = 'all' | 'objectives' |
-- 'off' (the 0.6-0.9.2 dropdowns, used when kinds / map_kinds aren't set), legend = false, compass, overlay, pings =
-- false (that view off), range = <m>, size = 'small' | 'medium' | 'large'. (0.9 dropped measure, hover, cursor_gain
-- and open_rule with the cursor model: dev/src/retired.)
local C = {}
local max, min = math.max, math.min

local opt = chef.options or {}
C.opt = opt

local radar = opt.radar
local mode = opt.mode
C.MODE = (mode == 'no_radar' or mode == 'map_only') and mode or 'all'
-- the folded map (corner radar): off with mode no_radar / map_only, or radar = 'off' / false
C.RADAR = mode ~= 'no_radar' and mode ~= 'map_only' and radar ~= 'off' and radar ~= false
C.MAP_SCALE = ({ small = 0.6, medium = 0.75, large = 1.0 })[type(radar) == 'string' and radar or opt.size or ''] or 0.75
-- what's left: 'map' beside the open map (0.7's ledger pills), 'always' also while it's closed, or false (off)
local legend = opt.legend
if legend == false or legend == 'off' then C.LEGEND = false
elseif legend == 'always' then C.LEGEND = 'always'
else C.LEGEND = 'map' end
C.COMPASS = mode ~= 'map_only' and opt.compass ~= false   -- the nearest valuables on the game's compass
C.OVERLAY = opt.overlay ~= false               -- loot, nests and structures at their true spots on the open map
C.PINGS = opt.pings ~= false                   -- the ping assist and my own waypoints
C.RANGE = max(25, min(1000, tonumber(opt.range) or 150))   -- meters from me to the radar's edge
C.ROTATE = opt.rotate ~= false                 -- the radar turns with my view (0.7.1 on; 0.7.0 kept north up)
C.MARKERS = tonumber(opt.markers or 50)        -- world markers' range in meters, or nil (off; mode map_only)
if (C.MARKERS and C.MARKERS <= 0) or mode == 'map_only' then C.MARKERS = nil end
-- Panel opacity: a dropdown pick, or (no pick) the game's own HUD background opacity, read by hud.lua
C.OPACITY = tonumber(opt.opacity)
if C.OPACITY then C.OPACITY = max(0, min(1, C.OPACITY)) end
C.MAP_OPACITY = max(0, min(1, tonumber(opt.map_opacity) or 1))         -- the open map's world icons (not the legend)
C.MARKER_OPACITY = max(0, min(1, tonumber(opt.marker_opacity) or 1))   -- the pins over loot and waypoints
C.HELPER = opt.helper ~= 'off'                 -- start the companion with the game (main.lua)

-- loot kinds and map kinds (objectives, structures, ...): the tick boxes' tables, else the old dropdowns' sets
-- (nil = all)
local LOOT = {
  valuables = { credit = true, medal = true, common = true, rare = true, super = true, requisition = true },
  samples = { common = true, rare = true, super = true },
}
local EXTRAS = {
  objectives = { objective = true, extract = true, side_objective = true },
  off = {},
}
function C.kind_on(id)
  if type(opt.kinds) == 'table' then return opt.kinds[id] == true end
  local set = LOOT[opt.loot or 'all']
  return set == nil or set[id] == true
end
function C.map_kind_on(cat)
  if type(opt.map_kinds) == 'table' then return opt.map_kinds[cat] == true end
  local set = EXTRAS[opt.extras or 'all']
  return set == nil or set[cat] == true
end

-- F7 hides the mod; Numpad 1 / 3 set and clear a waypoint (pings.lua). 0.8 dropped F8 (world pins) and F9 (done).
C.KEYS = { toggle = 'f7', wp_set = 'numpad 1', wp_clear = 'numpad 3' }
C.FADE = 0.4                  -- seconds a picked-up mark takes to fade out
C.EYE = 1.6                   -- my camera sits about this high above my feet

-- The game's HUD colors (sampled from captures; see the plan, section 04)
C.RGB = {
  text = { 255, 255, 237 }, rim = { 201, 197, 170 }, me = { 255, 233, 0 }, ping = { 113, 245, 255 },
  objective = { 255, 136, 36 }, label = { 255, 156, 68 }, hostile = { 255, 75, 62 }, dark = { 10, 11, 12 },
  done = { 140, 230, 140 }, dim = { 120, 118, 104 }, side = { 150, 140, 255 },
  muted = { 150, 146, 128 },  -- secondary text on panels (the map label's distance)
}
-- panels on the open map and the compass (the 0.8 mock): fill, and the rim-coloured outline's alpha
C.PANEL = { fill = { 12, 13, 14 }, shadow = { 0, 0, 0 } }

-- loot by value, most valuable first (the map's clusters show the top one, the compass only valuables)
C.RANK = { 'super', 'rare', 'credit', 'medal', 'common', 'requisition', 'ammo', 'grenade', 'stim' }
C.VALUABLE = { super = true, rare = true, credit = true, medal = true, common = true, requisition = true }

return C
