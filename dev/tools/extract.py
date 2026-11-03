"""extract: dump every resource of every option folder of a packaged Treasure Radar (or any Arsenal mod folder).

  python -I extract.py <mod folder> <out dir>

Writes, for each option folder that holds a patch archive:
  <out>/<option>/<label>.lua            Lua resources: the text after the 8-byte prefix, byte for byte
  <out>/<option>/textures/<label>.png   texture resources: RGBA PNG (tex.py; rebuilds the resource exactly)
  <out>/<option>/raw/<id>.{main,gpu,stream}   resources of any other type, as stored
and <out>/index.json: option -> archive fields and resources (index, id, type, sizes, sha256, file, and per type
the Lua flag and header line, or the texture size and format), plus every resource name it could prove.

Names: the archive stores only ids (murmur64a of a name). extract.py tries names it can guess and keeps those
whose hash matches ('name' in the index; 'lua_ref' says where an addon refers to a texture id):
  'boot' (the loader), the header path of each Lua file, '<mod>/options/<option>', and for textures the addon's
  assignments: TEXTURES.x -> '<mod>/x', TEXTURES.x[n] -> '<mod>/x_<n-1>', GLYPHS[i][c] (cap N) ->
  '<mod>/glyph<N>_<byte of c>', T.TEX['a/b'] -> 'treasure_radar/a/b' (the bundle.py scheme).
  0.5.1's nine icon textures (TEXTURES.credit ...) match none of these; their names are unknown.
"""
import hashlib
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import patchlib as pl  # noqa: E402
import tex  # noqa: E402

HEADER_RE = re.compile(rb'^%?-- HD2-(\w+): ([\w/.\-]+)')
_ID = r"'([0-9a-fA-F]{16})'"
RE_TEX_FIELD = re.compile(r"\bTEXTURES\.(\w+)\s*=\s*" + _ID)
RE_TEX_ARRAY = re.compile(r"\bTEXTURES\.(\w+)\[(\d+)\]\s*=\s*" + _ID)
RE_GLYPH_CAP = re.compile(r"\bGLYPHS\[(\d+)\]\s*=\s*\{\s*cap\s*=\s*(\d+)")
RE_GLYPH = re.compile(r"\bGLYPHS\[(\d+)\]\[(['\"])(.)\2\]\s*=\s*\{\s*" + _ID)
RE_TTEX = re.compile(r"\bT\.TEX\[(['\"])([^'\"]+)\1\]\s*=\s*" + _ID)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def option_folders(mod):
    out = []
    for d in sorted(os.listdir(mod)):
        p = os.path.join(mod, d)
        if d in ('dev',) or not os.path.isdir(p):
            continue
        if os.path.isfile(os.path.join(p, pl.ARCHIVE_NAME)):
            out.append(d)
    return out


def lua_header(text):
    """-> (kind, path) of a '-- HD2-<Kind>: <path>' first line, or (None, None)."""
    m = HEADER_RE.match(text.split(b'\n', 1)[0])
    if not m:
        return None, None
    return m.group(1).decode(), m.group(2).decode()


def texture_refs(text, mod):
    """Lua source of an addon -> {id: (lua_ref, [candidate names])}."""
    s = text.decode('utf-8', 'replace')
    refs = {}
    for m in RE_TEX_FIELD.finditer(s):
        refs[int(m.group(2), 16)] = ('TEXTURES.%s' % m.group(1), ['%s/%s' % (mod, m.group(1))])
    for m in RE_TEX_ARRAY.finditer(s):
        n = int(m.group(2))
        refs[int(m.group(3), 16)] = ('TEXTURES.%s[%d]' % (m.group(1), n),
                                     ['%s/%s_%d' % (mod, m.group(1), n - 1), '%s/%s_%d' % (mod, m.group(1), n),
                                      '%s/%s/%02d' % (mod, m.group(1), n - 1)])
    caps = {int(m.group(1)): int(m.group(2)) for m in RE_GLYPH_CAP.finditer(s)}
    for m in RE_GLYPH.finditer(s):
        i, c = int(m.group(1)), m.group(3)
        cap = caps.get(i)
        names = ['%s/glyph%d_%d' % (mod, cap, ord(c))] if cap is not None else []
        refs[int(m.group(4), 16)] = ("GLYPHS[%d]['%s']" % (i, c) + (' (cap %d)' % cap if cap else ''), names)
    for m in RE_TTEX.finditer(s):
        n = m.group(2)
        refs[int(m.group(3), 16)] = ("T.TEX['%s']" % n, ['treasure_radar/' + n, mod + '/' + n])
    return refs


