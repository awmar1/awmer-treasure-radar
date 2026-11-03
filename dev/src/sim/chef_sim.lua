-- A fake Chef Loader API for running the addon's modules straight from dev/src/addon (no bundle, no archives).
-- sim.py fills SIM each frame (time, camera, input, units, map open) and reads SIM.draws back.
-- What it emulates of the real loader: the chef.* signatures, colors that only live for the frame they were made in
-- (a stale one is a warning), layers >= chef.TOP going to the top world (dropped, with a warning, while the map is
-- closed), chef.watch lists rebuilt every `every` seconds, chef.world_to_screen's "behind me" rule, the raw mouse axis
-- (Mouse.axis_index('mouse') / Mouse.axis, this frame's movement from SIM.raw_x, raw_y).
SIM = {
  t = 0, frame = 0, w = 1920, h = 1080, world_id = 1, mission = true,
  cam = { x = 0, y = 0, z = 1.6, fx = 0, fy = 1, fz = 0, yaw = 0, fov = 1.2 },
  down = {}, pressed = {}, mouse = {}, cursor = nil, wheel = 0, worlds = 1, raw_x = 0, raw_y = 0, nocam = false,
  units = {},           -- { unit = 'u1', kind = '<hex>', x, y, z, alive = true }
  draws = {}, logs = {}, warnings = {}, peer = 'ed64736ca681ab28', calls = {},
}
local warned = {}
local function warn(s) if not warned[s] then warned[s] = true; SIM.warnings[#SIM.warnings + 1] = s end end

chef = { loader = 'Chef Loader (sim)', loader_version = '0.1.1', name = 'mods/chef/treasure_radar', TOP = 2000 }
chef.options = {}
function chef.log(...) local ok, s = pcall(string.format, ...); SIM.logs[#SIM.logs + 1] = string.format('%8.2f %s', SIM.t, ok and s or tostring((...))) end
local CALLS = {
  ['Network.peer_id'] = function() return SIM.peer end,
  ['Unit.alive'] = function(u) local e = SIM.by_unit and SIM.by_unit[u]; return e ~= nil and e.alive == true end,
  ['Application.worlds'] = function() local t = { 'world:main' }; for i = 2, SIM.worlds do t[i] = 'world:' .. i end; return t end,
  ['Unit.world_position'] = function(u) local e = SIM.by_unit and SIM.by_unit[u]; if e then return { e.x, e.y, e.z } end end,
  ['Mouse.axis_index'] = function(name) if name == 'mouse' then return 0 end end,
  ['Mouse.axis'] = function(ix) if ix == 0 then return { SIM.raw_x, SIM.raw_y, 0 } end end,
  ['Vector3.to_elements'] = function(v) if type(v) == 'table' then return v[1], v[2], v[3] end end,
  -- 0.9: the census (the loader's "world N: mission (K units)"; SIM.num_units, from a scenario's 'census') and the
  -- main world (0.9.1: the camera probe and its World.debug_camera_pose stand-in are gone)
  ['World.num_units'] = function(w) return SIM.num_units end,
  ['Application.main_world'] = function() return 'world:main' end,
  -- 0.9.2: the line probe. A line object belongs to the world it was made in (dispatching or destroying it in another
  -- one is an error, as in the harness's engine); SIM.dispatched[world] = { frame, lines, lo } of its last dispatch
  -- (lo: the line object's number, in the order they were made),
  -- SIM.empty: how many dispatches had no lines (none expected). The probe never destroys a line object: the
  -- destroy stand-in stays so that a stray call is counted in SIM.calls (probe.py wants 0).
  ['World.create_line_object'] = function(w)
    SIM.line_objects = (SIM.line_objects or 0) + 1
    return { lo = SIM.line_objects, world = w, lines = 0 }
  end,
  ['World.destroy_line_object'] = function(w, lo)
    if type(lo) ~= 'table' or lo.world ~= w or lo.dead then error('a line object from another world, or destroyed') end
    lo.dead = true
  end,
  ['LineObject.reset'] = function(lo) if lo.dead then error('a destroyed line object') end; lo.lines = 0 end,
  ['LineObject.add_line'] = function(lo, c, a, b)
    if type(c) ~= 'table' or c.f ~= SIM.frame then warn('stale color (made in an earlier frame) used by add_line') end
    if type(a) ~= 'table' or type(b) ~= 'table' then error('add_line without two Vector3s') end
    lo.lines = lo.lines + 1
  end,
  ['LineObject.dispatch'] = function(w, lo)
    if lo.world ~= w or lo.dead then error('dispatch with a line object from another world, or destroyed') end
    SIM.dispatched = SIM.dispatched or {}
    SIM.dispatched[w] = { frame = SIM.frame, lines = lo.lines, lo = lo.lo }
    if lo.lines == 0 then SIM.empty = (SIM.empty or 0) + 1 end
  end,
  ['Vector3'] = function(x, y, z) return { x, y, z } end,
}
-- as the loader's guarded call: nil, 'missing' for a name it doesn't have, nil and the error for one that fails
function chef.call(name, ...)
  SIM.calls[name] = (SIM.calls[name] or 0) + 1
  local f = CALLS[name]
  if not f then return nil, 'missing' end
  local ok, a, b, c, d = pcall(f, ...)
  if not ok then return nil, tostring(a) end
  return a, b, c, d
end
function chef.call_kind(name, kind, ...) return chef.call(name, ...) end
function chef.time() return SIM.t end
function chef.world() return 'world:main' end
function chef.world_id() return SIM.world_id end
function chef.in_mission() return SIM.mission end
function chef.mission_kinds(k) SIM.mission_kinds = k end
function chef.camera() if SIM.nocam then return nil end return SIM.cam end   -- nocam: a frame without one

-- the view: +x east, +y north, +z up; screen bottom-left origin
function chef.world_to_screen(x, y, z)
  local c = SIM.cam
  local ax, ay, az = x - c.x, y - c.y, z - c.z
  local d = ax * c.fx + ay * c.fy + az * c.fz
  if d <= 0.5 then return nil end
  -- right = forward x up, up' = right x forward
  local rx, ry, rz = c.fy, -c.fx, 0
  local rl = math.sqrt(rx * rx + ry * ry); if rl < 1e-6 then rx, ry, rl = 1, 0, 1 end
  rx, ry = rx / rl, ry / rl
  local ux, uy, uz = ry * c.fz - rz * c.fy, rz * c.fx - rx * c.fz, rx * c.fy - ry * c.fx
  local f = (SIM.h / 2) / math.tan(c.fov / 2)
  local sx = SIM.w / 2 + (ax * rx + ay * ry + az * rz) / d * f
  local sy = SIM.h / 2 + (ax * ux + ay * uy + az * uz) / d * f
  return sx, sy
end

local watchers = {}
function chef.watch(kinds, every)
  local w = { kinds = kinds, every = every or 5, next = 0, items = {}, generation = 0, active = true, want_now = true }
  function w.pause() w.active = false end
  function w.resume() if not w.active then w.active, w.want_now = true, true end end
  function w.refresh() w.want_now = true end
  watchers[#watchers + 1] = w
  return w
end
-- sim.py calls this each frame before the addon's update; a scan finishes SCAN_FRAMES frames after it starts
local SCAN_FRAMES = 4
function SIM.scan()
  for _, w in ipairs(watchers) do
    if w.pending and SIM.frame >= w.pending_frame then
      local items = {}
      for _, e in ipairs(w.pending) do
        if e.alive then items[#items + 1] = { unit = e.unit, kind = e.kind, x = e.x, y = e.y, z = e.z } end
      end
      w.items, w.generation, w.pending = items, w.generation + 1, nil
    end
    if w.active and not w.pending and (w.want_now or SIM.t >= w.next) then
      w.want_now, w.next = false, SIM.t + w.every
      local list = {}
      for _, e in ipairs(SIM.units) do if w.kinds[e.kind] and e.alive then list[#list + 1] = e end end
      w.pending, w.pending_frame = list, SIM.frame + SCAN_FRAMES
    end
  end
end
function SIM.new_world()
  for _, w in ipairs(watchers) do w.items, w.pending, w.generation, w.want_now = {}, nil, w.generation + 1, true end
end

function chef.key_down(name) return SIM.down[name] == true end
function chef.key_pressed(name) return SIM.pressed[name] == true end
function chef.screen() return SIM.w, SIM.h end
function chef.wheel() return SIM.wheel end
function chef.cursor() if SIM.cursor then return SIM.cursor[1], SIM.cursor[2] end end
function chef.mouse_down(name) return SIM.mouse[name] == true end

local colors = {}
function chef.color(r, g, b, a)
  return { r, g, b, a or 255, f = SIM.frame }
end
local function rec(t)
  local c = t.c
  if type(c) ~= 'table' then warn('draw without a color: ' .. t.op); return false end
  if c.f ~= SIM.frame then warn('stale color (made in an earlier frame) used by ' .. t.op .. ': draws white in game') end
  local layer = t.layer or 900
  if layer >= chef.TOP then
    if SIM.worlds < 2 then warn('drew on the top layer while the map is closed (dropped)'); return false end
    t.top = true
  end
  SIM.draws[#SIM.draws + 1] = t
  return true
end
function chef.text_width(s, px) return #s * 6 * px - px end
function chef.rect(x, y, w, h, c, layer) rec({ op = 'rect', x = x, y = y, w = w, h = h, c = c, layer = layer }) end
function chef.text(x, y, s, px, c, layer) rec({ op = 'text', x = x, y = y, s = s, px = px, c = c, layer = layer }); return chef.text_width(s, px) end
function chef.sprite(x, y, rows, cell, cols, layer) rec({ op = 'sprite', x = x, y = y, rows = rows, cell = cell, cols = cols, c = cols.X or cols.o, layer = layer }) end
SIM.textures = {}       -- name -> true for the PNGs that exist
function chef.bitmap(tex, x, y, w, h, c, layer)
  if not SIM.textures[tex] then warn('bitmap of unknown texture ' .. tostring(tex)); return false end
  return rec({ op = 'bitmap', tex = tex, x = x, y = y, w = w, h = h, c = c, layer = layer })
end
function chef.line(x1, y1, z1, x2, y2, z2, c) rec({ op = 'line', a = { x1, y1, z1 }, b = { x2, y2, z2 }, c = c, layer = 850 }) end
