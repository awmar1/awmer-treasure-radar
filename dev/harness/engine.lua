-- Fake Stingray engine for the Treasure Radar test harness (runs inside a real Lua 5.1, driven by runner.py).
-- It installs the global `stingray` (what the game's boot script reads with rawget(_G, 'stingray')) and returns E,
-- the control table the Python runner uses to build worlds, move the camera, press keys and read back the draw calls.
--
-- Emulated sharp edges (see README.md):
--   * value types (Vector3, Vector2, Color, Quaternion, IdString64) are one-frame temporaries: used in a later frame
--     they are flagged in the warnings, and a stale Color draws white
--   * a GUI / line object used after its world went away (or after World.destroy_gui) is a fatal crash: the run aborts
--   * Unit.world_position / Unit.camera / Camera.* on a picked-up (dead) unit are a fatal crash (E.strict_units)
--   * a call the scenario names on a unit of a fragile kind is a fatal crash, alive or not (E.fragile)
--   * functions the fake doesn't have are nil (and are listed as "missing")
-- Handles (worlds, units, GUIs, cameras, materials, line objects) are userdata, like the engine's.

local E = {
  frame = 0, time = 0, w = 1920, h = 1080, peer = '1100001a2b3c4d5',
  worlds = {}, main = nil, next_id = 1,
  textures = {}, materials = { e2d6ed90906c1e8b = true }, resources = {},
  keys_down = {}, keys_prev = {}, mouse_down = {}, cursor = { 960, 540 }, wheel = 0, raw = { 0, 0 },
  cam = { x = 0, y = 0, z = 1.6, yaw = 0, pitch = 0, fov = math.rad(50) },
  warnings = {}, warn_order = {}, missing = {}, missing_order = {},
  crashed = nil, crash_trace = nil,
  strict_units = 'crash',          -- 'crash' or 'warn': position/camera calls on a dead unit
  fragile = {},                    -- hex id -> { call name = true }: calls that crash on that kind's units
  rec = {}, nrec = 0, lines = {}, counts = {},
  units_by_uid = {}, next_uid = 1,
  stats = { guis = 0, gui_destroyed = 0, values = 0 },
}

local floor, sqrt, sin, cos, tan, fmt = math.floor, math.sqrt, math.sin, math.cos, math.tan, string.format
local H = setmetatable({}, { __mode = 'k' })     -- handle userdata -> its data
local VAL = setmetatable({}, { __mode = 'k' })   -- value userdata -> its data

-- ------------------------------------------------------------------ diagnostics
function E.warn(msg)
  local w = E.warnings[msg]
  if w then w.count = w.count + 1; return end
  E.warnings[msg] = { count = 1, first_frame = E.frame, first_t = E.time }
  E.warn_order[#E.warn_order + 1] = msg
end

-- A crash: the game would die here (a null read, not a Lua error). The first one is kept with a Lua traceback, every
-- engine call from now on fails, and the runner aborts the run after this frame.
local function crash(msg)
  if not E.crashed then
    E.crashed = msg
    E.crash_frame = E.frame
    E.crash_trace = debug.traceback('CRASH: ' .. msg, 2)
  end
  error('ENGINE CRASH: ' .. msg, 2)
end
E.crash = crash

local function alive_check()
  if E.crashed then error('ENGINE CRASH (already): ' .. E.crashed, 3) end
end

-- ------------------------------------------------------------------ handles and values
local HPROTO = newproxy(true)
getmetatable(HPROTO).__tostring = function(p) local d = H[p]; return d and ('[' .. d.kind .. ' ' .. tostring(d.id) .. ']') or '[dead handle]' end
getmetatable(HPROTO).__index = function(p, k) error('engine handle has no field ' .. tostring(k), 2) end
local function handle(kind, data)
  local p = newproxy(HPROTO)
  data.kind, data.id = kind, data.id or E.next_id
  E.next_id = E.next_id + 1
  H[p] = data
  data.h = p
  return p
end
local function get(p, kind, what)
  local d = H[p]
  if not d or d.kind ~= kind then error(fmt('%s: bad argument (expected %s, got %s)', what, kind, d and d.kind or type(p)), 3) end
  return d
end

local VPROTO = newproxy(true)
local vmt = getmetatable(VPROTO)
vmt.__index = function(p, k)
  local d = VAL[p]
  if d and d.frame ~= E.frame then E.warn('stale ' .. d.t .. ' read (made in an earlier frame)') end
  if d then return d[k] end
end
vmt.__tostring = function(p)
  local d = VAL[p]
  if not d then return '[value]' end
  if d.t == 'Color' then return fmt('Color(%s, %s, %s, %s)', d.a, d.r, d.g, d.b) end
  if d.t == 'IdString64' then return 'IdString64(' .. d.hex .. ')' end
  return fmt('%s(%s, %s, %s)', d.t, tostring(d.x), tostring(d.y), tostring(d.z))
end
local function value(t, d)
  local p = newproxy(VPROTO)
  d.t, d.frame = t, E.frame
  VAL[p] = d
  return p
end
-- the value's data; a value from an earlier frame is flagged (its memory would be reused by now)
local function val(p, t, what)
  local d = VAL[p]
  if not d or (t and d.t ~= t and not (t == 'Vector3' and d.t == 'Vector2')) then
    error(fmt('%s: bad argument (expected %s, got %s)', what, t or 'a value', d and d.t or type(p)), 3)
  end
  if d.frame ~= E.frame then d.stale = true; E.warn(fmt('stale %s used in %s (made in frame %d, used in frame %d)', d.t, what, d.frame, E.frame)) end
  return d
end

-- ------------------------------------------------------------------ the stingray table (unknown names are nil)
local S = {}
local function note_missing(name)
  if not E.missing[name] then E.missing[name] = E.frame; E.missing_order[#E.missing_order + 1] = name end
end
local function api_table(name, t, call)
  setmetatable(t, { __index = function(_, k) note_missing(name .. '.' .. tostring(k)); return nil end, __call = call })
  S[name] = t
  return t
end

-- vectors -----------------------------------------------------------
local function v3(x, y, z) E.stats.values = E.stats.values + 1; return value('Vector3', { x = x or 0, y = y or 0, z = z or 0 }) end
E.v3 = v3
local Vector3 = api_table('Vector3', {}, function(_, x, y, z) alive_check(); return v3(x, y, z) end)
function Vector3.to_elements(v) alive_check(); local d = val(v, nil, 'Vector3.to_elements'); return d.x or 0, d.y or 0, d.z or 0 end
function Vector3.x(v) return val(v, 'Vector3', 'Vector3.x').x end
function Vector3.y(v) return val(v, 'Vector3', 'Vector3.y').y end
function Vector3.z(v) return val(v, 'Vector3', 'Vector3.z').z end
function Vector3.length(v) local d = val(v, 'Vector3', 'Vector3.length'); return sqrt(d.x * d.x + d.y * d.y + d.z * d.z) end
-- (in Stingray a Vector2 is a Vector3 with z = 0)
api_table('Vector2', {}, function(_, x, y) alive_check(); E.stats.values = E.stats.values + 1; return value('Vector2', { x = x or 0, y = y or 0, z = 0 }) end)

-- Color(a, r, g, b) or Color(r, g, b) ---------------------------------
api_table('Color', {}, function(_, a, r, g, b)
  alive_check()
  if b == nil then a, r, g, b = 255, a, r, g end
  E.stats.values = E.stats.values + 1
  return value('Color', { a = a or 255, r = r or 0, g = g or 0, b = b or 0 })
end)

-- quaternions --------------------------------------------------------
local function qmul(a, b)
  return { x = a.w * b.x + a.x * b.w + a.y * b.z - a.z * b.y, y = a.w * b.y - a.x * b.z + a.y * b.w + a.z * b.x,
           z = a.w * b.z + a.x * b.y - a.y * b.x + a.z * b.w, w = a.w * b.w - a.x * b.x - a.y * b.y - a.z * b.z }
end
local function qrot(q, x, y, z)
  -- v' = v + w t + q x t, t = 2 (q x v)
  local tx, ty, tz = 2 * (q.y * z - q.z * y), 2 * (q.z * x - q.x * z), 2 * (q.x * y - q.y * x)
  return x + q.w * tx + (q.y * tz - q.z * ty), y + q.w * ty + (q.z * tx - q.x * tz), z + q.w * tz + (q.x * ty - q.y * tx)
end
-- the camera's rotation: yaw clockwise from north (+y) about +z, then pitch up about the camera's x (z is up; a
-- Stingray camera looks along its local +y)
local function yaw_pitch_q(yaw, pitch)
  local qz = { x = 0, y = 0, z = sin(-yaw / 2), w = cos(-yaw / 2) }
  local qx = { x = sin(pitch / 2), y = 0, z = 0, w = cos(pitch / 2) }
  return qmul(qz, qx)
end
local Quaternion = api_table('Quaternion', {}, function(_, axis, angle)
  alive_check()
  local a = val(axis, 'Vector3', 'Quaternion')
  local s = sin(angle / 2)
  return value('Quaternion', { x = a.x * s, y = a.y * s, z = a.z * s, w = cos(angle / 2) })
end)
function Quaternion.forward(q) alive_check(); return v3(qrot(val(q, 'Quaternion', 'Quaternion.forward'), 0, 1, 0)) end
function Quaternion.right(q) alive_check(); return v3(qrot(val(q, 'Quaternion', 'Quaternion.right'), 1, 0, 0)) end
function Quaternion.up(q) alive_check(); return v3(qrot(val(q, 'Quaternion', 'Quaternion.up'), 0, 0, 1)) end
function Quaternion.to_elements(q) local d = val(q, 'Quaternion', 'Quaternion.to_elements'); return d.x, d.y, d.z, d.w end

-- IdString64 -----------------------------------------------------------
local IdString64 = api_table('IdString64', {}, function(_, name)
  alive_check()
  return value('IdString64', { hex = 'name:' .. tostring(name) })
end)
function IdString64.from_hex(hex)
  alive_check()
  if type(hex) ~= 'string' or not hex:match('^%x+$') or #hex > 16 then error('IdString64.from_hex: bad hex string ' .. tostring(hex), 2) end
  hex = string.rep('0', 16 - #hex) .. hex:lower()
  return value('IdString64', { hex = hex })
end
function IdString64.to_hex(id) return val(id, 'IdString64', 'IdString64.to_hex').hex end
local function idhex(id, what)
  if type(id) == 'string' then return id end
  return val(id, 'IdString64', what).hex
end

-- ------------------------------------------------------------------ worlds
local function world_of(h, what)
  local d = get(h, 'world', what)
  if d.destroyed then crash(what .. ' on a world that was destroyed (' .. d.name .. ')') end
  return d
end
function E.new_world(name, as_main)
  local w = { name = name, t = 0, units = {}, guis = {}, created = E.frame }
  handle('world', w)
  if as_main then
    if E.main then E.destroy_world(E.main.name) end
    table.insert(E.worlds, 1, w)
    E.main = w
  else
    E.worlds[#E.worlds + 1] = w
  end
  return w.id
end
function E.find_world(name)
  for _, w in ipairs(E.worlds) do if w.name == name then return w end end
end
function E.destroy_world(name)
  for i, w in ipairs(E.worlds) do
    if w.name == name then
      w.destroyed = true
      for _, u in ipairs(w.units) do local d = H[u]; d.alive, d.removed = false, true end
      for _, g in pairs(w.guis) do g.destroyed = true end
      table.remove(E.worlds, i)
      if E.main == w then E.main = nil end
      return true
    end
  end
  return false
end
function E.world_names()
  local t = {}
  for i, w in ipairs(E.worlds) do t[i] = w.name end
  return table.concat(t, ',')
end

-- units --------------------------------------------------------------
-- E.add_unit(world name or nil for the main world, resource id hex, x, y, z, cameras) -> uid
function E.add_unit(wname, hex, x, y, z, ncams)
  local w = wname and E.find_world(wname) or E.main
  local uid = E.next_uid
  E.next_uid = uid + 1
  local d = { uid = uid, hex = hex, name = '#ID[' .. hex .. ']', x = x or 0, y = y or 0, z = z or 0, alive = true,
              removed = false, ncams = ncams or 0, world = w }
  local h = handle('unit', d)
  w.units[#w.units + 1] = h
  E.units_by_uid[uid] = d
  return uid
end
-- n units of random ids (not in `avoid`, a set of hex ids) scattered within `spread` meters, made in Lua (fast)
function E.add_filler(wname, n, seed, spread, avoid)
  local w = wname and E.find_world(wname) or E.main
  local state = seed or 1
  local function rnd()   -- a small LCG so runs are repeatable
    state = (state * 1103515245 + 12345) % 2147483648
    return state / 2147483648
  end
  for i = 1, n do
    local hex
    repeat hex = fmt('%08x%08x', floor(rnd() * 4294967295), floor(rnd() * 4294967295)) until not (avoid and avoid[hex])
    local d = { uid = E.next_uid, hex = hex, name = '#ID[' .. hex .. ']', x = (rnd() * 2 - 1) * spread,
                y = (rnd() * 2 - 1) * spread, z = rnd() * 20, alive = true, removed = false, ncams = 0, world = w, filler = true }
    E.next_uid = E.next_uid + 1
    w.units[#w.units + 1] = handle('unit', d)
  end
end
function E.kill_unit(uid) local d = E.units_by_uid[uid]; if d then d.alive = false end end
function E.move_unit(uid, x, y, z) local d = E.units_by_uid[uid]; if d then d.x, d.y, d.z = x, y, z end end
function E.remove_unit(uid)
  local d = E.units_by_uid[uid]
  if not d or d.removed then return end
  d.alive, d.removed = false, true
  local list = d.world.units
  for i = #list, 1, -1 do if list[i] == d.h then table.remove(list, i); break end end
end
function E.unit_state(uid)
  local d = E.units_by_uid[uid]
  if not d then return 'none' end
  return d.removed and 'removed' or (d.alive and 'alive' or 'dead')
end

local function unit_of(u, what)
  local d = get(u, 'unit', what)
  if d.world.destroyed and not d.removed then d.removed, d.alive = true, false end
  return d
end
-- some kinds crash the game on a call any unit of theirs gets (on the ship, Unit.world_position on one did)
function E.set_fragile(hex, what)
  local f = E.fragile[hex] or {}
  f[what] = true
  E.fragile[hex] = f
end
local function fragile_check(d, what)
  local f = E.fragile[d.hex]
  if f and f[what] then crash(what .. ' on a unit of a kind it crashes on (' .. d.name .. ')') end
end
local function unit_must_live(d, what)
  if d.removed or not d.alive then
    local msg = what .. ' on a ' .. (d.removed and 'destroyed' or 'dead') .. ' unit (' .. d.name .. ')'
    if E.strict_units == 'crash' then crash(msg) else E.warn(msg) end
  end
end

-- ------------------------------------------------------------------ cameras
local function cam_basis()
  local c = E.cam
  local sy, cy, sp, cp = sin(c.yaw), cos(c.yaw), sin(c.pitch), cos(c.pitch)
  return { sy * cp, cy * cp, sp }, { cy, -sy, 0 }, { -sy * sp, -cy * sp, cp }
end
function E.set_camera(x, y, z, yaw_deg, pitch_deg, fov_deg)
  local c = E.cam
  c.x, c.y, c.z, c.yaw, c.pitch = x, y, z, math.rad(yaw_deg), math.rad(pitch_deg)
  if fov_deg then c.fov = math.rad(fov_deg) end
  if E.cam_uid then E.move_unit(E.cam_uid, x, y, z) end
end
-- world point -> screen pixels (bottom-left origin) and depth along the view
local function project(x, y, z)
  local c = E.cam
  local f, r, u = cam_basis()
  local dx, dy, dz = x - c.x, y - c.y, z - c.z
  local zc = dx * f[1] + dy * f[2] + dz * f[3]
  local xc = dx * r[1] + dy * r[2] + dz * r[3]
  local yc = dx * u[1] + dy * u[2] + dz * u[3]
  local k = 1 / tan(c.fov / 2)
  local div = zc ~= 0 and zc or 1e-6
  return E.w / 2 + xc / div * k * E.h / 2, E.h / 2 + yc / div * k * E.h / 2, zc
end
E.project = project

-- ------------------------------------------------------------------ stingray.Application
local Application = api_table('Application', {})
function Application.main_world() alive_check(); return E.main and E.main.h or nil end
function Application.worlds()
  alive_check()
  local t = {}
  for i, w in ipairs(E.worlds) do t[i] = w.h end
  return t
end
function Application.back_buffer_size() alive_check(); return E.w, E.h end
function Application.can_get(typ, id)
  alive_check()
  local hex = idhex(id, 'Application.can_get')
  if typ == 'texture' then return E.textures[hex] == true end
  if typ == 'material' then return E.materials[hex] == true end
  return E.resources[tostring(typ) .. ':' .. hex] == true
end

-- ------------------------------------------------------------------ stingray.World
local World = api_table('World', {})
function World.time(w) alive_check(); return world_of(w, 'World.time').t end
function World.num_units(w) alive_check(); return #world_of(w, 'World.num_units').units end
function World.units(w)
  alive_check()
  local d = world_of(w, 'World.units')
  local t, src = {}, d.units
  for i = 1, #src do t[i] = src[i] end
  return t
end
function World.create_screen_gui(w, ...)
  alive_check()
  local d = world_of(w, 'World.create_screen_gui')
  local g = { world = d, args = table.concat({ ... }, ' '), created = E.frame, tex = nil }
  local h = handle('gui', g)
  d.guis[g.id] = g
  E.stats.guis = E.stats.guis + 1
  return h
end
function World.destroy_gui(w, gh)
  alive_check()
  local d = world_of(w, 'World.destroy_gui')
  local g = get(gh, 'gui', 'World.destroy_gui')
  if g.destroyed then crash('World.destroy_gui on a GUI that was already destroyed') end
  if g.world ~= d then crash('World.destroy_gui with a GUI from another world') end
  g.destroyed = true
  d.guis[g.id] = nil
  E.stats.gui_destroyed = E.stats.gui_destroyed + 1
end
function World.create_line_object(w)
  alive_check()
  local d = world_of(w, 'World.create_line_object')
  local lo = { world = d, lines = {} }
  return handle('line_object', lo)
end

-- ------------------------------------------------------------------ stingray.Unit
local Unit = api_table('Unit', {})
function Unit.alive(u)
  alive_check()
  local d = H[u]
  if not d or d.kind ~= 'unit' then return false end
  if d.world.destroyed then return false end
  return d.alive and not d.removed
end
function Unit.debug_name(u)
  alive_check()
  local d = unit_of(u, 'Unit.debug_name')
  if d.removed then E.warn('Unit.debug_name on a destroyed unit (a stale handle; returned its old name)') end
  return d.name
end
function Unit.world_position(u, node)
  alive_check()
  local d = unit_of(u, 'Unit.world_position')
  fragile_check(d, 'Unit.world_position')
  unit_must_live(d, 'Unit.world_position')
  return v3(d.x, d.y, d.z)
end
function Unit.num_cameras(u)
  alive_check()
  local d = unit_of(u, 'Unit.num_cameras')
  fragile_check(d, 'Unit.num_cameras')
  if d.removed then E.warn('Unit.num_cameras on a destroyed unit (a stale handle)'); return 0 end
  return d.ncams
end
function Unit.camera(u, which)
  alive_check()
  local d = unit_of(u, 'Unit.camera')
  unit_must_live(d, 'Unit.camera')
  if d.ncams < 1 then error('Unit.camera: the unit has no camera ' .. tostring(which), 2) end
  d.cam_h = d.cam_h or handle('camera', { unit = d })
  return d.cam_h
end

-- ------------------------------------------------------------------ stingray.Camera
local Camera = api_table('Camera', {})
local function cam_of(c, what)
  local d = get(c, 'camera', what)
  unit_must_live(d.unit, what)
  return d
end
function Camera.world_position(c) alive_check(); cam_of(c, 'Camera.world_position'); return v3(E.cam.x, E.cam.y, E.cam.z) end
function Camera.world_rotation(c)
  alive_check()
  cam_of(c, 'Camera.world_rotation')
  local q = yaw_pitch_q(E.cam.yaw, E.cam.pitch)
  return value('Quaternion', q)
end
function Camera.vertical_fov(c) alive_check(); cam_of(c, 'Camera.vertical_fov'); return E.cam.fov end
-- a world position on screen: x, y in pixels from the bottom left (z: depth along the view; behind me it mirrors,
-- like a real projection)
function Camera.world_to_screen(c, p)
  alive_check()
  cam_of(c, 'Camera.world_to_screen')
  local d = val(p, 'Vector3', 'Camera.world_to_screen')
  local sx, sy, depth = project(d.x, d.y, d.z)
  return v3(sx, sy, depth)
end

-- ------------------------------------------------------------------ stingray.Gui (draw calls are recorded)
local Gui = api_table('Gui', {})
local WHITE = { a = 255, r = 255, g = 255, b = 255 }
local function gui_of(g, what)
  local d = get(g, 'gui', what)
  if d.world.destroyed then crash(what .. ' on a GUI whose world went away (' .. d.world.name .. ')') end
  if d.destroyed then crash(what .. ' on a GUI destroyed with World.destroy_gui') end
  return d
end
local function color_of(c, what)
  if c == nil then return WHITE end
  local d = VAL[c]
  if not d or d.t ~= 'Color' then error(what .. ': bad color argument (' .. type(c) .. ')', 3) end
  if d.frame ~= E.frame then
    E.warn(fmt('stale Color used in %s (made in frame %d): drawn white', what, d.frame))
    return WHITE
  end
  return d
end
local function world_slot(wd)
  if wd == E.main then return 0, 'main' end
  local k = 0
  for _, w in ipairs(E.worlds) do
    if w ~= E.main then k = k + 1; if w == wd then return k, w.name end end
  end
  return 99, wd.name
end
local function record(kind, gd, p, s, c, tex)
  local slot, wname = world_slot(gd.world)
  local n = E.nrec + 1
  E.nrec = n
  E.rec[n] = { kind, slot, wname, gd.id, p.z or 0, p.x or 0, p.y or 0, s.x or 0, s.y or 0, c.a, c.r, c.g, c.b, tex or '-' }
  local key = (slot == 0 and 'main_' or 'top_') .. kind
  E.counts[key] = (E.counts[key] or 0) + 1
end
function Gui.rect(g, pos, size, color)
  alive_check()
  local gd = gui_of(g, 'Gui.rect')
  local p, s = val(pos, 'Vector3', 'Gui.rect'), val(size, 'Vector3', 'Gui.rect')
  record('rect', gd, p, s, color_of(color, 'Gui.rect'))
end
function Gui.material(g, id)
  alive_check()
  local gd = gui_of(g, 'Gui.material')
  local hex = idhex(id, 'Gui.material')
  if not E.materials[hex] then return nil end
  gd.mats = gd.mats or {}
  gd.mats[hex] = gd.mats[hex] or handle('material', { gui = gd, hex = hex })
  return gd.mats[hex]
end
function Gui.bitmap(g, material, pos, size, color)
  alive_check()
  local gd = gui_of(g, 'Gui.bitmap')
  local hex = idhex(material, 'Gui.bitmap')
  local p, s = val(pos, 'Vector3', 'Gui.bitmap'), val(size, 'Vector3', 'Gui.bitmap')
  local tex
  if not E.materials[hex] then tex = 'nomaterial:' .. hex
  else tex = gd.tex and gd.tex[hex] or ('notexture:' .. hex) end
  record('bitmap', gd, p, s, color_of(color, 'Gui.bitmap'), tex)
end

local Material = api_table('Material', {})
function Material.set_texture(m, slot, tex)
  alive_check()
  local md = get(m, 'material', 'Material.set_texture')
  if md.gui.world.destroyed or md.gui.destroyed then crash('Material.set_texture on the material of a GUI that went away') end
  local slot_hex, tex_hex = idhex(slot, 'Material.set_texture'), idhex(tex, 'Material.set_texture')
  if not E.textures[tex_hex] then E.warn('Material.set_texture with a texture that is not loaded: ' .. tex_hex) end
  md.gui.tex = md.gui.tex or {}
  md.gui.tex[md.hex] = tex_hex
  md.slot = slot_hex
end

-- ------------------------------------------------------------------ stingray.LineObject
local LineObject = api_table('LineObject', {})
local function lo_of(lo, what)
  local d = get(lo, 'line_object', what)
  if d.world.destroyed then crash(what .. ' on a line object whose world went away') end
  return d
end
function LineObject.reset(lo) alive_check(); lo_of(lo, 'LineObject.reset').lines = {} end
function LineObject.add_line(lo, color, a, b)
  alive_check()
  local d = lo_of(lo, 'LineObject.add_line')
  local c = color_of(color, 'LineObject.add_line')
  local pa, pb = val(a, 'Vector3', 'LineObject.add_line'), val(b, 'Vector3', 'LineObject.add_line')
  d.lines[#d.lines + 1] = { c.a, c.r, c.g, c.b, pa.x, pa.y, pa.z, pb.x, pb.y, pb.z }
end
function LineObject.dispatch(w, lo)
  alive_check()
  local wd = world_of(w, 'LineObject.dispatch')
  local d = lo_of(lo, 'LineObject.dispatch')
  if d.world ~= wd then crash('LineObject.dispatch with a line object from another world') end
  for _, l in ipairs(d.lines) do E.lines[#E.lines + 1] = l end
  E.counts.lines = (E.counts.lines or 0) + #d.lines
end

-- ------------------------------------------------------------------ input
-- Key names as the engine knows them (Keyboard.button_index returns nil for any other name).
local KEYS = { 'escape', 'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12', 'tab', 'enter',
  'space', 'backspace', 'left shift', 'right shift', 'left ctrl', 'right ctrl', 'left alt', 'right alt', 'up', 'down',
  'left', 'right', 'insert', 'delete', 'home', 'end', 'page up', 'page down', 'numpad +', 'numpad -', 'numpad *',
  'numpad /', 'numpad enter', 'numpad 0', 'numpad 1', 'numpad 2', 'numpad 3', 'numpad 4', 'numpad 5', 'numpad 6',
  'numpad 7', 'numpad 8', 'numpad 9', 'num lock', 'caps lock',
  'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x',
  'y', 'z', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9' }
local KEY_INDEX, KEY_NAME = {}, {}
for i, k in ipairs(KEYS) do KEY_INDEX[k] = i - 1; KEY_NAME[i - 1] = k end
E.KEY_INDEX = KEY_INDEX

local Keyboard = api_table('Keyboard', {})
function Keyboard.button_index(name) alive_check(); return KEY_INDEX[name] end
function Keyboard.button_name(i) return KEY_NAME[i] end
function Keyboard.button(i) alive_check(); local k = KEY_NAME[i]; return (k and E.keys_down[k]) and 1 or 0 end
function Keyboard.pressed(i) alive_check(); local k = KEY_NAME[i]; return (k and E.keys_down[k] and not E.keys_prev[k]) and true or false end
function Keyboard.released(i) alive_check(); local k = KEY_NAME[i]; return (k and E.keys_prev[k] and not E.keys_down[k]) and true or false end

local MOUSE_AXES = { cursor = 0, delta = 1, wheel = 2, mouse = 3 }   -- mouse: raw counts this frame (the game's too)
local MOUSE_BUTTONS = { left = 0, right = 1, middle = 2, extra_1 = 3, extra_2 = 4 }
local MOUSE_BUTTON_NAME = {}
for k, v in pairs(MOUSE_BUTTONS) do MOUSE_BUTTON_NAME[v] = k end
local Mouse = api_table('Mouse', {})
function Mouse.axis_index(name) alive_check(); return MOUSE_AXES[name] end
function Mouse.axis(i)
  alive_check()
  if i == 0 then return v3(E.cursor[1], E.cursor[2], 0) end
  if i == 2 then return v3(0, E.wheel, 0) end
  if i == 3 then return v3(E.raw[1], E.raw[2], 0) end
  return v3(0, 0, 0)
end
function Mouse.button_index(name) alive_check(); return MOUSE_BUTTONS[name] end
function Mouse.button(i) alive_check(); local k = MOUSE_BUTTON_NAME[i]; return (k and E.mouse_down[k]) and 1 or 0 end
function Mouse.pressed(i) alive_check(); local k = MOUSE_BUTTON_NAME[i]; return (k and E.mouse_down[k] and not (E.mouse_prev or {})[k]) and true or false end

local Network = api_table('Network', {})
function Network.peer_id() alive_check(); return E.peer end

setmetatable(S, { __index = function(_, k) note_missing(tostring(k)); return nil end })
E.S = S

-- ------------------------------------------------------------------ the runner's controls
-- input for the coming frame: keys = 'f7,tab' (names held down), mouse = 'left', cursor x/y, wheel delta, raw mouse
-- counts x/y
function E.set_input(keys, mouse, cx, cy, wheel, rx, ry)
  E.keys_prev, E.keys_down = E.keys_down, {}
  for k in tostring(keys or ''):gmatch('[^,]+') do E.keys_down[k] = true end
  E.mouse_prev, E.mouse_down = E.mouse_down, {}
  for k in tostring(mouse or ''):gmatch('[^,]+') do E.mouse_down[k] = true end
  E.cursor = { cx or E.cursor[1], cy or E.cursor[2] }
  E.wheel = wheel or 0
  E.raw = { rx or 0, ry or 0 }
end
-- a new frame: the temporaries of the last one die, the clock moves on
function E.begin_frame(dt)
  E.frame = E.frame + 1
  E.time = E.time + dt
  for _, w in ipairs(E.worlds) do w.t = w.t + dt end
  E.rec, E.nrec, E.lines, E.counts = {}, 0, {}, {}
end
function E.count(key) return E.counts[key] or 0 end
-- this frame's draw calls as text, one per line (tab separated):
-- kind, world slot (0 = main, 1.. = the others), world name, gui id, layer, x, y, w, h, a, r, g, b, texture
function E.dump()
  local out = {}
  for i = 1, E.nrec do
    local r = E.rec[i]
    out[i] = fmt('%s\t%d\t%s\t%d\t%.4f\t%.4f\t%.4f\t%.4f\t%.4f\t%d\t%d\t%d\t%d\t%s', r[1], r[2], r[3], r[4], r[5], r[6], r[7],
      r[8], r[9], r[10], r[11], r[12], r[13], r[14])
  end
  return table.concat(out, '\n')
end
function E.dump_lines()
  local out = {}
  for i, l in ipairs(E.lines) do out[i] = table.concat(l, '\t') end
  return table.concat(out, '\n')
end
function E.dump_warnings()
  local out = {}
  for i, m in ipairs(E.warn_order) do local w = E.warnings[m]; out[i] = fmt('%d\t%d\t%.3f\t%s', w.count, w.first_frame, w.first_t, m) end
  return table.concat(out, '\n')
end
function E.dump_missing()
  local out = {}
  for i, m in ipairs(E.missing_order) do out[i] = fmt('%d\t%s', E.missing[m], m) end
  return table.concat(out, '\n')
end
function E.set_texture_loaded(hex) E.textures[hex] = true end
function E.set_material_loaded(hex) E.materials[hex] = true end
function E.num_units(wname) local w = wname and E.find_world(wname) or E.main; return w and #w.units or 0 end
function E.make_camera_unit(wname, hex)
  E.cam_uid = E.add_unit(wname, hex, E.cam.x, E.cam.y, E.cam.z, 1)
  return E.cam_uid
end

stingray = S
return E