def _dflt(v, d):
    return d if v is None else v


def safe_label(s):
    return re.sub(r'[^A-Za-z0-9_.\-]+', '_', s).strip('._') or 'x'


def extract(mod, out, quiet=False):
    mod = os.path.abspath(mod)
    out = os.path.abspath(out)
    if out == mod or not out.startswith(os.path.join(mod, 'dev') + os.sep) and out.startswith(mod + os.sep):
        raise SystemExit('refusing to write into the mod folder itself: %s' % out)
    folders = option_folders(mod)
    archives = {f: pl.Archive.read(os.path.join(mod, f, pl.ARCHIVE_NAME)) for f in folders}

    # ---- names: collect candidates from every Lua resource of the mod
    mods = set()
    refs = {}
    for a in archives.values():
        for r in a.resources:
            if r.type == pl.TYPE_LUA:
                try:
                    _, text = r.lua()
                except ValueError:
                    continue
                kind, path = lua_header(text)
                if path:
                    mods.add(path)
                if kind == 'Addon':
                    refs.update(texture_refs(text, path))
    names = {pl.LOADER_ID: 'boot'}
    for p in mods:
        names[pl.resource_id(p)] = p
    for f in folders:
        for p in mods:
            names[pl.resource_id('%s/options/%s' % (p, f))] = '%s/options/%s' % (p, f)
    for rid, (ref, cands) in refs.items():
        for c in cands:
            if pl.resource_id(c) == rid:
                names[rid] = c
                break

    if os.path.isdir(out) and os.listdir(out):
        if not os.path.isfile(os.path.join(out, 'index.json')):
            raise SystemExit('%s is not empty and not an earlier extraction (no index.json): not touching it' % out)
        shutil.rmtree(out)
    os.makedirs(out, exist_ok=True)
    manifest = None
    mpath = os.path.join(mod, 'manifest.json')
    if os.path.isfile(mpath):
        with open(mpath, 'rb') as f:
            mbytes = f.read()
        mj = json.loads(mbytes)
        manifest = {'file': 'manifest.json', 'sha256': sha(mbytes), 'Guid': mj.get('Guid'), 'Name': mj.get('Name'),
                    'Version': mj.get('Version')}
    index = {'tool': 'dev/tools/extract.py', 'format': 1, 'source': mod, 'manifest': manifest, 'options': {},
             'names': {pl.hexid(k): v for k, v in sorted(names.items(), key=lambda kv: kv[1])}}
    counts = {}
    for f in folders:
        a = archives[f]
        base = os.path.join(mod, f, pl.ARCHIVE_NAME)
        files = {}
        for what, p in (('main', base), ('gpu', base + pl.GPU_EXT), ('stream', base + pl.STREAM_EXT)):
            b = open(p, 'rb').read() if os.path.exists(p) else b''
            files[what] = {'size': len(b), 'sha256': sha(b)}
        entry = {
            'archive': pl.ARCHIVE_NAME,
            'files': files,
            'canonical': not a.deviations and pl.check_roundtrip(base) == [],
            'deviations': a.deviations,
            'header_unk_0c': a.header_unk_0c,
            'header_extra': 'default' if a.header_extra == pl.DEFAULT_HEADER_EXTRA else a.header_extra.hex(),
            'types': [{'type': pl.type_name(t), 'id': pl.hexid(t), 'count': sum(1 for r in a.resources if r.type == t),
                       'unk_18': _dflt(a.type_fields[t].unk_18, 16), 'unk_1c': _dflt(a.type_fields[t].unk_1c, a.wide())}
                      for t in a.type_order()],
            'pad_main_end': a.pad_main_end,
            'resources': [],
        }
        odir = os.path.join(out, f)
        os.makedirs(odir)
        used = set()

        def label_for(r, ext, sub):
            n = names.get(r.id)
            if n == 'boot':
                lab = 'boot'
            elif n:
                lab = n.rsplit('/', 1)[-1]
            elif r.id in refs:
                lab = refs[r.id][0].replace('TEXTURES.', '')
            else:
                lab = pl.hexid(r.id)
            lab = safe_label(lab)
            key = (sub, lab.lower())
            if key in used:
                lab = '%s_%s' % (lab, pl.hexid(r.id))
                key = (sub, lab.lower())
            used.add(key)
            return (sub + '/' if sub else '') + lab + ext

        for i, r in enumerate(a.resources):
            e = {'index': i, 'id': pl.hexid(r.id), 'type': pl.type_name(r.type), 'size': len(r.data),
                 'gpu_size': len(r.gpu), 'stream_size': len(r.stream), 'sha256': sha(r.data)}
            if r.gpu:
                e['gpu_sha256'] = sha(r.gpu)
            if r.stream:
                e['stream_sha256'] = sha(r.stream)
            if r.id in names:
                e['name'] = names[r.id]
            if r.id in refs:
                e['lua_ref'] = refs[r.id][0]
            for k in ('unk_28', 'unk_30'):
                if getattr(r, k):
                    e[k] = getattr(r, k)
            for k in ('unk_44', 'unk_48'):
                if getattr(r, k) is not None:
                    e[k] = getattr(r, k)
            done = False
            if r.type == pl.TYPE_LUA and not r.gpu and not r.stream:
                try:
                    flag, text = r.lua()
                except ValueError as err:
                    e['error'] = str(err)
                else:
                    rel = label_for(r, '.lua', '')
                    with open(os.path.join(odir, rel), 'wb') as fh:
                        fh.write(text)
                    kind, path = lua_header(text)
                    e.update({'file': '%s/%s' % (f, rel), 'lua_flag': flag, 'lua_kind': kind, 'lua_path': path,
                              'first_line': text.split(b'\n', 1)[0].decode('utf-8', 'replace')[:200],
                              'text_sha256': sha(text)})
                    done = True
            elif r.type == pl.TYPE_TEXTURE and not r.stream:
                try:
                    info = tex.parse_toc(r.data)
                    png = tex.decode_png(r.data, r.gpu)
                except tex.TextureError as err:
                    e['error'] = str(err)
                else:
                    rel = label_for(r, '.png', 'textures')
                    os.makedirs(os.path.join(odir, 'textures'), exist_ok=True)
                    with open(os.path.join(odir, rel), 'wb') as fh:
                        fh.write(png)
                    e.update({'file': '%s/%s' % (f, rel), 'width': info['width'], 'height': info['height'],
                              'dxgi': info['dxgi'], 'toc_canonical': info['canonical']})
                    if not info['canonical']:
                        e['toc_hex'] = r.data.hex()
                    done = True
            if not done:
                os.makedirs(os.path.join(odir, 'raw'), exist_ok=True)
                stem = os.path.join(odir, 'raw', pl.hexid(r.id))
                for ext, b in (('.main', r.data), ('.gpu', r.gpu), ('.stream', r.stream)):
                    if b or ext == '.main':
                        with open(stem + ext, 'wb') as fh:
                            fh.write(b)
                e['file'] = '%s/raw/%s.main' % (f, pl.hexid(r.id))
            entry['resources'].append(e)
            counts[e['type']] = counts.get(e['type'], 0) + 1
        index['options'][f] = entry
    with open(os.path.join(out, 'index.json'), 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(index, fh, indent=1)
        fh.write('\n')
    if not quiet:
        nres = sum(counts.values())
        named = sum(1 for o in index['options'].values() for e in o['resources'] if 'name' in e)
        print('extracted %d option folders, %d resources (%s), %d with a proven name -> %s'
              % (len(folders), nres, ', '.join('%d %s' % (v, k) for k, v in sorted(counts.items())), named, out))
        noncanon = [f for f, o in index['options'].items() if not o['canonical']]
        if noncanon:
            print('not canonical (patchlib would not rewrite them byte for byte): %s' % ', '.join(noncanon))
    return index


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    extract(argv[0], argv[1])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
