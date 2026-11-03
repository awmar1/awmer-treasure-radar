"""build: package Treasure Radar from a JSON build description.

  python -I build.py <build.json> [--out DIR] [--force] [--no-discovery]

Writes <out> (default dev/build/Treasure-Radar-<version>): manifest.json, the copied files (images/,
thumbnail.png) and one folder per option holding its patch archive (9ba626afa44a3aa3.patch_0, .gpu_resources,
.stream). Next to it, <out>.meta/: the bundles and their line maps, ids.json (every resource: folder, kind, name,
id, sizes) and discovery.txt (what the loader's own discovery code finds in the build).

The build fails (exit 1, and <out> is left incomplete or absent) on: a Lua file that doesn't compile under Lua 5.1,
an options file that doesn't return a table when run the loader's way, a duplicate id, a texture id that equals a
0.5.1 id (unless "allow_reserved_ids"), a manifest Include or Image that doesn't exist, or an addon/options resource
the loader's discovery doesn't find. See README.md for the JSON schema; builds/0.5.1.json is a complete example.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import patchlib as pl  # noqa: E402
import tex  # noqa: E402
import luatools  # noqa: E402
import bundle as bundlemod  # noqa: E402

SCHEMA = 'treasure-radar-build/1'
DEV = os.path.dirname(HERE)
MOD_ROOT = os.path.dirname(DEV)
BUILD_ROOT = os.path.join(DEV, 'build')
REFERENCE_LOADER = os.path.join(DEV, 'reference', '0.5.1', 'loader.lua')
HEADER_RE = re.compile(rb'^-- HD2-([A-Za-z]+): ([A-Za-z0-9_/.\-]+)')     # the loader's '^%-%- HD2%-(%a+): ([%w_/%.%-]+)'
FOLDER_RE = re.compile(r'^[A-Za-z0-9_.\-]+$')

KEYS = {
    'loader': {'file', 'text', 'set', 'replace'},
    'bundle': {'modules', 'textures', 'texture_prefix', 'name', 'title', 'include_textures', 'strict', 'set', 'replace'},
    'addon': {'file', 'text', 'name', 'set', 'replace'},
    'lua': {'file', 'text', 'name', 'set', 'replace'},
    'options': {'value', 'text', 'file', 'for', 'name'},
    'texture': {'png', 'name', 'id', 'dxgi'},
    'textures': {'dir', 'prefix', 'dxgi'},
    'raw': {'type', 'name', 'id', 'main', 'gpu', 'stream'},
}
TOP_KEYS = {'schema', 'version', 'mod', 'title', 'out', 'manifest', 'files', 'options', 'allow_reserved_ids',
            'comment', '//'}


class BuildError(Exception):
    pass


def lua_quote(v):
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, (int, float)):
        return repr(v)
    s = str(v)
    return "'" + s.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n').replace('\r', '\\r') + "'"


def apply_set(text, sets, where):
    """Marker lines: 'local X = <anything>  --@@KEY@@' -> 'local X = <Lua literal of the value>  --@@KEY@@'."""
    for key, value in (sets or {}).items():
        pat = re.compile(rb'^(local [A-Za-z_][A-Za-z0-9_]* = ).*?(\s*--@@' + re.escape(key.encode()) + rb'@@)[ \t]*$', re.M)
        found = pat.findall(text)
        if len(found) != 1:
            raise BuildError('%s: "set" %s: expected one line ending in --@@%s@@, found %d' % (where, key, key, len(found)))
        lit = lua_quote(value).encode('utf-8')
        text = pat.sub(lambda m: m.group(1) + lit + m.group(2), text)
    return text


def apply_replace(text, pairs, where):
    for p in pairs or []:
        if not isinstance(p, list) or len(p) not in (2, 3):
            raise BuildError('%s: "replace" items are [old, new] or [old, new, count]' % where)
        old, new = p[0].encode('utf-8'), p[1].encode('utf-8')
        n = text.count(old)
        if n == 0 or (len(p) == 3 and n != p[2]):
            raise BuildError('%s: "replace" %r occurs %d times%s' % (where, p[0], n, '' if len(p) == 2 else ', expected %d' % p[2]))
        text = text.replace(old, new)
    return text


def sha(b):
    return hashlib.sha256(b).hexdigest()


class Builder:
    def __init__(self, desc_path, out=None, force=False, log=print):
        self.desc_path = os.path.abspath(desc_path)
        self.dir = os.path.dirname(self.desc_path)
        with open(self.desc_path, encoding='utf-8') as f:
            self.desc = json.load(f)
        self.log = log
        self.force = force
        d = self.desc
        if d.get('schema') != SCHEMA:
            raise BuildError('"schema" must be "%s"' % SCHEMA)
        unknown = set(d) - TOP_KEYS
        if unknown:
            raise BuildError('unknown top-level keys: %s' % ', '.join(sorted(unknown)))
        self.version = d.get('version')
        if not self.version or not bundlemod.VERSION_RE.match(self.version):
            raise BuildError('"version" is required (letters, digits, . _ + -)')
        self.mod = d.get('mod', bundlemod.DEFAULT_MOD)
        self.title = d.get('title', 'Treasure Radar')
        o = out or (self.path(self.s(d['out'])) if d.get('out') else os.path.join(BUILD_ROOT, 'Treasure-Radar-' + self.version))
        self.out = os.path.abspath(o)
        self.meta = self.out + '.meta'
        self.allow_reserved = bool(d.get('allow_reserved_ids', False))
        self.reserved = bundlemod.reserved_ids()
        self.archives = {}       # folder -> Archive
        self.rows = []           # one per resource: dict for ids.json
        self.loaders = []        # (folder, text)
        self.bundles = []        # (folder, name, Bundle)
        self.warnings = []

    # ------------------------------------------------------------------ helpers
    def s(self, v):
        """{version}, {mod} and {title} in a string of the description."""
        if isinstance(v, str):
            return v.replace('{version}', self.version).replace('{mod}', self.mod).replace('{title}', self.title)
        if isinstance(v, list):
            return [self.s(x) for x in v]
        if isinstance(v, dict):
            return {k: self.s(x) for k, x in v.items()}
        return v

    def path(self, p):
        return os.path.normpath(os.path.join(self.dir, p))

    def read(self, p):
        with open(self.path(p), 'rb') as f:
            return f.read()

    def warn(self, msg):
        self.warnings.append(msg)
        self.log('warning: ' + msg)

    def text_of(self, r, where):
        if ('file' in r) == ('text' in r):
            raise BuildError('%s: give "file" or "text"' % where)
        text = self.read(self.s(r['file'])) if 'file' in r else self.s(r['text']).encode('utf-8')
        text = apply_set(text, self.s(r.get('set')), where)
        text = apply_replace(text, self.s(r.get('replace')), where)
        if text.startswith(b'\xef\xbb\xbf'):
            raise BuildError('%s: starts with a UTF-8 byte order mark' % where)
        return text

    def compile(self, text, chunk, where):
        err = luatools.compile_check(text, chunk)
        if err:
            raise BuildError('%s: does not compile: %s' % (where, err))

    def header(self, text):
        m = HEADER_RE.match(text[:112])
        return (m.group(1).decode(), m.group(2).decode()) if m else (None, None)

    def add(self, folder, res, kind, name, src=None, extra=None):
        a = self.archives[folder]
        a.add(res)
        row = {'folder': folder, 'kind': kind, 'type': pl.type_name(res.type), 'id': pl.hexid(res.id), 'name': name,
               'size': len(res.data), 'gpu_size': len(res.gpu), 'stream_size': len(res.stream)}
        if src:
            row['source'] = os.path.relpath(src, self.dir).replace(os.sep, '/') if os.path.isabs(src) else src
        if extra:
            row.update(extra)
        self.rows.append(row)

    def lua_res(self, folder, kind, name, text, rid=None, src=None, extra=None):
        rid = pl.resource_id(name) if rid is None else rid
        self.add(folder, pl.Resource(rid, pl.TYPE_LUA, pl.lua_body(text)), kind, name, src, extra)

    def texture_res(self, folder, kind, png, name=None, rid=None, dxgi=tex.DXGI_RGBA8, check_reserved=True):
        if rid is None:
            rid = pl.resource_id(name)
        if check_reserved and not self.allow_reserved and rid in self.reserved:
            raise BuildError('%s: texture %s id %016x is a 0.5.1 or loader id (set "allow_reserved_ids" only to '
                             'rebuild 0.5.1)' % (folder, name or png, rid))
        try:
            toc, gpu = tex.encode(png, dxgi)
        except tex.TextureError as e:
            raise BuildError('%s: %s: %s' % (folder, png, e))
        info = tex.parse_toc(toc)
        self.add(folder, pl.Resource(rid, pl.TYPE_TEXTURE, toc, gpu), kind, name, png,
                 {'width': info['width'], 'height': info['height']})

    # ------------------------------------------------------------------ resources
    def resource(self, folder, i, r):
        where = '%s[%d]' % (folder, i)
        if not isinstance(r, dict) or 'kind' not in r:
            raise BuildError('%s: a resource is an object with a "kind"' % where)
        kind = r['kind']
        if kind not in KEYS:
            raise BuildError('%s: unknown kind %r (%s)' % (where, kind, ', '.join(KEYS)))
        bad = set(r) - KEYS[kind] - {'kind', 'comment', '//'}
        if bad:
            raise BuildError('%s: %s takes no %s' % (where, kind, ', '.join(sorted(bad))))
        where = '%s (%s)' % (where, kind)

        if kind == 'loader':
            text = self.text_of(r, where)
            self.compile(text, 'boot', where)
            self.loaders.append((folder, text))
            self.lua_res(folder, kind, 'boot', text, pl.LOADER_ID, r.get('file'))

        elif kind == 'bundle':
            name = self.s(r.get('name', self.mod))
            mods_txt = self.path(self.s(r.get('modules', os.path.relpath(bundlemod.DEFAULT_MODULES, self.dir))))
            tdir = r.get('textures', os.path.relpath(bundlemod.DEFAULT_TEXTURES, self.dir))
            tdir = self.path(self.s(tdir)) if tdir else None
            prefix = self.s(r.get('texture_prefix', bundlemod.DEFAULT_PREFIX))
            try:
                b = bundlemod.make_bundle(self.version, mods_txt, tdir, name, self.s(r.get('title', self.title)), prefix,
                                          reserved=self.reserved, strict=r.get('strict', True))
            except bundlemod.BundleError as e:
                raise BuildError('%s: %s' % (where, e))
            for w in b.warnings:
                self.warn('%s: %s' % (where, w))
            if b.errors:
                raise BuildError('%s:\n  ' % where + '\n  '.join(b.errors))
            text = apply_set(b.text, self.s(r.get('set')), where)
            text = apply_replace(text, self.s(r.get('replace')), where)
            if text != b.text:
                self.compile(text, name, where)
                b.text = text
            self.bundles.append((folder, name, b))
            self.lua_res(folder, kind, name, b.text, None, mods_txt,
                         {'modules': [m[0] for m in b.modules], 'textures': len(b.textures)})
            if r.get('include_textures', True):
                for tname, tid, tpath in b.textures:
                    self.texture_res(folder, 'bundle texture', tpath, prefix + tname, tid)

        elif kind in ('addon', 'lua'):
            text = self.text_of(r, where)
            hk, hpath = self.header(text)
            if kind == 'addon':
                if hk != 'Addon':
                    raise BuildError('%s: an addon must start with "-- HD2-Addon: <path>"' % where)
                name = self.s(r.get('name', hpath))
            else:
                if 'name' not in r:
                    raise BuildError('%s: a lua resource needs a "name" (its id is the name\'s hash)' % where)
                name = self.s(r['name'])
            self.compile(text, name, where)
            self.lua_res(folder, kind, name, text, None, r.get('file'), {'header': hk and '%s: %s' % (hk, hpath)})

        elif kind == 'options':
            target = self.s(r.get('for', self.mod))
            forms = [k for k in ('value', 'text', 'file') if k in r]
            if len(forms) != 1:
                raise BuildError('%s: give one of "value", "text", "file"' % where)
            if 'value' in r:
                text = ('-- HD2-Options: %s\n-- %s option "%s": merged into the addon\'s options by the loader.\n'
                        'return %s\n' % (target, self.title, folder, self.s(r['value']))).encode('utf-8')
            else:
                text = self.text_of({k: r[k] for k in ('text', 'file') if k in r}, where)
            hk, hpath = self.header(text)
            if hk != 'Options' or hpath != target:
                raise BuildError('%s: an options file must start with "-- HD2-Options: %s"' % (where, target))
            name = self.s(r.get('name', '%s/options/%s' % (target, folder)))
            err = luatools.options_check(text, name)
            if err:
                raise BuildError('%s: %s' % (where, err))
            self.lua_res(folder, kind, name, text, None, r.get('file'), {'for': target})

        elif kind == 'texture':
            if ('name' in r) == ('id' in r):
                raise BuildError('%s: give "name" or "id"' % where)
            rid = pl.parse_id(r['id']) if 'id' in r else None
            self.texture_res(folder, kind, self.path(self.s(r['png'])), self.s(r.get('name')), rid,
                             r.get('dxgi', tex.DXGI_RGBA8))

        elif kind == 'textures':
            d = self.path(self.s(r['dir']))
            prefix = self.s(r.get('prefix', bundlemod.DEFAULT_PREFIX))
            found, tw = bundlemod.find_textures(d)
            for w in tw:
                self.warn('%s: %s' % (where, w))
            if not found:
                raise BuildError('%s: no PNG under %s' % (where, d))
            for tname, tpath in found:
                self.texture_res(folder, kind, tpath, prefix + tname, None, r.get('dxgi', tex.DXGI_RGBA8))

        elif kind == 'raw':
            if ('name' in r) == ('id' in r):
                raise BuildError('%s: give "name" or "id"' % where)
            rid = pl.parse_id(r['id']) if 'id' in r else pl.resource_id(self.s(r['name']))
            parts = {k: self.read(self.s(r[k])) if k in r else b'' for k in ('main', 'gpu', 'stream')}
            self.add(folder, pl.Resource(rid, pl.parse_type(r['type']), parts['main'], parts['gpu'], parts['stream']),
                     kind, self.s(r.get('name')), r.get('main'))

    # ------------------------------------------------------------------ the whole build
    def build(self, discovery=True):
        d = self.desc
        opts = d.get('options')
        if not isinstance(opts, dict) or not opts:
            raise BuildError('"options" must map option folder names to resource lists')
        for folder, spec in opts.items():
            if not FOLDER_RE.match(folder) or folder in ('images', 'dev'):
                raise BuildError('bad option folder name %r' % folder)
            archive_cfg = {}
            if isinstance(spec, dict):
                archive_cfg = spec.get('archive', {})
                spec = spec.get('resources')
            if not isinstance(spec, list) or not spec:
                raise BuildError('%s: needs a non-empty list of resources' % folder)
            a = pl.Archive()
            if 'pad_main_end' in archive_cfg:
                a.pad_main_end = archive_cfg['pad_main_end']
            if 'header_extra' in archive_cfg:
                a.header_extra = bytes.fromhex(archive_cfg['header_extra'])
            self.archives[folder] = a
            for i, r in enumerate(spec):
                try:
                    self.resource(folder, i, r)
                except (OSError, ValueError) as e:      # a missing file, a bad id, an id used twice in the folder
                    raise BuildError('%s[%d]: %s' % (folder, i, e))
        # ids: unique in the whole build
        seen = {}
        for row in self.rows:
            if row['id'] in seen:
                o = seen[row['id']]
                raise BuildError('id %s is used twice: %s %s (%s) and %s %s (%s)' % (
                    row['id'], o['folder'], o['kind'], o['name'], row['folder'], row['kind'], row['name']))
            seen[row['id']] = row
        if len(self.loaders) > 1:
            self.warn('%d option folders carry the loader (boot); only one may be deployed at a time'
                      % len(self.loaders))
        self.prepare_out()
        for folder, a in self.archives.items():
            os.makedirs(os.path.join(self.out, folder))
            main, gpu, stream = a.write(os.path.join(self.out, folder, pl.ARCHIVE_NAME))
            self.log('  %-14s %3d resources  main %7d B  gpu %9d B  stream %d B'
                     % (folder, len(a.resources), len(main), len(gpu), len(stream)))
        for dest, src in self.s(d.get('files', {})).items():
            self.copy(self.path(src), os.path.join(self.out, dest))
        self.write_manifest()
        os.makedirs(self.meta, exist_ok=True)
        for folder, name, b in self.bundles:
            stem = os.path.join(self.meta, '%s.%s' % (folder, name.replace('/', '.')))
            bundlemod.write_bundle(b, stem + '.lua')
        with open(os.path.join(self.meta, 'ids.json'), 'w', encoding='utf-8', newline='\n') as f:
            json.dump({'version': self.version, 'out': self.out, 'resources': self.rows}, f, indent=1)
            f.write('\n')
        if discovery:
            self.discovery_check()
        return self

    def prepare_out(self):
        out = self.out
        o, b, m = (os.path.normcase(os.path.abspath(x)) for x in (out, BUILD_ROOT, MOD_ROOT))
        inside_build = o.startswith(b + os.sep)
        touches_mod = o == m or m.startswith(o + os.sep) or o.startswith(m + os.sep)
        if not inside_build and (touches_mod or not self.force):
            raise BuildError('output %s is not under %s%s' % (out, BUILD_ROOT, '' if touches_mod else
                                                             ' (use --force to write elsewhere outside the mod folder)'))
        for p, marker in ((out, 'manifest.json'), (self.meta, 'ids.json')):
            if os.path.isdir(p) and os.listdir(p):
                if not inside_build and not os.path.isfile(os.path.join(p, marker)):
                    raise BuildError('%s exists and is not an earlier build; not deleting it' % p)
                shutil.rmtree(p)
        os.makedirs(out, exist_ok=True)

    def copy(self, src, dest):
        if os.path.isdir(src):
            for root, dirs, files in os.walk(src):
                dirs.sort()
                for fn in sorted(files):
                    s = os.path.join(root, fn)
                    self.copy(s, os.path.join(dest, os.path.relpath(s, src)))
        elif os.path.isfile(src):
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copyfile(src, dest)
        else:
            raise BuildError('"files": %s does not exist' % src)

    def write_manifest(self):
        m = self.desc.get('manifest')
        if not isinstance(m, dict):
            raise BuildError('"manifest" is required')
        bad = set(m) - {'template', 'set', 'options', 'add_options', 'ascii', 'comment', '//'}
        if bad:
            raise BuildError('manifest takes no %s' % ', '.join(sorted(bad)))
        obj = {}
        if 'template' in m:
            with open(self.path(self.s(m['template'])), encoding='utf-8') as f:
                obj = json.load(f)
        for k, v in self.s(m.get('set', {})).items():
            obj[k] = v
        if 'options' in m:
            obj['Options'] = self.s(m['options'])
        if 'add_options' in m:
            obj['Options'] = list(obj.get('Options', [])) + self.s(m['add_options'])
        for k in ('Guid', 'Name', 'Options'):
            if k not in obj:
                raise BuildError('manifest has no %s (give a "template" or "set" it)' % k)
        includes = []

        def walk(lst, where):
            for o in lst:
                for f in o.get('Include', []):
                    if f not in self.archives:
                        raise BuildError('manifest %s "%s" includes %r, which this build does not make' % (where, o.get('Name'), f))
                    includes.append(f)
                img = o.get('Image')
                if img and not os.path.isfile(os.path.join(self.out, img)):
                    raise BuildError('manifest %s "%s": image %s is not in the build ("files")' % (where, o.get('Name'), img))
                walk(o.get('SubOptions', []), 'sub-option')
        walk(obj['Options'], 'option')
        icon = obj.get('IconPath')
        if icon and not os.path.isfile(os.path.join(self.out, icon)):
            raise BuildError('manifest IconPath %s is not in the build ("files")' % icon)
        for f in self.archives:
            if f not in includes:
                self.warn('option folder %s is not included by any manifest option (Arsenal never deploys it)' % f)
        text = json.dumps(obj, indent=2, ensure_ascii=m.get('ascii', True))
        with open(os.path.join(self.out, 'manifest.json'), 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
        self.manifest = obj
        self.deploy_order = list(dict.fromkeys(includes + list(self.archives)))

    def discovery_check(self):
        """Deploy the build (every folder, in manifest order, as patch_0, patch_1, ...) and run the loader's own
        discovery code on it under Lua 5.1; then the same with only the loader's folder."""
        if self.loaders:
            folder, loader = self.loaders[0]
            which = 'the loader of %s' % folder
        else:
            with open(REFERENCE_LOADER, 'rb') as f:
                loader = f.read()
            which = 'the 0.5.1 reference loader (this build has none)'
        lines = ['discovery check with %s' % which]
        problems = []
        runs = [('all option folders', self.deploy_order)]
        if self.loaders:
            runs.append(('only %s' % self.loaders[0][0], [self.loaders[0][0]]))
        expect_addons = [r for r in self.rows if r['type'] == 'lua' and r['kind'] in ('bundle', 'addon')]
        expect_options = [r for r in self.rows if r['type'] == 'lua' and r['kind'] == 'options']
        for label, folders in runs:
            paths = [os.path.join(self.out, f, pl.ARCHIVE_NAME) for f in folders]
            res = luatools.loader_discover(loader, paths)
            deployed = {'9ba626afa44a3aa3.patch_%d' % n: f for n, f in enumerate(folders)}
            lines.append('-- %s deployed as patch_0..%d: %d files read, %d bad' % (label, len(folders) - 1,
                                                                                   res['scan']['files'], res['scan']['bad']))
            for a in res['addons']:
                lines.append('addon   %s in %s (%s), %d bytes, %s' % (a['name'], deployed[a['file']], a['file'],
                                                                     len(a['src']), 'compiles' if a['compiles'] else a['error']))
                if not a['compiles']:
                    problems.append('the loader cannot compile %s: %s' % (a['name'], a['error']))
            for o in res['options']:
                lines.append('options %s in %s' % (o['name'], deployed[o['file']]))
            for k, v in res['merged'].items():
                lines.append('merged options of %s: %s' % (k, json.dumps(v, sort_keys=True)))
            for line in res['log']:
                lines.append('loader log: ' + line)
                problems.append('loader log: ' + line)
            found = {(deployed[a['file']], a['src']) for a in res['addons']}
            found_o = {(deployed[o['file']], o['src']) for o in res['options']}
            for r in expect_addons:
                if r['folder'] in folders:
                    src = pl.parse_lua_body(self.archives[r['folder']].find(int(r['id'], 16)).data)[1]
                    if (r['folder'], src) not in found:
                        problems.append('the loader does not find addon %s in %s (header or ALLOW mismatch?)'
                                        % (r['name'], r['folder']))
            for r in expect_options:
                if r['folder'] in folders:
                    src = pl.parse_lua_body(self.archives[r['folder']].find(int(r['id'], 16)).data)[1]
                    if (r['folder'], src) not in found_o:
                        problems.append('the loader does not find options %s in %s' % (r['name'], r['folder']))
        self.discovery = lines
        with open(os.path.join(self.meta, 'discovery.txt'), 'w', encoding='utf-8', newline='\n') as f:
            f.write('\n'.join(lines + ['problems: %d' % len(problems)] + problems) + '\n')
        if problems:
            raise BuildError('discovery check:\n  ' + '\n  '.join(problems))
        self.log('discovery check (%s): %s' % (which, '; '.join(
            l for l in lines if l.startswith('addon') or l.startswith('--'))))


def main(argv):
    ap = argparse.ArgumentParser(description='Build Treasure Radar from a JSON build description.')
    ap.add_argument('desc')
    ap.add_argument('--out', help='output folder (default: "out" of the description, else dev/build/Treasure-Radar-<version>)')
    ap.add_argument('--force', action='store_true', help='allow an output folder outside dev/build (never inside the mod folder)')
    ap.add_argument('--no-discovery', action='store_true', help='skip the loader discovery check')
    a = ap.parse_args(argv)
    try:
        b = Builder(a.desc, a.out, a.force)
        print('building %s %s -> %s' % (b.title, b.version, b.out))
        b.build(discovery=not a.no_discovery)
    except (BuildError, OSError, ValueError) as e:      # ValueError: also a JSON syntax error
        print('BUILD FAILED: %s' % e)
        return 1
    print('built %s (%d option folders, %d resources, %d warnings); meta in %s'
          % (b.out, len(b.archives), len(b.rows), len(b.warnings), b.meta))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
