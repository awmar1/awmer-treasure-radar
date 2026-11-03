"""bundle: build the addon's one Lua resource from the module files in modules.txt.

  python -I bundle.py --version 0.6.0 [--modules dev/src/addon/modules.txt] [--textures dev/src/textures]
                      [--out dev/build/bundle/treasure_radar.lua] [--mod mods/chef/treasure_radar]
                      [--title "Treasure Radar"] [--prefix treasure_radar/] [--strict]
  python -I bundle.py --where <bundle line> [<bundle>.map.txt]     which module file and line a bundle line is

Output (exactly this shape):

  -- HD2-Addon: mods/chef/treasure_radar
  -- Treasure Radar <version> (built from N modules)
  local chef = ...
  local T = { chef = chef, mod = {}, version = '<version>', TEX = {} }
  T.TEX['<texture name>'] = '<16 hex id>'          one line per PNG under the textures folder, sorted by name
  T.mod['<module>'] = (function(...)
  <module file, verbatim>
  end)(T, chef)
  ...                                               one block per module, in modules.txt order
  return T.mod['main']

and <out without .lua>.map.txt: which bundle lines come from which module file lines. The game reports errors
against bundle lines ('mods/chef/treasure_radar:123: ...'); `--where 123` turns that into 'hud.lua:45'.

Texture names: the PNG's path under the textures folder, '/'-separated, without '.png' ('icons/medal').
Texture ids: murmur64a('<prefix><name>') with prefix 'treasure_radar/' (so 'treasure_radar/icons/medal'), checked
against every id of the shipped 0.5.1 archives and the loader's id (never equal) and against each other.

modules.txt: one module per line, the file name relative to modules.txt with or without '.lua'; '#' starts a comment
line. The module's name is that path without '.lua'. A listed file that doesn't exist is skipped with a warning
(--strict: an error); 'main' must exist; a .lua file under modules.txt's folder that is not listed is a warning.
Every module and the whole bundle must compile under Lua 5.1 (lupa lua51), else nothing is written and the exit
code is 1.
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import patchlib as pl  # noqa: E402
import luatools  # noqa: E402

DEV = os.path.dirname(HERE)
MOD_ROOT = os.path.dirname(DEV)
DEFAULT_MODULES = os.path.join(DEV, 'src', 'addon', 'modules.txt')
DEFAULT_TEXTURES = os.path.join(DEV, 'src', 'textures')
DEFAULT_OUT = os.path.join(DEV, 'build', 'bundle', 'treasure_radar.lua')
DEFAULT_MOD = 'mods/chef/treasure_radar'
DEFAULT_PREFIX = 'treasure_radar/'
REFERENCE_INDEX = os.path.join(DEV, 'reference', '0.5.1', 'resources', 'index.json')
MAX_LUA = 4 * 1024 * 1024 - 8          # the loader skips Lua resources over 4 MiB

NAME_RE = re.compile(r'^[A-Za-z0-9_.\-]+(/[A-Za-z0-9_.\-]+)*$')
VERSION_RE = re.compile(r'^[A-Za-z0-9_.+\-]+$')
MODPATH_RE = re.compile(r'^[A-Za-z0-9_/.\-]+$')    # what the loader's header pattern [%w_/%.%-]+ takes


class BundleError(Exception):
    pass


def reserved_ids(extra_roots=()):
    """Ids a new texture must never take: every resource id shipped in 0.5.1 (from the extracted index and from the
    mod folder's option archives) and the loader's id."""
    ids = {pl.LOADER_ID, pl.TYPE_LUA, pl.TYPE_TEXTURE}
    if os.path.isfile(REFERENCE_INDEX):
        with open(REFERENCE_INDEX, encoding='utf-8') as f:
            idx = json.load(f)
        for o in idx['options'].values():
            for r in o['resources']:
                ids.add(int(r['id'], 16))
    for root in (MOD_ROOT,) + tuple(extra_roots):
        if not os.path.isdir(root):
            continue
        for d in sorted(os.listdir(root)):
            p = os.path.join(root, d, pl.ARCHIVE_NAME)
            if d != 'dev' and os.path.isfile(p):
                for r in pl.Archive.read(p).resources:
                    ids.add(r.id)
    return ids


def read_modules(modules_txt):
    """-> [(module name, absolute path)] in file order."""
    base = os.path.dirname(os.path.abspath(modules_txt))
    out, seen = [], set()
    with open(modules_txt, encoding='utf-8') as f:
        for n, line in enumerate(f, 1):
            s = line.strip()
            if not s or s.startswith('#'):
                continue
            name = s[:-4] if s.endswith('.lua') else s
            name = name.replace('\\', '/')
            if not NAME_RE.match(name) or '..' in name.split('/'):
                raise BundleError('%s:%d: bad module name %r' % (modules_txt, n, s))
            if name in seen:
                raise BundleError('%s:%d: module %r listed twice' % (modules_txt, n, name))
            seen.add(name)
            out.append((name, os.path.join(base, *name.split('/')) + '.lua'))
    return out


def find_textures(tex_dir):
    """-> sorted [(name, absolute path)] of the PNGs under tex_dir."""
    out, warnings = [], []
    if not tex_dir or not os.path.isdir(tex_dir):
        return out, warnings
    for root, dirs, files in os.walk(tex_dir):
        dirs.sort()
        for fn in files:
            p = os.path.join(root, fn)
            rel = os.path.relpath(p, tex_dir).replace(os.sep, '/')
            if not fn.endswith('.png'):
                if fn.lower().endswith('.png'):
                    warnings.append('%s: extension must be lower-case .png; ignored' % rel)
                continue
            name = rel[:-4]
            if not NAME_RE.match(name):
                raise BundleError('texture %r: names may only use A-Z a-z 0-9 _ . - and /' % rel)
            out.append((name, p))
    out.sort()
    return out, warnings


def texture_id(name, prefix=DEFAULT_PREFIX):
    return pl.resource_id(prefix + name)


class Bundle:
    def __init__(self):
        self.text = b''
        self.map_lines = []
        self.modules = []        # (name, path, first bundle line, last bundle line, file lines)
        self.textures = []       # (name, id, path)
        self.warnings = []
        self.errors = []


def make_bundle(version, modules_txt=DEFAULT_MODULES, textures_dir=DEFAULT_TEXTURES, mod=DEFAULT_MOD,
                title='Treasure Radar', prefix=DEFAULT_PREFIX, reserved=None, strict=False, textures=None):
    """Build the bundle in memory (nothing written). `textures`: [(name, path)] to use instead of scanning
    textures_dir. -> Bundle (check .errors)."""
    b = Bundle()
    if not VERSION_RE.match(version or ''):
        raise BundleError('bad version %r' % version)
    if not MODPATH_RE.match(mod):
        raise BundleError('bad mod path %r (the loader only reads [A-Za-z0-9_/.-])' % mod)
    if "'" in title or '\n' in title or '\\' in title:
        raise BundleError('bad title %r' % title)
    mods = read_modules(modules_txt)
    present = []
    for name, path in mods:
        if os.path.isfile(path):
            present.append((name, path))
        elif strict:
            b.errors.append('module %s: %s does not exist' % (name, path))
        else:
            b.warnings.append('module %s: %s does not exist; skipped' % (name, path))
    if 'main' not in [n for n, _ in present]:
        b.errors.append("no module 'main' (the bundle returns T.mod['main'])")
    base = os.path.dirname(os.path.abspath(modules_txt))
    listed = {os.path.normcase(os.path.abspath(p)) for _, p in mods}
    for root, dirs, files in os.walk(base):
        dirs.sort()
        for fn in sorted(files):
            p = os.path.join(root, fn)
            if fn.endswith('.lua') and os.path.normcase(os.path.abspath(p)) not in listed:
                b.warnings.append('%s is not listed in modules.txt; not bundled'
                                  % os.path.relpath(p, base).replace(os.sep, '/'))
    if textures is None:
        textures, tw = find_textures(textures_dir)
        b.warnings += tw
    reserved = reserved_ids() if reserved is None else reserved
    by_id = {}
    for name, path in textures:
        tid = texture_id(name, prefix)
        if tid in reserved:
            b.errors.append('texture %s: id %016x (of %r) is reserved (a 0.5.1 or loader id)' % (name, tid, prefix + name))
        if tid in by_id:
            b.errors.append('textures %s and %s have the same id %016x' % (by_id[tid], name, tid))
        by_id[tid] = name
        b.textures.append((name, tid, path))

    lines = []        # bundle lines (bytes, no newline)
    mp = []           # map rows: (b1, b2, what, f1, f2)

    def gen(text, what):
        lines.append(text)
        mp.append((len(lines), len(lines), what, None, None))

    gen(b'-- HD2-Addon: ' + mod.encode(), '(header)')
    gen(('-- %s %s (built from %d modules)' % (title, version, len(present))).encode('utf-8'), '(header)')
    gen(b'local chef = ...', '(header)')
    gen(("local T = { chef = chef, mod = {}, version = '%s', TEX = {} }" % version).encode(), '(header)')
    for name, tid, _ in b.textures:
        gen(("T.TEX['%s'] = '%016x'" % (name, tid)).encode(), '(texture ids)')
    for name, path in present:
        with open(path, 'rb') as f:
            src = f.read()
        rel = os.path.relpath(path, os.path.dirname(os.path.abspath(modules_txt))).replace(os.sep, '/')
        if src.startswith(b'\xef\xbb\xbf'):
            b.errors.append('%s: starts with a UTF-8 byte order mark; save it without one' % rel)
            continue
        err = luatools.compile_check(src, rel)
        if err:
            b.errors.append(err)
        if b'\r' in src:
            b.warnings.append('%s: has CR characters (CRLF line ends?); the bundle keeps them' % rel)
        first = src.split(b'\n', 1)[0].rstrip(b'\r')
        if first.strip() != b'local T, chef = ...':
            b.warnings.append("%s: first line is not 'local T, chef = ...'" % rel)
        body = src.split(b'\n')
        if body and body[-1] == b'':
            body.pop()               # the file ended with a newline
        gen(("T.mod['%s'] = (function(...)" % name).encode(), '(wrapper) ' + name)
        start = len(lines) + 1
        lines.extend(body)
        if body:
            mp.append((start, len(lines), rel, 1, len(body)))
        b.modules.append((name, path, start, len(lines), len(body)))
        gen(b'end)(T, chef)', '(wrapper) ' + name)
    gen(b"return T.mod['main']", '(footer)')
    b.text = b'\n'.join(lines) + b'\n'
    if len(b.text) > MAX_LUA:
        b.errors.append('bundle is %d bytes; the loader skips Lua resources over 4 MiB' % len(b.text))
    if not b.errors:
        err = luatools.compile_check(b.text, mod)
        if err:
            b.errors.append('bundle: ' + err)
    # merge consecutive generated rows of the same kind
    merged = []
    for row in mp:
        if merged and row[3] is None and merged[-1][3] is None and merged[-1][2] == row[2] and merged[-1][1] + 1 == row[0]:
            merged[-1] = (merged[-1][0], row[1], row[2], None, None)
        else:
            merged.append(row)
    b.map_lines = ['# %s %s bundle (%s): bundle lines -> source lines, 1-based, inclusive' % (title, version, mod),
                   '# module files are relative to %s' % os.path.dirname(os.path.abspath(modules_txt)).replace(os.sep, '/'),
                   '# bundle\tfile\tfile lines']
    for b1, b2, what, f1, f2 in merged:
        b.map_lines.append('%d-%d\t%s\t%s' % (b1, b2, what, '-' if f1 is None else '%d-%d' % (f1, f2)))
    return b


def write_bundle(b, out):
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, 'wb') as f:
        f.write(b.text)
    mpath = map_path(out)
    with open(mpath, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(b.map_lines) + '\n')
    return mpath


def map_path(out):
    return (out[:-4] if out.endswith('.lua') else out) + '.map.txt'


def where(line, map_file):
    """Bundle line -> 'file:line' (or what generated it)."""
    with open(map_file, encoding='utf-8') as f:
        for row in f:
            if row.startswith('#') or not row.strip():
                continue
            rng, what, frng = row.rstrip('\n').split('\t')
            b1, b2 = map(int, rng.split('-'))
            if b1 <= line <= b2:
                if frng == '-':
                    return 'line %d is generated: %s' % (line, what)
                f1 = int(frng.split('-')[0])
                return '%s:%d' % (what, f1 + line - b1)
    return 'line %d is past the end of the bundle' % line


def main(argv):
    ap = argparse.ArgumentParser(description='Bundle the addon modules into one Lua resource.')
    ap.add_argument('--version')
    ap.add_argument('--modules', default=DEFAULT_MODULES)
    ap.add_argument('--textures', default=DEFAULT_TEXTURES)
    ap.add_argument('--out', default=DEFAULT_OUT)
    ap.add_argument('--mod', default=DEFAULT_MOD)
    ap.add_argument('--title', default='Treasure Radar')
    ap.add_argument('--prefix', default=DEFAULT_PREFIX)
    ap.add_argument('--strict', action='store_true', help='a module listed in modules.txt but missing is an error')
    ap.add_argument('--where', type=int, metavar='LINE')
    ap.add_argument('map', nargs='?')
    a = ap.parse_args(argv)
    if a.where is not None:
        print(where(a.where, a.map or map_path(a.out)))
        return 0
    if not a.version:
        ap.error('--version is required')
    try:
        b = make_bundle(a.version, a.modules, a.textures, a.mod, a.title, a.prefix, strict=a.strict)
    except BundleError as e:
        print('error: %s' % e)
        return 1
    for w in b.warnings:
        print('warning: %s' % w)
    for e in b.errors:
        print('error: %s' % e)
    if b.errors:
        print('bundle NOT written (%d errors)' % len(b.errors))
        return 1
    mpath = write_bundle(b, a.out)
    print('wrote %s (%d bytes, %d lines, %d modules, %d textures) and %s'
          % (a.out, len(b.text), b.text.count(b'\n'), len(b.modules), len(b.textures), mpath))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
