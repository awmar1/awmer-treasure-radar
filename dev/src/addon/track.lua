local T, chef = ...
-- The loot: the loader lists the pickup kinds' units every LIST_EVERY s (spread over frames); I sort them into piles.
--   stacks:  for the map views (radar, compass, bezel, overlay): a kind's pickups within kind.stack m (2D) share one
--   pickups: for world markers and waypoints: a kind's pickups within MARK_STACK m (3D)
-- A pickup near me that's picked up drops out at once (checked every ALIVE_EVERY s), without waiting for the next list;
-- one that's gone from a new list fades out on the map views.
local R = {}
local C, K = T.mod.config, T.mod.kinds
local sqrt = math.sqrt
local LIST_EVERY = 3
local ALIVE_EVERY = 0.1
local MARK_STACK = 2

R.stacks, R.pickups = {}, {}
local counts, seen_max, gone, gone_n = {}, {}, {}, {}
local stack_of = {}
local watch, last_gen, waiting_gen = nil, -1, nil
local next_alive = 0
local last_line = nil

-- the units I watch: every loot kind that's on
local watch_kinds, n_active = {}, 0
for _, k in ipairs(K.loot) do
  if k.on then
    n_active = n_active + 1
    for _, u in ipairs(k.units) do watch_kinds[u] = true end
  end
end
R.any = n_active > 0
-- Every loot kind, ticked or not, is how the loader tells a small mission from the ship (it never has any). Supplies
-- aren't: I don't know that the ship has none.
if chef.mission_kinds then
  local loot = {}
  for _, k in ipairs(K.loot) do
    if not k.supply then for _, u in ipairs(k.units) do loot[u] = true end end
  end
  chef.mission_kinds(loot)
end

function R.left(k) local c = (counts[k.id] or 0) - (gone_n[k.id] or 0); return c > 0 and c or 0 end
function R.seen(k) return seen_max[k.id] or 0 end

