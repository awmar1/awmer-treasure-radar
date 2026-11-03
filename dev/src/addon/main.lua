local T, chef = ...
-- The frame loop: builds the frame state S, handles the mod's own keys, and runs every module in PIPE order (update
-- for all, then draw for all). Each module runs under its own pcall: one that keeps failing is switched off and the
-- rest go on.
-- Idle: nothing outside a mission; the unit lists rest while nothing on screen needs them.
local M = { version = T.version }
local C, D = T.mod.config, T.mod.draw
local floor, max, sqrt, atan2 = math.floor, math.max, math.sqrt, math.atan2
local MAX_ERRORS = 30

-- view: the open map's model and clusters (after the loot and structure lists, before anything that draws them)
-- (0.9.3: lineprobe, 0.9.2's one-mission experiment, is retired: dev/src/retired/lineprobe-0.9.2.lua)
M.PIPE = { 'hud', 'mapview', 'track', 'objectives', 'pings', 'view', 'markers', 'radar', 'compass', 'legend',
           'overlay' }

local S = {
  t = 0, dt = 0, frame = 0, w = 1920, h = 1080, px = 2, cam = nil, me = { x = 0, y = 0, z = 0 }, fx = 0, fy = 1,
  heading = 0, hidden = false, map_open = false, map = {}, opacity = 1, need_loot = false,
  markers_on = true,   -- always true since 0.8 (F8 is gone); kept for the modules that read it
}
M.S = S

-- the modules that exist in this build, in PIPE order, each with its error count
local mods, started = {}, false
for _, name in ipairs(M.PIPE) do
  local m = T.mod[name]
  if type(m) == 'table' then mods[#mods + 1] = { name = name, m = m, errors = 0, on = true } end
end

local function run(e, hook)
  local fn = e.on and e.m[hook]
  if type(fn) ~= 'function' then return end
  local ok, err = pcall(fn, S)
  if ok then return end
  e.errors = e.errors + 1
  if e.errors <= 3 then chef.log('%s.%s error: %s', e.name, hook, tostring(err)) end
  if e.errors >= MAX_ERRORS then
    e.on = false
    chef.log('%s switched off for this session after %d errors', e.name, e.errors)
  end
end
local function run_all(hook) for i = 1, #mods do run(mods[i], hook) end end

-- The companion (the closer zooms' screen reader, shipped in the mod's folder under the manager's Mods): started once
-- per game run, one log line per outcome, never retried. It exits with the game by itself. Without it the mod is whole
-- map only. mod_folder is the build's (core's options row, the manifest's Name).
local function start_companion()
  if not C.HELPER then chef.log('companion start: off in the options'); return end
  local ok, dir = pcall(os.getenv, 'LOCALAPPDATA')
  local folder = C.opt.mod_folder
  if not (ok and type(dir) == 'string' and dir ~= '' and type(folder) == 'string') then
    chef.log('companion start: no mod folder known, not started')
    return
  end
  local exe = dir .. '\\Helldivers2ModManager\\Mods\\' .. folder .. '\\companion\\TreasureRadarCompanion.exe'
  local opened, f = pcall(io.open, exe, 'rb')
  if not (opened and f) then chef.log('companion start: not found at %s (whole map only)', exe); return end
  pcall(function() f:close() end)
  if type(os.execute) ~= 'function' then chef.log('companion start: os.execute is not available, not started'); return end
  local ran, code = pcall(os.execute, 'start "" "' .. exe .. '"')
  if ran then chef.log('companion start: started %s (returned %s)', exe, tostring(code))
  else chef.log('companion start: could not start %s: %s', exe, tostring(code)) end
end

local function start()
  started = true
  local names = {}
  for _, e in ipairs(mods) do names[#names + 1] = e.name end
  chef.log('Treasure Radar %s: %s', tostring(T.version), table.concat(names, ', '))
  start_companion()
  run_all('init')
end

-- the loot lists are needed while anything that shows loot is up (or a waypoint follows a pile)
local function wants_loot()
  if C.MARKERS then return true end
  local p = T.mod.pings
  if p and p.wants_loot and p.wants_loot() then return true end
  if S.hidden then return false end
  return (C.RADAR or C.LEGEND or C.COMPASS or C.OVERLAY) and true or false   -- C.LEGEND may be a string (0.9.3)
end

local mission_id = nil
function M.update(dt)
  if not started then start() end
  S.frame = S.frame + 1
  if not chef.in_mission() then
    if mission_id then run_all('idle') end
    S.map_open = false
    return
  end
  S.t, S.dt = chef.time(), type(dt) == 'number' and dt or 0
  if chef.world_id() ~= mission_id then
    -- a new mission: nothing from the last one carries over
    mission_id = chef.world_id()
    S.map_open = false
    run_all('reset')
  end

  if chef.key_pressed(C.KEYS.toggle) then S.hidden = not S.hidden; chef.log('mod HUD %s (F7)', S.hidden and 'hidden' or 'shown') end

  local cam = chef.camera()
  if not cam then
    run_all('blind')        -- mapview keeps this frame's wheel, mouse and presses for the next full frame
    return
  end
  S.cam = cam
  S.w, S.h = chef.screen()
  S.px = max(1, floor(S.h / 540 + 0.5))     -- 2 at 1080p, 3 at 1440p, 4 at 4K
  local me = S.me
  me.x, me.y, me.z = cam.x, cam.y, cam.z - C.EYE
  local l = sqrt(cam.fx * cam.fx + cam.fy * cam.fy)
  if l > 1e-3 then S.fx, S.fy = cam.fx / l, cam.fy / l end    -- looking straight down: keep the last heading
  S.heading = atan2(S.fx, S.fy)
  S.need_loot = wants_loot()

  D.frame(S)
  run_all('update')
  run_all('draw')
end

function M.shutdown()
  for i = 1, #mods do
    local e = mods[i]
    if type(e.m.shutdown) == 'function' then pcall(e.m.shutdown) end
  end
end

return M
