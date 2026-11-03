local T, chef = ...
-- Objectives, structures, nests, caches and extraction for the map views (T.mod.objectives.marks).
-- My own slow unit list (chef.watch, every EVERY s) over the units of every map kind that's on; it runs while the
-- map is closed and not hidden (for the radar; 0.9.3: with no radar too, for the open map's overlay and legend).
-- Units of a group close together make one mark at their centroid:
--   nests        holes of one faction within JOIN.nest m: one mark per nest, SMALL / MEDIUM / LARGE by its holes
--   structures   of a kind within JOIN.structure m (an outpost's fabricators), objectives' parts within JOIN.objective m
-- A mark's state is 'unknown' (drawn as active) until it's 'done':
--   gone     every member is gone from a fresh list, or Unit.alive says so (marks within ALIVE_REACH m, every
--            ALIVE_EVERY s)
--   swap     the kind's done = 'swap:<id>' and a unit of that id turns up within SWAP_REACH m
--   manual   MANUAL_KEY (none since 0.8; F9 before) toggles the mark nearest my view direction within MANUAL_REACH m (it stays as set)
-- Marks are kept across pauses (map open, HUD hidden) and cleared on a new mission. Mark tables are reused from list
-- to list (matched by group and position). A done mark keeps n = 0: views draw it dimmed with done_tex(mark) over it.
-- Normal builds watch the verified and likely kinds; the structures_all option the guesses too. A kind with more than CAP units in a mission is a wrong id: dropped for that mission, logged once.
-- Exports: marks, state, wants(S), set_state(mark, state), nearest(x, y, radius), done_tex(mark), anim_probe (hook).
local O = {}
local C, K = T.mod.config, T.mod.kinds
local sqrt, max, abs, floor = math.sqrt, math.max, math.abs, math.floor
local fmt, concat, sort, upper = string.format, table.concat, table.sort, string.upper

local EVERY = 6                -- seconds between my unit lists (structures don't move; the alive check covers near ones)
local SYNC = 1.5               -- my next list moves onto track's nearest one when that's this close: one walk for both
local ALIVE_EVERY = 1
local ALIVE_REACH = 100
local JOIN = { nest = 50, structure = 30, objective = 25, side_objective = 25, poi = 5, extract = 25 }
local HOLE = 3                 -- a nest's units this close together are one hole (a medium hole and its ceiling)
local SWAP_REACH = 10
local CAP, CAP_NEST = 40, 120  -- bug holes come by the dozen: a map with ten nests is a real one
local MANUAL_KEY = C.KEYS and C.KEYS.done   -- 0.8: no key (nil); the sim and old builds can still set one
local MANUAL_REACH = 60
local MANUAL_CONE = 0.5        -- within 60 degrees of my view direction
local NEST_SIZE = { bug_hole_small = 1, bug_hole_medium = 2, bug_hole_large = 3, bug_colony_spawner = 4 }
local CAT_ORDER = { poi = 1, nest = 2, structure = 3, side_objective = 4, objective = 5, extract = 6 }
local CATS = { 'nest', 'structure', 'objective', 'side_objective', 'poi', 'extract' }
local NOUN = {
  nest = { 'nest', 'nests' }, structure = { 'structure', 'structures' }, objective = { 'objective', 'objectives' },
  side_objective = { 'side objective', 'side objectives' }, poi = { 'cache', 'caches' },
  extract = { 'extraction', 'extractions' },
}
local WHY = { gone = 'gone from the list', alive = 'destroyed', swap = 'wreck seen', manual = 'by hand',
              set = 'set', anim = 'animation' }

local opt = chef.options or {}
local TESTER = opt.structures_all == true

-- ------------------------------------------------------------------ the kinds I watch
local used, used_list, guess_on = {}, {}, {}
local swap_of, anim_want = {}, {}
for _, k in ipairs(K.map) do
  if k.on and (k.conf == 'verified' or k.conf == 'likely' or TESTER) then
    used[k.id] = k
    used_list[#used_list + 1] = k
    if k.conf == 'guess' then guess_on[#guess_on + 1] = k.id end
    local d = type(k.done) == 'string' and k.done or ''
    local hex = d:match('^swap:(%x+)$')
    if hex then
      local l = swap_of[hex]
      if not l then l = {}; swap_of[hex] = l end
      l[#l + 1] = k
    end
    local a = d:match('^anim:(.+)$')
    if a then anim_want[k.id] = a end
  end
end
O.any = #used_list > 0

-- the watch's kinds (hex -> true), refilled in place (the watch keeps this table): used kinds not dropped, and the
-- swap ids
local watch_kinds, dropped = {}, {}
local function fill_watch()
  for h in pairs(watch_kinds) do watch_kinds[h] = nil end
  for _, k in ipairs(used_list) do
    if not dropped[k.id] then for _, u in ipairs(k.units) do watch_kinds[u] = true end end
  end
  for h in pairs(swap_of) do watch_kinds[h] = true end
end
fill_watch()
local function count(t) local n = 0; for _ in pairs(t) do n = n + 1 end; return n end

O.marks = {}
O.state = { running = false, tester = TESTER, kinds = #used_list, units = count(watch_kinds), counts = {}, done = 0,
            line = nil }

local watch, last_gen = nil, -1
local gone = {}                 -- units Unit.alive says are gone (since the last list)
local next_alive = 0
local last_line, last_kinds, empty_noted = nil, nil, false
local last_S = nil

local function group_of(k) return k.cat == 'nest' and ('nest:' .. tostring(k.faction or 'any')) or k.id end
local function label_of(m)
  if m.kind.cat ~= 'nest' then return m.kind.label end
  local s = m.size or 0
  return s <= 3 and 'SMALL NEST' or s <= 6 and 'MEDIUM NEST' or 'LARGE NEST'
end
local function where(m)
  local S = last_S
  if not (S and S.me) then return '' end
  return fmt(' %d m', sqrt((m.x - S.me.x) ^ 2 + (m.y - S.me.y) ^ 2) + 0.5)
end

-- ------------------------------------------------------------------ the log line (one per change)
local function summarize()
  local cnt, holes, done = {}, 0, 0
  for _, m in ipairs(O.marks) do
    local cat = m.kind.cat
    cnt[cat] = (cnt[cat] or 0) + 1
    if m.state == 'done' then done = done + 1
    elseif cat == 'nest' then holes = holes + (m.holes or 0) end
  end
  local parts = {}
  for _, cat in ipairs(CATS) do
    local c = cnt[cat]
    if c then
      local s = c .. ' ' .. NOUN[cat][c == 1 and 1 or 2]
      if cat == 'nest' then s = s .. ' (' .. holes .. (holes == 1 and ' hole)' or ' holes)') end
      parts[#parts + 1] = s
    end
  end
  local line = #parts > 0 and concat(parts, ', ') or 'none found yet'
  if done > 0 then line = line .. '; ' .. done .. ' done' end
  O.state.counts, O.state.done = cnt, done
  if line ~= last_line then
    last_line, O.state.line = line, line
    chef.log('structures: %s', line)
  end
end

local function set_done(m, why)
  m.state, m.why = 'done', why
  chef.log('structures: %s%s done (%s)', m.label, where(m), WHY[why] or why)
end

-- drawn from the least important up: done marks first, then caches, nests, structures, side objectives, objectives
local function order(a, b)
  local da, db = a.state == 'done', b.state == 'done'
  if da ~= db then return da end
  local ca, cb = CAT_ORDER[a.kind.cat] or 0, CAT_ORDER[b.kind.cat] or 0
  if ca ~= cb then return ca < cb end
  return (a.kind.rank or 0) > (b.kind.rank or 0)
end
local function refill(list)
  sort(list, order)
  local M = O.marks
  if list == M then return end
  for i = #M, 1, -1 do M[i] = nil end
  for i = 1, #list do M[i] = list[i] end
end

-- ------------------------------------------------------------------ a fresh list
local function drop(k, n)
  dropped[k.id] = true
  for _, u in ipairs(k.units) do if not swap_of[u] then watch_kinds[u] = nil end end
  chef.log('structures: %s (%s) has %d units in this mission: not what I took it for, dropped until the next mission',
    k.id, k.conf, n)
end

local function rebuild(items)
  -- the units per kind, and the cap
  local per = {}
  for i = 1, #items do
    local k = K.by_unit[items[i].kind]
    if k and used[k.id] and not dropped[k.id] then per[k.id] = (per[k.id] or 0) + 1 end
  end
  for id, n in pairs(per) do
    local k = used[id]
    if n > (k.cat == 'nest' and CAP_NEST or CAP) then drop(k, n) end
  end
  if TESTER then
    local parts = {}
    for _, k in ipairs(used_list) do
      if per[k.id] and not dropped[k.id] then parts[#parts + 1] = k.id .. ' ' .. per[k.id] end
    end
    local line = concat(parts, ', ')
    if line ~= last_kinds then last_kinds = line; chef.log('structures: units by kind: %s', line ~= '' and line or 'none') end
  end
  -- an empty list while marks still have members: not believed (the way out of a mission, a scan cut short)
  if #items == 0 then
    for _, m in ipairs(O.marks) do
      if m.n > 0 then
        if not empty_noted then empty_noted = true; chef.log('structures: an empty unit list ignored, marks kept') end
        return
      end
    end
  end
  gone = {}

  -- the groups: greedy, each unit joins the nearest group of its key within the kind's JOIN, at the running centroid
  local fresh, swaps = {}, {}
  for i = 1, #items do
    local it = items[i]
    if swap_of[it.kind] then swaps[#swaps + 1] = it end
    local k = K.by_unit[it.kind]
    if k and used[k.id] and not dropped[k.id] then
      local g, r = group_of(k), JOIN[k.cat] or 25
      local c, best = nil, r * r
      for _, f in ipairs(fresh) do
        if f.group == g then
          local d = (f.x - it.x) ^ 2 + (f.y - it.y) ^ 2
          if d <= best then c, best = f, d end
        end
      end
      local z = it.z or 0
      if c then
        local n = c.n + 1
        c.x, c.y, c.z = c.x + (it.x - c.x) / n, c.y + (it.y - c.y) / n, c.z + (z - c.z) / n
        c.n = n
        c.units[n], c.ukind[n], c.px[n], c.py[n] = it.unit, k, it.x, it.y
        if (NEST_SIZE[k.id] or 0) > (NEST_SIZE[c.kind.id] or 0) then c.kind = k end
      else
        fresh[#fresh + 1] = { group = g, kind = k, x = it.x, y = it.y, z = z, n = 1, units = { it.unit }, ukind = { k },
                              px = { it.x }, py = { it.y } }
      end
    end
  end

  -- each group takes over the nearest old mark of its key within JOIN (the same table), or makes a new one
  local old, taken, list = O.marks, {}, {}
  for _, c in ipairs(fresh) do
    local r = JOIN[c.kind.cat] or 25
    local m, best = nil, r * r
    for _, o in ipairs(old) do
      if not taken[o] and o.group == c.group then
        local d = (o.x - c.x) ^ 2 + (o.y - c.y) ^ 2
        if d <= best then m, best = o, d end
      end
    end
    if m then
      taken[m] = true
      m.kind, m.x, m.y, m.z, m.n, m.units, m.ukind = c.kind, c.x, c.y, c.z, c.n, c.units, c.ukind
      if m.state == 'done' and m.why == 'gone' and not m.manual then
        m.state, m.why = 'unknown', nil
        chef.log('structures: %s%s is back in the list', m.label, where(m))
      end
    else
      m = { kind = c.kind, group = c.group, x = c.x, y = c.y, z = c.z, n = c.n, units = c.units, ukind = c.ukind,
            gone_t = nil, state = 'unknown', size = 0 }
    end
    -- holes (units HOLE m apart) and how far the members spread
    local holes, spread = 0, 0
    local px, py = c.px, c.py
    for i = 1, c.n do
      local alone = true
      for j = 1, i - 1 do
        if (px[i] - px[j]) ^ 2 + (py[i] - py[j]) ^ 2 <= HOLE * HOLE then alone = false; break end
      end
      if alone then holes = holes + 1 end
      local d = (px[i] - c.x) ^ 2 + (py[i] - c.y) ^ 2
      if d > spread then spread = d end
    end
    m.holes, m.size, m.spread, m.seen = holes, max(m.size or 0, holes), sqrt(spread), max(m.seen or 0, c.n)
    m.label = label_of(m)
    list[#list + 1] = m
  end
  -- the old marks no group took: every member is gone (done), or their kind was dropped (removed)
  for _, o in ipairs(old) do
    if not taken[o] and not dropped[o.kind.id] then
      if o.state ~= 'done' and not o.manual then set_done(o, 'gone') end
      o.n, o.units, o.ukind = 0, {}, {}
      list[#list + 1] = o
    end
  end

  -- a swap unit (the destroyed variant) near a mark of the kind it replaces
  for _, it in ipairs(swaps) do
    for _, k in ipairs(swap_of[it.kind]) do
      for _, m in ipairs(list) do
        if m.kind == k and not m.manual and (m.state ~= 'done' or m.why == 'gone') then
          local r = SWAP_REACH + (m.spread or 0)
          if (m.x - it.x) ^ 2 + (m.y - it.y) ^ 2 <= r * r then
            if m.state == 'done' then m.why = 'swap' else set_done(m, 'swap') end
          end
        end
      end
    end
  end

  refill(list)
  summarize()
end

-- ------------------------------------------------------------------ near me: Unit.alive, the animation hook
-- HOOK (done = 'anim:<state>'): O.anim_probe(mark, state) -> true once the mark's units show that state. Nothing here
-- asks the engine for animation states (no such call is confirmed safe); a probe build may set this function.
O.anim_probe = nil

local function check_near(S)
  if S.t < next_alive then return end
  next_alive = S.t + ALIVE_EVERY
  local mx, my, r2 = S.me.x, S.me.y, ALIVE_REACH * ALIVE_REACH
  local changed = false
  for _, m in ipairs(O.marks) do
    if m.n > 0 and (m.x - mx) ^ 2 + (m.y - my) ^ 2 <= r2 then
      local us, uk, n0 = m.units, m.ukind, m.n
      for i = 1, #us do
        local u = us[i]
        if not gone[u] then
          -- a skipped (crash-guarded) or failed call says why: only a plain "not alive" counts
          local a, why = chef.call_kind('Unit.alive', uk[i].id, u)
          if a ~= true and why == nil then
            gone[u] = true
            m.n = m.n - 1
          end
        end
      end
      if m.n ~= n0 then
        changed = true
        if m.n <= 0 then
          m.n = 0
          if m.state ~= 'done' and not m.manual then set_done(m, 'alive') end
        else
          chef.log('structures: %s%s: %d of %d units left', m.label, where(m), m.n, max(m.seen or 0, #us))
        end
      end
      local want = anim_want[m.kind.id]
      if want and O.anim_probe and m.n > 0 and m.state ~= 'done' and not m.manual then
        local ok, hit = pcall(O.anim_probe, m, want)
        if ok and hit == true then set_done(m, 'anim'); changed = true end
      end
    end
  end
  if changed then refill(O.marks); summarize() end
end

-- ------------------------------------------------------------------ the manual key
local function manual(S)
  local best, bdot, bd = nil, MANUAL_CONE, nil
  for _, m in ipairs(O.marks) do
    local dx, dy = m.x - S.me.x, m.y - S.me.y
    local d = sqrt(dx * dx + dy * dy)
    if d <= MANUAL_REACH then
      local dot = d < 3 and 1 or (dx * S.fx + dy * S.fy) / d
      if dot >= bdot and (best == nil or dot > bdot + 1e-3 or d < bd) then best, bdot, bd = m, dot, d end
    end
  end
  local key = upper(MANUAL_KEY or 'manual')
  if not best then
    chef.log('structures: %s: no mark in view within %d m', key, MANUAL_REACH)
    return
  end
  best.manual = true
  if best.state == 'done' then best.state, best.why = 'unknown', nil
  else best.state, best.why = 'done', 'manual' end
  chef.log('structures: %s marked %s %d m %s', key, best.label, bd + 0.5, best.state == 'done' and 'done' or 'not done')
  refill(O.marks)
  summarize()
end

-- ------------------------------------------------------------------ exports
-- the list runs while the map is closed and not hidden, for the radar or (0.9.3: mode no_radar / map_only) the open
-- map's overlay and legend, which draw the marks it kept
function O.wants(S)
  S = S or last_S
  if not S then return false end
  return (C.RADAR == true or C.OVERLAY == true or C.LEGEND ~= false) and not S.hidden and not S.map_open
end

-- a view or tool sets a mark's state by hand ('active' | 'done' | 'unknown'); automatic changes leave it alone then
function O.set_state(mark, state)
  if type(mark) ~= 'table' or (state ~= 'active' and state ~= 'done' and state ~= 'unknown') then return false end
  if mark.state ~= state then
    mark.state, mark.why, mark.manual = state, state == 'done' and 'set' or nil, true
    chef.log('structures: %s set %s', tostring(mark.label), state)
    refill(O.marks)
    summarize()
  end
  return true
end

-- the nearest mark to a point (2D) within radius (any distance if nil) -> mark, distance
function O.nearest(x, y, radius)
  local best, bd = nil, radius and radius * radius or math.huge
  for _, m in ipairs(O.marks) do
    local d = (m.x - x) ^ 2 + (m.y - y) ^ 2
    if d <= bd then best, bd = m, d end
  end
  return best, best and sqrt(bd) or nil
end

-- the overlay a done mark wears: a cross on what was destroyed (nests, structures), a check on the rest
function O.done_tex(mark)
  local cat = mark and mark.kind and mark.kind.cat
  return (cat == 'nest' or cat == 'structure') and 'map/cross' or 'map/done'
end

-- ------------------------------------------------------------------ life cycle
function O.init()
  local conf = { verified = 0, likely = 0, guess = 0 }
  for _, k in ipairs(used_list) do conf[k.conf] = (conf[k.conf] or 0) + 1 end
  chef.log('structures: %d kinds on (verified %d, likely %d, guess %d), %d unit ids; list every %d s while the map is '
    .. 'closed; %s marks the mark in view done', #used_list, conf.verified, conf.likely, conf.guess, count(watch_kinds),
    EVERY, MANUAL_KEY and upper(MANUAL_KEY) or 'no key')
  if TESTER then
    chef.log('structures: Tester build: guesses on (%d): %s', #guess_on, #guess_on > 0 and concat(guess_on, ', ') or 'none')
  else
    chef.log('structures: guesses off (Tester builds only)')
  end
end

function O.reset(S)
  for i = #O.marks, 1, -1 do O.marks[i] = nil end
  gone, dropped = {}, {}
  fill_watch()
  last_gen = watch and watch.generation or -1
  last_line, last_kinds, empty_noted, next_alive = nil, nil, false, 0
  O.state.units, O.state.counts, O.state.done, O.state.line = count(watch_kinds), {}, 0, nil
  if O.any then chef.log('structures: new mission: watching %d unit ids of %d kinds', O.state.units, #used_list) end
end

-- outside a mission the list rests (the marks stay until the next mission's reset)
function O.idle()
  if watch and watch.active then watch.pause() end
  O.state.running = false
end

-- one walk of the world's units for track and me: my next list moves onto track's nearest one (its lists come every
-- tw.every s) when that's within SYNC s, so mine come every EVERY +- SYNC s, in step with every other one of track's.
-- (watch.next is the loader's own clock, chef.time(); track.watch is exported by track.lua: without it, nothing happens)
local function sync()
  local tr = T.mod.track
  local tw = type(tr) == 'table' and tr.watch
  if type(tw) ~= 'table' or not tw.active or watch.want_now then return end
  local tn, te, mn = tw.next, tw.every, watch.next
  if type(tn) ~= 'number' or type(te) ~= 'number' or te <= 0 or type(mn) ~= 'number' then return end
  local k = floor((mn - tn) / te + 0.5)
  if k < 0 then return end
  local target = tn + k * te
  if target ~= mn and abs(target - mn) <= SYNC then watch.next = target end
end

function O.update(S)
  last_S = S
  if not O.any then return end
  if MANUAL_KEY and not S.map_open and chef.key_pressed(MANUAL_KEY) then manual(S) end
  if not O.wants(S) then
    if watch and watch.active then
      watch.pause()
      chef.log('structures: list paused (%s), %d marks kept', S.map_open and 'map open' or S.hidden and 'HUD hidden'
        or 'no view uses it', #O.marks)
    end
    O.state.running = false
    return
  end
  if not watch then
    watch = chef.watch(watch_kinds, EVERY)
  elseif not watch.active then
    watch.resume()
    chef.log('structures: list resumed')
  end
  O.state.running = true
  sync()
  if watch.generation ~= last_gen then
    last_gen = watch.generation
    rebuild(watch.items)
  end
  check_near(S)
end

return O
