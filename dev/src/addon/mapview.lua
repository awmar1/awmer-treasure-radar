local T, chef = ...
-- Is the game's map open? (S.map_open, read by every map view.) Lua can't ask the game, so two signals are combined
-- (research 7.1):
--   The world list: the loader draws chef.TOP layers into the first world that isn't the main one, so a second world
--   is needed for anything drawn over the map; the list vetoes.
--   The Map key (the player's own binding from input_settings.config; default Tab, Press) is a toggle, and decides
--   (mode 'key', the start of every session). The game keeps several worlds all mission long (the player's log: worlds
--   2-8 from the mission's start), so the list alone would call the map open from the drop on (0.6's bug).
--   If a world turns out to come with a Map press and go with the next (the sim's model), the list alone tells from
--   then on (mode 'list').
-- Hide on any doubt: Esc, a frame gap (no camera, a menu), a camera jump (death, respawn) and a new mission close it
-- until the map's world goes away and comes back, or the Map key is pressed.
-- The game ignores some Map presses (a fast double tap, the map's open/close animation: the player's 0.7.0 log), so
-- the toggle can drift. In key mode the mouse sets it right (the player's snapshots: with the map open the camera
-- doesn't turn at all, with it closed it turns with the mouse): a sideways mouse move that turns the camera closes it
-- at once; a long one that leaves the camera perfectly still opens it, but not after a doubt (a menu, a terminal,
-- the drop) until the camera has followed the mouse once.
-- While it's open: wheel notches (zoom in = +). The map's cursor and panning aren't chef.cursor (research 7.3): view.lua
-- follows them from the raw mouse (V.mouse). For its doubts: V.wheel_any (notches in any state), V.cold (this open was
-- found by the mouse, not seen begin) and V.fixes (opens taken back: the camera turned with the mouse).
-- V.top_now: a second world this very frame. Also here: the Map and ping (CommunicationSpot) bindings (V.binds) and
-- V.cursor (bottom-left origin; the system cursor, not the map's).
-- 0.8.2: the mouse says nothing in the map's animation (PRESS_QUIET after a press: the camera turns in it while the
-- hand still moves, and 0.8.1 took a false open back 0.5 s after each Tab). view.lua keeps a shadow model while the
-- mod thinks the map is closed, from: V.follows (the camera followed the mouse: the game's map is closed), V.stills
-- (a move ended with the camera still: it's open), V.doubts, V.notches_shut, V.t_press / V.press_open. Frames without
-- a camera keep their input for the next full frame (V.blind, main.lua). V.note: chef.log at most NOTE_MAX lines a s.
-- 0.8.3: a turn is a follow only at the mouse's own rate (FOLLOW_RATE deg per count at least, and RATIO_PART of the
-- learned ratio), at any time: slow camera drift with the map open (0.002-0.008 deg/count in the player's 0.8.2 log)
-- took four real opens back. For view.lua's take-back: V.stills_press (stills since the last Map press) and
-- V.follow_since (s from the press to the follow that took the open back).
local V = {}
local abs, pi, floor, max = math.abs, math.pi, math.floor, math.max
local fmt, upper = string.format, string.upper

-- ------------------------------------------------------------------ tuning
local OPEN_FRAMES = 2          -- the world list must agree this many frames in a row
local PROOF_WINDOW = 0.75      -- s after a Map press in which a world-list change counts as the press's doing
local GAP_FRAMES = 15          -- frames without an update (no camera, a menu) that put the map in doubt
local JUMP = 25                -- m the camera may move in one frame before it counts as death / respawn
local ESC = { 'esc', 'escape' }
local FOLLOW_COUNTS, FOLLOW_DEG = 60, 0.6   -- a mouse move (sideways counts) that turned the camera this much: closed
local STILL_COUNTS, STILL_DEG = 500, 0.05   -- one this long that turned it less than this: open
local MOVE_GAP = 0.2           -- s without mouse movement that end a move
local PRESS_QUIET = 0.5        -- s after a Map press or Esc in which the mouse says nothing (the map's animation)
local FOLLOW_RATE = 0.015      -- deg per count a follow turns at least (the player's mouse-look: 0.03-0.04)
local RATIO_MIN = 200          -- counts: a move this long that turned the camera teaches its degrees per count
local RATIO_PART = 0.2         -- the share of that a follow must turn too, at any time (lenient: aiming changes it)
local RATIO_EMA = 0.25         -- how much each such move teaches
local BLIND_RUN = 3            -- frames without a camera in a row worth a log line
local NOTE_MAX = 20            -- V.note: log lines a second at most
V.CURSOR_TOP_LEFT = true       -- chef.cursor() counts from the top-left (probe item); V.cursor flips it

-- ------------------------------------------------------------------ public state
V.top_now = false              -- a second world this frame: chef.TOP layers can draw
V.mode = 'key'                 -- 'key' | 'list' (kept for the whole session once a Map press proved it)
V.proven = false               -- a Map press showed which mode it is
V.notches = 0                  -- wheel notches since this open (+ = zoom in)
V.notches_mission = 0          -- every open this mission (in case the game keeps its zoom between opens)
V.panned = false               -- kept for older readers: always false (view.lua follows the map's panning)
V.wheel_any = 0                -- wheel notches this mission, open or not (absolute)
V.cold = false                 -- this open was found by the mouse: the game's map was open before it
V.fixes = 0                    -- opens taken back this mission (the game's map was closed)
V.follows = 0                  -- the camera followed the mouse this mission, open or not (the game's map is closed)
V.stills = 0                   -- a move of FOLLOW_COUNTS+ ended with the camera still, after the quiet (it's open)
V.stills_press = 0             -- the same since the last Map press (a real open, if the press opened the toggle)
V.follow_since = nil           -- s from the last Map press to the last follow (nil: no press before it)
V.doubts = 0                   -- doubts this mission (Esc, a frame gap, a camera jump)
V.notches_shut = 0             -- wheel notches while the mod thinks the map is closed (+ = zoom in)
V.wheel_frame = 0              -- this frame's notches (any state; the blind frames' too)
V.t_press = nil                -- S.t of the last Map press
V.press_open = false           -- it opened the mod's toggle (false: closed it)
V.t_open = nil                 -- S.t when this open began (nil while closed)
V.opens = 0                    -- opens this mission
V.binds = {}                   -- map, ping: { dev = 'key'|'mouse'|nil, names = { ... }, label = 'TAB', trigger, from }

-- ------------------------------------------------------------------ bindings (read-only)
local DEFAULTS = {
  map = { action = 'Map', input = 'tab', device = 'Keyboard', trigger = 'Press' },
  ping = { action = 'CommunicationSpot', input = 'q', device = 'Keyboard', trigger = 'Tap' },
}
local MOUSE = {
  MouseButtonLeft = { 'left' }, MouseButtonRight = { 'right' }, MouseButtonMiddle = { 'middle' },
  MouseButton4 = { 'extra_1', 'x1', 'mouse 4', 'button4' }, MouseButton5 = { 'extra_2', 'x2', 'mouse 5', 'button5' },
}
local MOUSE_LABEL = { MouseButtonLeft = 'LMB', MouseButtonRight = 'RMB', MouseButtonMiddle = 'MMB',
  MouseButton4 = 'MOUSE 4', MouseButton5 = 'MOUSE 5' }

local function getenv(name)
  local ok, v = pcall(os.getenv, name)
  if ok and type(v) == 'string' and v ~= '' then return v end
end
-- read-only: mode 'r', never anything else
local function read_file(path)
  local ok, f = pcall(io.open, path, 'r')
  if not (ok and f) then return nil end
  local ok2, text = pcall(f.read, f, '*a')
  pcall(f.close, f)
  if ok2 and type(text) == 'string' then return text end
end
V.read_file, V.getenv = read_file, getenv
local function fields(s)
  local e = {}
  for k, v in s:gmatch('([%w_]+)%s*=%s*"([^"]*)"') do e[k] = v end
  for k, v in s:gmatch('([%w_]+)%s*=%s*([^%s"{}%[%]]+)') do if e[k] == nil then e[k] = v end end
  return e
end
-- every overridden action: name -> its entries
local function parse_binds(text)
  text = text:gsub('//[^\n]*', '')
  local acts = {}
  for _, body in text:gmatch('([%w_]+)%s*=%s*(%b{})') do
    for name, arr in body:sub(2, -2):gmatch('([%w_]+)%s*=%s*(%b[])') do
      local list = {}
      for e in arr:gmatch('%b{}') do list[#list + 1] = fields(e:sub(2, -2)) end
      acts[name] = list
    end
  end
  return acts
end
local function account_of(id64)    -- SteamID64 -> Steam account id, on digit strings (doubles lose digits)
  if #id64 < 10 or #id64 > 20 then return nil end
  local hi, lo = tonumber(id64:sub(1, -10)), tonumber(id64:sub(-9))
  if not (hi and lo) then return nil end
  local acc = (hi - 76561197) * 1e9 + (lo - 960265728)
  if acc > 0 and acc < 4294967296 then return fmt('%.0f', acc) end
end
-- the bindings file's text and a template of where it was (never the ids)
local function find_bindings()
  local cands = {}
  local appdata, peer = getenv('APPDATA'), chef.call('Network.peer_id')
  if appdata and peer then
    cands[#cands + 1] = { appdata .. '\\Arrowhead\\Helldivers2\\saves\\' .. tostring(peer) .. '_input_settings.config',
      '%APPDATA%\\...\\saves\\<player>_input_settings.config' }
  end
  if appdata then
    cands[#cands + 1] = { appdata .. '\\Arrowhead\\Helldivers2\\input_settings.config', '%APPDATA%\\...\\input_settings.config' }
  end
  local seen = {}
  for _, r in ipairs({ { getenv('SteamPath'), '' }, { getenv('ProgramFiles(x86)'), '\\Steam' }, { getenv('ProgramFiles'), '\\Steam' } }) do
    if r[1] then
      local root = r[1]:gsub('/', '\\') .. r[2]
      if not seen[root:lower()] then
        seen[root:lower()] = true
        local vdf = read_file(root .. '\\config\\loginusers.vdf')
        if vdf then
          local first, rest = {}, {}
          for id, body in vdf:gmatch('"(7656%d+)"%s*(%b{})') do
            local acc = account_of(id)
            if acc then if body:match('"MostRecent"%s*"1"') then first[#first + 1] = acc else rest[#rest + 1] = acc end end
          end
          for _, acc in ipairs(rest) do first[#first + 1] = acc end
          for i = 1, math.min(#first, 8) do
            cands[#cands + 1] = { root .. '\\userdata\\' .. first[i] .. '\\553850\\remote\\input_settings.config',
              'Steam\\userdata\\<account>\\553850\\remote\\input_settings.config' }
          end
        end
      end
    end
  end
  for _, c in ipairs(cands) do
    local text = read_file(c[1])
    if text then return text, c[2] end
  end
end

-- a binding from the action's entries (the first keyboard or mouse one), or the default when it isn't overridden
local function make_bind(def, entries, from)
  local e = nil
  if entries then
    for _, x in ipairs(entries) do
      if (x.device_type == 'Keyboard' or x.device_type == 'Mouse') and type(x.input) == 'string' then e = x; break end
    end
    if not e then return { dev = nil, names = {}, label = '?', from = from } end   -- gamepad only
  else
    e, from = { device_type = def.device, input = def.input, trigger = def.trigger }, 'default'
  end
  if e.device_type == 'Mouse' then
    local names = MOUSE[e.input]
    if not names then return { dev = nil, names = {}, label = upper(e.input), trigger = e.trigger, from = from } end
    return { dev = 'mouse', names = names, label = MOUSE_LABEL[e.input] or upper(e.input), trigger = e.trigger, from = from }
  end
  return { dev = 'key', names = { e.input }, label = upper(e.input), trigger = e.trigger, from = from }
end

local binds_line = nil
local function read_binds()
  local text, where = find_bindings()
  local acts = text and parse_binds(text) or {}
  local from = where and 'file' or 'default'
  V.binds.map = make_bind(DEFAULTS.map, acts[DEFAULTS.map.action], from)
  V.binds.ping = make_bind(DEFAULTS.ping, acts[DEFAULTS.ping.action], from)
  local m, p = V.binds.map, V.binds.ping
  local line = fmt('map %s %s (%s), ping %s %s (%s)', m.label, tostring(m.trigger), m.from, p.label, tostring(p.trigger), p.from)
  if line ~= binds_line then
    binds_line = line
    chef.log('binds: %s; file: %s', line, where or 'none found')
  end
end

-- down / pressed for a binding (a mouse button's press is an edge kept here; one in the frames without a camera
-- since the last full frame counts in this one: held)
local mouse_was = {}
local held = { left = false, right = false, middle = false }
function V.down(b)
  if not (b and b.dev) then return false end
  local f = b.dev == 'key' and chef.key_down or chef.mouse_down
  for i = 1, #b.names do if f(b.names[i]) then return true end end
  return false
end
function V.pressed(b)
  if not (b and b.dev) then return false end
  local names = b.names
  if b.dev == 'key' then
    for i = 1, #names do if chef.key_pressed(names[i]) then return true end end
    return false
  end
  local d = V.down(b)
  local was = mouse_was[b]
  mouse_was[b] = d
  if d and not was then return true end
  for i = 1, #names do if held[names[i]] then return true end end
  return false
end

-- chef.log, at most NOTE_MAX lines a second; the rest are counted, and the count is logged when the next second starts
local note_s, note_n, note_drop = nil, 0, 0
function V.note(t, ...)
  local s = floor(t or 0)
  if s ~= note_s then
    if note_drop > 0 then chef.log('log: %d lines left out in the second from %d s', note_drop, note_s) end
    note_s, note_n, note_drop = s, 0, 0
  end
  if note_n >= NOTE_MAX then note_drop = note_drop + 1; return end
  note_n = note_n + 1
  chef.log(...)
end
local function any_pressed(list)
  for i = 1, #list do if chef.key_pressed(list[i]) then return true end end
  return false
end

-- the cursor in GUI pixels (bottom-left origin); raw = as chef.cursor() gives it
function V.cursor(S, raw)
  local x, y = chef.cursor()
  if type(x) ~= 'number' or type(y) ~= 'number' then return nil end
  if raw or not V.CURSOR_TOP_LEFT then return x, y end
  return x, S.h - y
end

-- this frame's raw mouse movement (counts; the engine's 'mouse' axis, guarded: 0, 0 when there's none)
local mouse_ix = nil
local function raw_mouse()
  if mouse_ix == nil then mouse_ix = chef.call('Mouse.axis_index', 'mouse') or false end
  if not mouse_ix then return 0, 0 end
  local v = chef.call('Mouse.axis', mouse_ix)
  if v == nil then return 0, 0 end
  local x, y = chef.call('Vector3.to_elements', v)
  if type(x) ~= 'number' or type(y) ~= 'number' then return 0, 0 end
  return x, y
end
-- with the counts of the frames without a camera since the last full one (the same for every caller this frame)
local cdx, cdy = 0, 0
function V.mouse()
  local x, y = raw_mouse()
  return x + cdx, y + cdy
end

-- ------------------------------------------------------------------ inputs while open
local function wheel()
  local w = chef.wheel()
  if type(w) ~= 'number' then return 0 end
  if abs(w) >= 20 then w = w / 120 end       -- in case the engine counts Windows wheel units (probe item)
  return w
end

-- ------------------------------------------------------------------ state
local function worlds()
  local ws = chef.call('Application.worlds')
  if type(ws) ~= 'table' then return 0 end
  return #ws
end
local seen, unseen, wl = 0, 0, false
local key_open, doubt, esc_doubt = false, false, false
local pending, pending_wl = nil, false
local last_frame, lx, ly, lz = nil, nil, nil, nil
local logged, told_c = false, false
local move_n, move_deg, move_t, last_hd = 0, 0, nil, nil   -- this mouse move: sideways counts, camera turn (degrees)
local run_n, run_deg = 0, 0                -- the same since a rule last decided (it starts again; the move goes on)
local ratio = nil                          -- the camera's degrees per sideways count with the map closed (learned)
local open_ok, quiet_until = false, -1                       -- the camera followed the mouse since the last doubt
local cold = false                                           -- the mouse just opened it (V.cold for the next open)
-- the frames without a camera since the last full one: wheel, raw counts, presses (latched), the run's length
local bw, bdx, bdy, b_map, b_esc = 0, 0, 0, false, false
local b_run, b_t0, b_open = 0, 0, false
local BUTTONS = { 'left', 'right', 'middle' }
local latch = { left = false, right = false, middle = false }   -- pressed in them (held in the next full frame)
local last_down = { left = false, right = false, middle = false }

local function close_session()
  V.t_open, V.panned, V.notches, V.cold = nil, false, 0, false
end
local function set_doubt(why, S)
  if S.map_open then chef.log('map: closed (%s)', why) end
  doubt, key_open, open_ok = true, false, false
  V.doubts = V.doubts + 1
  if why == 'esc' then esc_doubt = true end
end
local function end_move() move_n, move_deg, move_t, run_n, run_deg = 0, 0, nil, 0, 0 end

-- a move ended (MOVE_GAP without counts): a long one that left the camera still says the game's map is open; one
-- that turned it while the map was thought closed teaches the camera's degrees per count
local function move_ended(now)
  if move_n >= FOLLOW_COUNTS and move_deg < STILL_DEG then V.stills, V.stills_press = V.stills + 1, V.stills_press + 1 end
  if move_n >= RATIO_MIN and move_deg > FOLLOW_DEG and not now then
    local r = move_deg / move_n
    ratio = ratio and ratio + (r - ratio) * RATIO_EMA or r
  end
end

-- key mode: the mouse and the camera set the toggle right when the game ignored a Map press (see the top)
local function follow(S)
  local hd = S.heading
  local turn = last_hd and abs((hd - last_hd + pi) % (2 * pi) - pi) * 180 / pi or 0
  last_hd = hd
  -- the map's animation may turn the camera while the hand still moves the mouse: nothing in it counts
  if S.t < quiet_until then end_move(); return end
  local now = key_open and not doubt
  local dx, dy = V.mouse()
  if dx ~= 0 or dy ~= 0 then
    local n = abs(dx)
    move_n, move_deg, run_n, run_deg, move_t = move_n + n, move_deg + turn, run_n + n, run_deg + turn, S.t
  elseif move_t and S.t - move_t <= MOVE_GAP then
    move_deg, run_deg = move_deg + turn, run_deg + turn        -- the camera may trail the mouse by a frame
  else
    if move_t then move_ended(now) end
    end_move()
  end
  if not move_t or V.mode ~= 'key' then return end
  if run_n >= FOLLOW_COUNTS and run_deg >= FOLLOW_DEG then
    local since = V.t_press and S.t - V.t_press
    local rate = ratio and max(FOLLOW_RATE, RATIO_PART * ratio) or FOLLOW_RATE
    if run_deg < rate * run_n then
      -- far slower than the mouse turns it: the camera drifting (or the animation's tail), not a follow
      if now then
        V.note(S.t, 'map: a slow turn, not a follow: %.2f deg in %d counts (%.4f deg/count, a follow needs %.4f)',
          run_deg, run_n, run_deg / run_n, rate)
      end
      run_n, run_deg = 0, 0
      return
    end
    V.follows, V.follow_since = V.follows + 1, since
    if now then
      chef.log('map: closed (the camera turns with the mouse: %.2f deg in %d counts (%.4f deg/count, a follow needs ' ..
        '%.4f), %s s after a Map press, usual %s deg/count; the game ignored a Map press)', run_deg, run_n,
        run_deg / run_n, rate, since and fmt('%.2f', since) or '-', ratio and fmt('%.4f', ratio) or '-')
      V.fixes = V.fixes + 1
    end
    key_open, open_ok = false, true
    run_n, run_deg = 0, 0
  elseif run_n >= STILL_COUNTS then
    if run_deg < STILL_DEG and open_ok and wl and not now then
      chef.log('map: open (the mouse moves and the camera stays still: %.3f deg in %d counts; the game ignored a Map ' ..
        'press)', run_deg, run_n)
      key_open, doubt, esc_doubt, cold = true, false, false, true
    end
    run_n, run_deg = 0, 0
  end
end

-- a frame without a camera (main.lua skips the modules then): keep what the player did for the next full frame
local function blind(S)
  for i = 1, #BUTTONS do held[BUTTONS[i]] = false end     -- the last full frame's are spent
  bw = bw + wheel()
  local x, y = raw_mouse()
  bdx, bdy = bdx + x, bdy + y
  if V.pressed(V.binds.map) then b_map = true end
  if any_pressed(ESC) then b_esc = true end
  for i = 1, #BUTTONS do
    local b = BUTTONS[i]
    local d = chef.mouse_down(b) and true or false
    if d and not last_down[b] then latch[b] = true end
    last_down[b] = d
  end
  if b_run == 0 then b_t0, b_open = S.t, key_open and not doubt end
  b_run = b_run + 1
end
V.blind = blind

-- this full frame takes in the blind frames' input: the counts (V.mouse), the buttons (V.pressed); the wheel and the
-- presses are returned. A frame gap's doubt drops their Map press (the state is unknown then anyway).
local function unblind(S, gap)
  cdx, cdy, bdx, bdy = bdx, bdy, 0, 0
  for i = 1, #BUTTONS do
    local b = BUTTONS[i]
    held[b], latch[b] = latch[b], false
    last_down[b] = chef.mouse_down(b) and true or false
  end
  if b_run >= BLIND_RUN then
    V.note(S.t, 'map: %d frames without a camera (%.2f s; the map was %s): their input is taken in now', b_run,
      S.t - b_t0, b_open and 'open' or 'closed')
  end
  local w, m, e = bw, b_map and not gap, b_esc
  bw, b_map, b_esc, b_run = 0, false, false, 0
  return w, m, e
end
local function clear_blind()
  bw, bdx, bdy, b_map, b_esc, b_run, cdx, cdy = 0, 0, 0, false, false, 0, 0, 0
  for i = 1, #BUTTONS do local b = BUTTONS[i]; held[b], latch[b], last_down[b] = false, false, false end
end

function V.init(S)
  read_binds()
end

function V.reset(S)
  if logged then chef.log('map closed (new mission)') end
  seen, unseen, wl = 0, 0, false
  key_open, doubt, esc_doubt, pending = false, false, false, nil
  last_frame, lx, ly, lz = nil, nil, nil, nil
  end_move()
  last_hd, open_ok, quiet_until = nil, false, -1     -- the drop: the mouse opens nothing until I've looked around
  V.notches_mission, V.opens, V.wheel_any, V.fixes, cold = 0, 0, 0, 0, false
  V.follows, V.stills, V.doubts, V.notches_shut, V.wheel_frame = 0, 0, 0, 0, 0
  V.t_press, V.press_open, V.stills_press, V.follow_since = nil, false, 0, nil
  clear_blind()
  close_session()
  S.map_open, V.top_now, logged = false, false, false
  read_binds()      -- once a mission: picks up a binding changed in the options
end

function V.update(S)
  local cam = S.cam
  -- doubt: a gap in the frames, or the camera jumping (death, respawn)
  local gap = last_frame and S.frame - last_frame > GAP_FRAMES
  if gap then set_doubt('frame gap', S) end
  last_frame = S.frame
  if cam then
    if lx then
      local dx, dy, dz = cam.x - lx, cam.y - ly, cam.z - lz
      if dx * dx + dy * dy + dz * dz > JUMP * JUMP then set_doubt('camera jump', S) end
    end
    lx, ly, lz = cam.x, cam.y, cam.z
  end
  local bwheel, bmap, besc = unblind(S, gap)

  -- the Map key: a toggle. Read before this frame's world-list edge, so a press in the same frame as the world it
  -- brings (or takes) counts against the state the last frame left, and pending_wl is the world list before the press
  if V.pressed(V.binds.map) or bmap then
    key_open, cold = not key_open, false
    if V.mode == 'key' or not wl then doubt, esc_doubt = false, false end
    if not V.proven then pending, pending_wl = S.t, wl end
    end_move()
    quiet_until = S.t + PRESS_QUIET
    V.t_press, V.press_open, V.stills_press = S.t, key_open, 0
  end

  -- the world list, debounced
  local n = worlds()
  V.top_now = n >= 2
  if V.top_now then seen, unseen = seen + 1, 0 else seen, unseen = 0, unseen + 1 end
  local edge = false
  if not wl and seen >= OPEN_FRAMES then wl, edge = true, true
  elseif wl and unseen >= OPEN_FRAMES then wl, edge = false, true end
  if edge then
    -- key mode: the second world is there with the map closed too, so only its going away says anything
    if not wl or V.mode ~= 'key' then key_open = wl end
    if not wl then doubt, esc_doubt = false, false        -- the map's world went: whatever it was is over
    elseif not esc_doubt then doubt = false end           -- a world after Esc may be the pause menu: stay hidden
    if pending and S.t - pending <= PROOF_WINDOW then
      pending = nil
      if not V.proven then
        V.mode, V.proven = 'list', true
        chef.log('map: the world list follows the Map key (list mode)')
      end
    end
  end

  if pending and S.t - pending > PROOF_WINDOW then
    if pending_wl and wl then
      -- key_open stays as the presses left it: open, or closed again by a second tap inside the window
      V.mode, V.proven = 'key', true
      doubt, esc_doubt = false, false
      chef.log('map: a second world is there with the map closed too; the Map key decides (key mode, confirmed)')
    elseif not pending_wl and not wl and not told_c then
      told_c = true
      chef.log('map: a Map press and no second world: nothing can be drawn over this map')
    end
    pending = nil
  end
  if any_pressed(ESC) or besc then
    set_doubt('esc', S)
    end_move()
    quiet_until = S.t + PRESS_QUIET
  end
  follow(S)

  local open = wl and not doubt and (V.mode == 'list' or key_open)
  if open and not V.t_open then
    close_session()
    V.t_open, V.opens, V.cold = S.t, V.opens + 1, cold
  elseif not open and V.t_open then
    close_session()
  end
  cold = false              -- V.cold holds it for this open
  local w = wheel() + bwheel    -- zoom while open: wheel notches (the blind frames' after this frame's presses)
  V.wheel_frame = w
  if w ~= 0 then
    V.wheel_any = V.wheel_any + abs(w)
    if open then V.notches, V.notches_mission = V.notches + w, V.notches_mission + w
    else V.notches_shut = V.notches_shut + w end
  end
  S.map_open = open
  if open ~= logged then
    logged = open
    if open then chef.log('map open (%s mode, open %d)', V.mode, V.opens) else chef.log('map closed') end
  end
end

function V.idle(S)
  if logged then chef.log('map closed (left the mission)') end
  seen, unseen, wl = 0, 0, false
  key_open, doubt, esc_doubt, pending = false, false, false, nil
  last_frame, lx = nil, nil
  end_move()
  clear_blind()
  last_hd, open_ok = nil, false
  V.top_now, V.wheel_frame = false, 0
  if V.t_open then close_session() end
  logged = false
end

return V
