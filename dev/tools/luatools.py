"""luatools: Lua 5.1 checks for the build (lupa's lua51, the same language as the game's Lua 5.1.4).

  compile_check(src, chunkname)      load without running; -> None or the compiler's error message
  loader_discover(loader_src, files) run the loader's OWN discovery code (cut out of its source) on built archives,
                                     the way the game would see them deployed as data/9ba626afa44a3aa3.patch_<N>;
                                     -> {'addons': [...], 'options': [...], 'scan': {...}, 'merged': {...}, ...}

  python -I luatools.py compile <file.lua> [...]
  python -I luatools.py discover <loader.lua> <option folder or archive> [...]   (patch_0, patch_1, ... in that order)
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '_pylib'))
sys.path.insert(0, HERE)
from lupa import lua51  # noqa: E402

DEPLOYED = 'data/9ba626afa44a3aa3.patch_%d'
_rt = None


def runtime():
    """A fresh Lua 5.1 state; strings stay bytes both ways."""
    rt = lua51.LuaRuntime(encoding=None, unpack_returned_tuples=True)
    v = rt.eval('_VERSION')
    if v != b'Lua 5.1':
        raise RuntimeError('lupa runtime is %r, not Lua 5.1' % v)
    return rt


def _shared():
    global _rt
    if _rt is None:
        _rt = runtime()
    return _rt


def compile_check(src, chunkname='chunk'):
    """Compile Lua source (bytes or str) with Lua 5.1's loadstring, without running it.
    -> None when it compiles, else the error message (str)."""
    if isinstance(src, str):
        src = src.encode('utf-8')
    if src.startswith(b'\xef\xbb\xbf'):
        return '%s: starts with a UTF-8 byte order mark (the game\'s loadstring rejects it)' % chunkname
    rt = _shared()
    f = rt.eval('function(s, n) local f, e = loadstring(s, n); if f then return true, nil end; return false, e end')
    ok, err = f(src, ('=' + chunkname).encode('utf-8'))
    if ok:
        return None
    return err.decode('utf-8', 'replace') if isinstance(err, bytes) else str(err)


def options_check(src, chunkname='options'):
    """Run an options file the way the loader does (no globals at all, under pcall); it must return a table.
    -> None or the error message."""
    if isinstance(src, str):
        src = src.encode('utf-8')
    rt = _shared()
    f = rt.eval("function(s, n) local f, e = loadstring(s, n); if not f then return false, e end; setfenv(f, {}); "
                "local ok, t = pcall(f); if not ok then return false, t end; if type(t) ~= 'table' then "
                "return false, 'returns a ' .. type(t) .. ', not a table' end; return true, nil end")
    ok, err = f(src, ('=' + chunkname).encode('utf-8'))
    if ok:
        return None
    return err.decode('utf-8', 'replace') if isinstance(err, bytes) else str(err)


def section(loader_src, start_re, end_re):
    """Lines of the loader from the line matching start_re up to (not including) the line matching end_re."""
    lines = loader_src.split(b'\n')
    s = next((i for i, l in enumerate(lines) if re.match(start_re, l)), None)
    if s is None:
        raise ValueError('loader: no line matches %r' % start_re)
    e = next((i for i in range(s + 1, len(lines)) if re.match(end_re, lines[i])), None)
    if e is None:
        raise ValueError('loader: no line matches %r after line %d' % (end_re, s + 1))
    return b'\n'.join(lines[s:e]) + b'\n'


def function_text(loader_src, name):
    """The text of a top-level `local function <name>(...)` of the loader (up to its closing 'end' line)."""
    lines = loader_src.split(b'\n')
    s = next((i for i, l in enumerate(lines) if l.startswith(b'local function ' + name + b'(')), None)
    if s is None:
        return None
    e = next((i for i in range(s + 1, len(lines)) if lines[i] == b'end'), None)
    return None if e is None else b'\n'.join(lines[s:e + 1]) + b'\n'


_OPTIONS_FOR = b'''local function options_for(name)
  local o = {}
  for _, r in ipairs(found_options) do
    if r.name == name then
      local chunk = loadstring(r.src, '@' .. r.name .. ' (options in ' .. r.file .. ')')
      local ok, t = false, nil
      if chunk then setfenv(chunk, {}); ok, t = pcall(chunk) end
      if ok and type(t) == 'table' then
        for k, v in pairs(t) do
          if type(v) == 'table' and type(o[k]) == 'table' then for k2, v2 in pairs(v) do o[k][k2] = v2 end
          else o[k] = v end
        end
      else
        log('options for ' .. name .. ' in ' .. r.file .. ' could not be read')
      end
    end
  end
  return o
end
'''


def loader_discover(loader_src, archives):
    """Run the loader's discovery on archives deployed as data/9ba626afa44a3aa3.patch_0, _1, ... (in list order).

    `archives`: main-file paths (or None for a gap: that patch number is missing). The discovery section of the
    loader (from its '-- --- discovery' line up to 'local function fingerprint') runs unchanged under Lua 5.1, with
    `open` serving only those files; then, like start_addons(), every addon found is compiled with
    loadstring(src, '@' .. name) and its options are merged with the loader's own options_for().
    """
    if isinstance(loader_src, str):
        loader_src = loader_src.encode('utf-8')
    disc = section(loader_src, rb'^-- -+ discovery\s*$', rb'^local function fingerprint\(')
    m = re.search(rb"^local ALLOW = .*$", loader_src, re.M)
    if not m:
        raise ValueError('loader: no "local ALLOW = ..." line')
    allow_line = m.group(0)
    opts_fn = function_text(loader_src, b'options_for') or _OPTIONS_FOR
    pre = b'''local FILES, LOGS = ...
local pairs, ipairs, pcall, type, tostring, tonumber, select = pairs, ipairs, pcall, type, tostring, tonumber, select
local fmt, concat, sort, sqrt, min, max, floor = string.format, table.concat, table.sort, math.sqrt, math.min, math.max, math.floor
local byte, sub = string.byte, string.sub
local clock = os.clock
local function log(text) LOGS[#LOGS + 1] = tostring(text) end
local function open(path, mode)
  local real = FILES[path]
  if not real then return nil end
  local ok, f = pcall(io.open, real, mode)
  if ok then return f end
end
''' + allow_line + b'\n'
    post = b'''
discover()
local compiled = {}
local merged = {}
local seen = {}
for i, r in ipairs(found_addons) do
  local chunk, err = loadstring(r.src, '@' .. r.name)
  compiled[i] = chunk and true or tostring(err)
  if not seen[r.name] then seen[r.name] = true; merged[r.name] = options_for(r.name) end
end
return found_addons, found_options, scan, compiled, merged
'''
    chunk_src = pre + disc + opts_fn + post
    rt = runtime()
    load = rt.eval('function(s) local f, e = loadstring(s, "=loader discovery"); return f, e end')
    fn, err = load(chunk_src)
    if fn is None:
        raise RuntimeError('the loader discovery section does not compile: %s' % err)
    files = rt.table()
    names = []
    for n, p in enumerate(archives):
        if p is not None:
            files[(DEPLOYED % n).encode()] = os.path.abspath(p).encode('utf-8')
            names.append(DEPLOYED % n)
    logs = rt.table()
    found_addons, found_options, scan, compiled, merged = fn(files, logs)

    def rows(t):
        out = []
        for i in range(1, len(t) + 1):
            r = t[i]
            out.append({'name': r[b'name'].decode(), 'file': r[b'file'].decode(), 'src': bytes(r[b'src'])})
        return out
    addons = rows(found_addons)
    for i, a in enumerate(addons):
        c = compiled[i + 1]
        a['compiles'] = c is True
        if c is not True:
            a['error'] = c.decode('utf-8', 'replace')
    return {
        'addons': addons,
        'options': rows(found_options),
        'scan': {k.decode(): scan[k] for k in (b'files', b'bad', b'ms')},
        'merged': {k.decode(): to_py(v) for k, v in merged.items()},
        'log': [logs[i].decode('utf-8', 'replace') for i in range(1, len(logs) + 1)],
        'deployed': names,
    }


def to_py(v):
    """A Lua value from lupa -> plain Python (tables become dicts; keys are str when they were strings)."""
    if isinstance(v, bytes):
        return v.decode('utf-8', 'replace')
    if v is None or isinstance(v, (bool, int, float)):
        return v
    try:
        items = list(v.items())
    except AttributeError:
        return repr(v)
    return {(k.decode() if isinstance(k, bytes) else k): to_py(x) for k, x in items}


def _main(argv):
    if len(argv) >= 2 and argv[0] == 'compile':
        bad = 0
        for p in argv[1:]:
            with open(p, 'rb') as f:
                err = compile_check(f.read(), os.path.basename(p))
            print('ok   %s' % p if err is None else 'FAIL %s' % err)
            bad += err is not None
        return 1 if bad else 0
    if len(argv) >= 3 and argv[0] == 'discover':
        import patchlib as pl
        with open(argv[1], 'rb') as f:
            loader = f.read()
        paths = []
        for p in argv[2:]:
            paths.append(os.path.join(p, pl.ARCHIVE_NAME) if os.path.isdir(p) else p)
        r = loader_discover(loader, paths)
        print('scan: %r' % r['scan'])
        for a in r['addons']:
            print('addon   %-40s %s  %d bytes  %s' % (a['name'], a['file'], len(a['src']),
                                                       'compiles' if a['compiles'] else 'ERROR ' + a['error']))
        for o in r['options']:
            print('options %-40s %s  %r' % (o['name'], o['file'], o['src'].split(b'\n')[2:3]))
        for k, v in r['merged'].items():
            print('merged options for %s: %r' % (k, v))
        for line in r['log']:
            print('log: ' + line)
        return 0
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(_main(sys.argv[1:]))
