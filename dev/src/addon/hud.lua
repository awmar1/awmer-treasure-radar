local T, chef = ...
-- The game's HUD settings and where the game puts things on screen.
-- Settings: saves\<player id>_user_settings.config in the game's folder in %APPDATA% (read-only), read at mission
-- start and every EVERY s in a mission, so changes made mid-mission follow.
local H = {}
local C = T.mod.config
local max, min = math.max, math.min
local EVERY = 10

H.raw = {}          -- every number in the file by key (hud_scale, hud_offset, hud_compass_width, ...)
local state = { key = nil, no_id = nil, no_file = nil, next = 0 }

function H.read()
  local ok, appdata = pcall(os.getenv, 'APPDATA')
  local peer = chef.call('Network.peer_id')
  if not (ok and type(appdata) == 'string' and peer) then
    if not state.no_id then state.no_id = true; chef.log('hud settings: not found yet (no player id)') end
    return
  end
  local okf, f = pcall(io.open, appdata .. '\\Arrowhead\\Helldivers2\\saves\\' .. tostring(peer) .. '_user_settings.config', 'r')
  if not (okf and f) then
    if not state.no_file then state.no_file = true; chef.log('hud settings: the settings file could not be opened; using the defaults') end
    return
  end
  local text = f:read('*a') or ''
  f:close()
  local raw = {}
  for k, v in text:gmatch('\n%s*(hud_[%w_]+)%s*=%s*([%-%d%.]+)') do raw[k] = tonumber(v) end
  H.raw = raw
  local key = string.format('%s %s %s %s %s %s %s', tostring(raw.hud_offset), tostring(raw.hud_scale), tostring(raw.hud_map_position),
    tostring(raw.hud_background_opacity), tostring(raw.hud_compass), tostring(raw.hud_compass_width), tostring(raw.hud_compass_angle_range))
  if key == state.key then return end
  state.key = key
  chef.log('hud settings: edge offset %s, scale %s, map position %s, background opacity %s, compass %s width %s range %s',
    tostring(raw.hud_offset), tostring(raw.hud_scale), tostring(raw.hud_map_position), tostring(raw.hud_background_opacity),
    tostring(raw.hud_compass), tostring(raw.hud_compass_width), tostring(raw.hud_compass_angle_range))
end

-- ------------------------------------------------------------------ geometry
-- The game anchors its HUD's bottom-right corner 70 px from the right and 44 px from the bottom (at 1440 px; 0.0486
-- and 0.0306 screen heights). HUD Edge Offset slides the HUD's sides between the 16:9 area in the middle of the screen
-- (1) and the screen's own edges (0). The map is a circle of radius 0.2056 screen heights, the same at any HUD Scale;
-- its center sits MAP_DX left of and MAP_DY above the corner at HUD Scale 0.85, and moves a little with HUD Scale
-- (measured at 0.75, 0.85 and 1.25 for 0.5; checked at 1920x1080, HUD Scale 0.9, Edge Offset 0 for 0.7: within 2 px;
-- 0.8's measuring run put it at 1674.0, 260.5 there, 1.4 px left of and 0.8 px below 0.7's, and MAP_DX, MAP_DY moved
-- to match).
local CORNER_RIGHT, CORNER_BOTTOM, BASE_SCALE = 70 / 1440, 44 / 1440, 0.85
local MAP_DX, MAP_DY = 256.27 / 1440, 300.23 / 1440
local DX_PER_SCALE, DY_PER_SCALE = 34 / 1440, 63 / 1440
H.MAP_RIM = 0.2056          -- the open map's rim radius, in screen heights
H.MY_RADIUS = 0.19          -- the folded map's radius at Size: large, in screen heights

function H.scale()
  local s = H.raw.hud_scale
  if type(s) ~= 'number' or s < 0.3 or s > 3 then return BASE_SCALE end
  return s
end
function H.offset()
  local off = H.raw.hud_offset
  if type(off) ~= 'number' or off < 0 or off > 1 then return 1 end
  return off
end
-- the HUD's left and right edges on screen
function H.sides(w, h)
  local area = min(w, h * 16 / 9)
  local inset = H.offset() * (w - area) / 2
  return inset, w - inset
end
-- the game's map circle: center (bottom-left origin) and rim radius
function H.map(w, h)
  local _, right = H.sides(w, h)
  local ds = H.scale() - BASE_SCALE
  right = right - CORNER_RIGHT * h
  return right - (MAP_DX + ds * DX_PER_SCALE) * h, CORNER_BOTTOM * h + (MAP_DY + ds * DY_PER_SCALE) * h, H.MAP_RIM * h
end
-- the map position setting isn't measured (only 0, the default): logged once per value
function H.map_measured() local p = H.raw.hud_map_position; return p == nil or p == 0 end

-- Panel opacity when Arsenal doesn't pick one: the game's HUD Background Opacity. Its scale isn't known yet (0..4
-- steps is a guess from a file holding 3); anything else counts as full.
function H.opacity()
  if C.OPACITY then return C.OPACITY end
  local v = H.raw.hud_background_opacity
  if type(v) ~= 'number' then return 1 end
  if v >= 0 and v <= 1 and v ~= math.floor(v) then return v end
  if v >= 0 and v <= 4 then return 0.4 + 0.15 * v end
  return 1
end

function H.reset() state.no_id, state.no_file, state.next = nil, nil, 0 end
function H.update(S)
  if S.t >= state.next then state.next = S.t + EVERY; H.read() end
  local cx, cy, r = H.map(S.w, S.h)
  local m = S.map
  m.cx, m.cy, m.r = cx, cy, r
  S.opacity = H.opacity()
end

return H