-- the stacks that vanished from the new list fade out where they were
local function carry_gone(old, t)
  for _, s in ipairs(old) do
    if s.n > 0 or (s.gone_t and t - s.gone_t < C.FADE) then
      local still = false
      for _, n in ipairs(R.stacks) do
        if n.kind == s.kind and (n.x - s.x) ^ 2 + (n.y - s.y) ^ 2 <= 1 then still = true; break end
      end
      if not still then
        s.n, s.gone_t = 0, s.gone_t or t
        R.stacks[#R.stacks + 1] = s
      end
    end
  end
end

local function rebuild(items, t)
  local old = R.stacks
  counts, gone, gone_n, stack_of = {}, {}, {}, {}
  R.stacks, R.pickups = {}, {}
  local stacks, pickups = R.stacks, R.pickups
  for _, it in ipairs(items) do
    local k = K.by_unit[it.kind]
    if k and k.on then
      counts[k.id] = (counts[k.id] or 0) + 1
      local z = it.z or 0
      local joined = nil
      for _, s in ipairs(stacks) do
        if s.kind == k and (s.x - it.x) ^ 2 + (s.y - it.y) ^ 2 <= k.stack * k.stack then joined = s; break end
      end
      if joined then joined.n = joined.n + 1; joined.units[#joined.units + 1] = it.unit
      else
        joined = { kind = k, x = it.x, y = it.y, z = z, n = 1, units = { it.unit } }
        stacks[#stacks + 1] = joined
      end
      stack_of[it.unit] = joined
      local near = nil
      for _, p in ipairs(pickups) do
        if p.kind == k and (p.x - it.x) ^ 2 + (p.y - it.y) ^ 2 + (p.z - z) ^ 2 <= MARK_STACK * MARK_STACK then near = p; break end
      end
      if near then near.n = near.n + 1; near.units[#near.units + 1] = it.unit
      else pickups[#pickups + 1] = { kind = k, x = it.x, y = it.y, z = z, n = 1, units = { it.unit } } end
    end
  end
  carry_gone(old, t)
  for _, k in ipairs(K.loot) do
    local c = counts[k.id] or 0
    if c > (seen_max[k.id] or 0) then seen_max[k.id] = c end
  end
  -- drawn from the least important up, so where icons overlap the more important one is on top
  table.sort(stacks, function(a, b) return a.kind.rank > b.kind.rank end)
  local parts = {}
  for _, k in ipairs(K.loot) do
    if (seen_max[k.id] or 0) > 0 then parts[#parts + 1] = k.id .. ' ' .. (counts[k.id] or 0) .. '/' .. seen_max[k.id] end
  end
  local line = table.concat(parts, ', ')
  if line ~= last_line then last_line = line; chef.log('ledger: %s', line ~= '' and line or 'nothing found yet') end
end

-- only the pickups within `reach` of me are checked, ALIVE_EVERY s apart
local function check_alive(S, reach)
  if S.t < next_alive then return end
  next_alive = S.t + ALIVE_EVERY
  local me = S.me
  local r2 = reach * reach
  for _, p in ipairs(R.pickups) do
    if p.n > 0 and (p.x - me.x) ^ 2 + (p.y - me.y) ^ 2 <= r2 then
      for _, u in ipairs(p.units) do
        if not gone[u] and chef.call_kind('Unit.alive', p.kind.id, u) ~= true then
          gone[u] = true
          gone_n[p.kind.id] = (gone_n[p.kind.id] or 0) + 1
          p.n = p.n - 1
          if p.n <= 0 then p.n, p.gone_t = 0, S.t end
          local s = stack_of[u]
          if s then
            s.n = s.n - 1
            if s.n <= 0 then s.n, s.gone_t = 0, S.t end
          end
        end
      end
    end
  end
end

-- the closest pickup pile of a kind (any kind if nil) within radius of a point, still there
function R.near(kind, x, y, z, radius)
  local best, bd = nil, radius * radius
  for _, p in ipairs(R.pickups) do
    if p.n > 0 and (kind == nil or p.kind == kind) then
      local d = (p.x - x) ^ 2 + (p.y - y) ^ 2 + ((p.z - (z or p.z)) ^ 2)
      if d <= bd then best, bd = p, d end
    end
  end
  return best, best and sqrt(bd) or nil
end

-- the alpha of a mark: 1 while it's there, fading to 0 over C.FADE once gone; nil once it's faded
function R.alpha(mark, t)
  if mark.n > 0 then return 1 end
  if not mark.gone_t then return nil end
  local a = 1 - (t - mark.gone_t) / C.FADE
  if a <= 0 then return nil end
  return a
end

function R.reset(S)
  counts, seen_max, gone, gone_n, stack_of = {}, {}, {}, {}, {}
  R.stacks, R.pickups = {}, {}
  last_gen = watch and watch.generation or -1
  last_line, next_alive = nil, 0
  local n = 0
  for _ in pairs(watch_kinds) do n = n + 1 end
  chef.log('new mission (world %d): watching %d loot unit kinds', chef.world_id(), n)
end

-- outside a mission the unit list rests
function R.idle() if watch then watch.pause() end end

-- S.need_loot (set by main): something on screen uses the loot; if not, the unit list rests
function R.update(S)
  if not R.any then return end
  if not S.need_loot then
    if watch then watch.pause() end
    return
  end
  if not watch then watch = chef.watch(watch_kinds, LIST_EVERY); R.watch = watch
  elseif not watch.active then
    -- back from a pause: the old piles may be out of date, so nothing is drawn until the fresh list is in
    watch.resume()
    waiting_gen = watch.generation
  end
  if watch.generation ~= last_gen then
    last_gen = watch.generation
    rebuild(watch.items, S.t)
  end
  if waiting_gen then
    if watch.generation == waiting_gen then R.stale = true; return end
    waiting_gen = nil
  end
  R.stale = false
  check_alive(S, (C.MARKERS or 0) + 5 > 40 and (C.MARKERS or 0) + 5 or 40)
end

return R
