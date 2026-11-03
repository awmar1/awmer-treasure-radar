"""patchlib: read and write Helldivers 2 (Stingray) patch archives, as Treasure Radar ships them.

A patch archive is three files that share a name: `<name>` (the main file: header, table of contents and each
resource's main part), `<name>.gpu_resources` (texture pixels etc.) and `<name>.stream` (streamed data).

Layout (all little-endian; determined from all 29 archives of Treasure Radar 0.5.1, see README.md):

  header, 72 bytes
    0x00 u32  magic 0xF0000011
    0x04 u32  number of type rows
    0x08 u32  number of entries
    0x0C u32  unknown, 0
    0x10 56 B unknown; all zero except u32 0x7BEA (31722) at 0x20 (file offset). Kept verbatim.
  type rows, 32 bytes each (one per resource type, ascending type id; entries are grouped in this order)
    0x00 u64  unknown, 0
    0x08 u64  type id (murmur64a of the type name: 'lua', 'texture')
    0x10 u64  number of entries of this type
    0x18 u32  16
    0x1C u32  64 when the archive has GPU/stream data, else 16 (same value as entry +0x48)
  entries, 80 bytes each
    0x00 u64  resource id (murmur64a of the resource name)
    0x08 u64  type id
    0x10 u64  offset of the main part in the main file
    0x18 u64  offset in .stream (0 when there is no stream part)
    0x20 u64  offset in .gpu_resources (0 when there is no GPU part)
    0x28 u64  unknown, 0
    0x30 u64  unknown, 0
    0x38 u32  size of the main part
    0x3C u32  size of the stream part
    0x40 u32  size of the GPU part
    0x44 u32  16
    0x48 u32  64 when the archive has GPU/stream data, else 16
    0x4C u32  index of the entry (0, 1, 2, ...)
  main parts: the first at the TOC end rounded up to 16, each next at the previous end rounded up to 16, zero padded.
    The file ends: padded with zeros to a multiple of 16 when the archive has no GPU data (every Lua-only 0.5.1
    archive), unpadded when it has GPU data (0.5.1's core). Both are kept exactly by `pad_main_end`.
  .gpu_resources: GPU parts at offsets that are multiples of 64, zero padded between; the file ends at a multiple of 64.
  .stream: like .gpu_resources (alignment 64 assumed; every 0.5.1 .stream file is empty).

Lua resource main part: u32 length of the text, u32 flag (2 = source text), the text (no terminator).

Usage as a tool:
  python -I patchlib.py info <archive or folder> [...]      describe archives
  python -I patchlib.py check <mod folder or archive> [...]  parse + rewrite every archive, compare bytes
"""
import os
import struct
import sys
from dataclasses import dataclass, field

MAGIC = 0xF0000011
HEADER_SIZE, TYPE_ROW_SIZE, ENTRY_SIZE = 72, 32, 80
ARCHIVE_NAME = '9ba626afa44a3aa3.patch_0'     # the archive Arsenal deploys as data/9ba626afa44a3aa3.patch_<N>
GPU_EXT, STREAM_EXT = '.gpu_resources', '.stream'

MAIN_ALIGN, GPU_ALIGN, STREAM_ALIGN = 16, 64, 64
# The 56 unknown header bytes at 0x10, as every 0.5.1 archive has them.
DEFAULT_HEADER_EXTRA = bytes(16) + struct.pack('<I', 0x7BEA) + bytes(36)

_M64 = 0xC6A4A7935BD1E995
_MASK = (1 << 64) - 1


def murmur64a(data, seed=0):
    """MurmurHash64A, the hash Stingray uses for resource names and type names."""
    if isinstance(data, str):
        data = data.encode('utf-8')
    n = len(data)
    h = (seed ^ (n * _M64)) & _MASK
    nb = n // 8
    for k, in struct.iter_unpack('<Q', data[:nb * 8]):
        k = (k * _M64) & _MASK
        k ^= k >> 47
        k = (k * _M64) & _MASK
        h ^= k
        h = (h * _M64) & _MASK
    tail = data[nb * 8:]
    if tail:
        for i in range(len(tail) - 1, -1, -1):
            h ^= tail[i] << (8 * i)
        h = (h * _M64) & _MASK
    h ^= h >> 47
    h = (h * _M64) & _MASK
    h ^= h >> 47
    return h


def resource_id(name):
    """The 64-bit id of a resource name, as the game computes it (murmur64a, seed 0)."""
    return murmur64a(name)


TYPE_LUA = murmur64a('lua')            # 0xa14e8dfa2cd117e2
TYPE_TEXTURE = murmur64a('texture')    # 0xcd4238c6a0c69e32
TYPE_NAMES = {TYPE_LUA: 'lua', TYPE_TEXTURE: 'texture'}
LOADER_ID = murmur64a('boot')          # 0xf476df93691895fa: the game's boot script, replaced by the built-in loader
assert TYPE_LUA == 0xA14E8DFA2CD117E2 and TYPE_TEXTURE == 0xCD4238C6A0C69E32 and LOADER_ID == 0xF476DF93691895FA

LUA_SOURCE = 2                         # Lua resource flag: the text is source code


def type_name(t):
    return TYPE_NAMES.get(t, '%016x' % t)


def parse_type(t):
    """'lua' / 'texture' / a hex id / an int -> type id."""
    if isinstance(t, int):
        return t
    for k, v in TYPE_NAMES.items():
        if v == t:
            return k
    return int(t, 16)


def hexid(i):
    return '%016x' % i


def parse_id(s):
    if isinstance(s, int):
        return s
    s = s.strip().lower()
    if s.startswith('0x'):
        s = s[2:]
    if len(s) != 16 or any(c not in '0123456789abcdef' for c in s):
        raise ValueError('not a 16-hex-digit id: %r' % s)
    return int(s, 16)


def align(x, a):
    return (x + a - 1) // a * a


def lua_body(text, flag=LUA_SOURCE):
    """Lua text (bytes) -> the main part of a Lua resource."""
    if isinstance(text, str):
        text = text.encode('utf-8')
    return struct.pack('<II', len(text), flag) + text


def parse_lua_body(data):
    """Main part of a Lua resource -> (flag, text bytes). Raises if the length doesn't add up."""
    if len(data) < 8:
        raise ValueError('Lua resource shorter than its 8-byte prefix')
    n, flag = struct.unpack_from('<II', data, 0)
    if n != len(data) - 8:
        raise ValueError('Lua resource length %d does not match its size %d - 8' % (n, len(data)))
    return flag, data[8:]


class FormatError(Exception):
    pass


@dataclass
class Resource:
    id: int
    type: int
    data: bytes = b''          # main part (Lua: prefix + text; texture: 0x154-byte header)
    gpu: bytes = b''           # .gpu_resources part
    stream: bytes = b''        # .stream part
    # fields of the entry nobody has seen set to anything but these (None: the writer's rule)
    unk_28: int = 0
    unk_30: int = 0
    unk_44: int = None
    unk_48: int = None
    name: str = None           # optional, informational only (not stored in the archive)

    @property
    def type_name(self):
        return type_name(self.type)

    def lua(self):
        """(flag, text) of a Lua resource."""
        return parse_lua_body(self.data)


@dataclass
class TypeFields:
    unk_00: int = 0
    unk_18: int = None
    unk_1c: int = None


class Archive:
    """A patch archive in memory: resources plus the few archive-wide fields.

    `to_bytes()` lays it out with the rules above (the canonical layout). `parse()` keeps every field it reads and
    records in `deviations` anything the canonical writer would not reproduce (another tool's archive); for every
    0.5.1 archive that list is empty and `to_bytes()` gives back the same bytes.
    """

    def __init__(self, resources=None):
        self.resources = list(resources or [])
        self.header_unk_0c = 0
        self.header_extra = DEFAULT_HEADER_EXTRA
        self.type_fields = {}          # type id -> TypeFields (parsed values; missing: the writer's rule)
        self.pad_main_end = None       # None: pad to 16 unless the archive has GPU/stream data
        self.pad_gpu_end = True        # pad .gpu_resources to a multiple of 64 at the end
        self.pad_stream_end = True
        self.deviations = []           # set by parse(): how the parsed bytes differ from the canonical layout

    # ------------------------------------------------------------------ helpers
    def has_gpu(self):
        return any(r.gpu or r.stream for r in self.resources)

    def wide(self):
        """The value of entry +0x48 / type row +0x1C: 64 with GPU/stream data, else 16."""
        return 64 if self.has_gpu() else 16

    def type_order(self):
        return sorted(set(r.type for r in self.resources))

    def ordered(self):
        """Resources grouped by type (ascending type id), each group in the order given."""
        out = []
        for t in self.type_order():
            out.extend(r for r in self.resources if r.type == t)
        return out

    def find(self, rid):
        for r in self.resources:
            if r.id == rid:
                return r
        return None

    def add(self, res):
        if self.find(res.id) is not None:
            raise ValueError('duplicate resource id %016x' % res.id)
        self.resources.append(res)
        return res

    # ------------------------------------------------------------------ writing
    def layout(self):
        """-> (ordered resources, [(offset, stream_offset, gpu_offset)], main size before end padding, gpu end, stream end)."""
        res = self.ordered()
        types = self.type_order()
        toc_end = HEADER_SIZE + TYPE_ROW_SIZE * len(types) + ENTRY_SIZE * len(res)
        pos, gpos, spos = toc_end, 0, 0
        offs = []
        for r in res:
            pos = align(pos, MAIN_ALIGN)
            off = pos
            pos += len(r.data)
            goff = soff = 0
            if r.gpu:
                gpos = align(gpos, GPU_ALIGN)
                goff = gpos
                gpos += len(r.gpu)
            if r.stream:
                spos = align(spos, STREAM_ALIGN)
                soff = spos
                spos += len(r.stream)
            offs.append((off, soff, goff))
        return res, offs, pos, gpos, spos

    def to_bytes(self):
        """-> (main, gpu_resources, stream) bytes."""
        res, offs, main_end, gpu_end, stream_end = self.layout()
        types = self.type_order()
        if len(res) > 0xFFFFFFFF or len(types) > 0xFFFFFFFF:
            raise ValueError('too many resources')
        for r in res:
            for what, b in (('main', r.data), ('gpu', r.gpu), ('stream', r.stream)):
                if len(b) > 0xFFFFFFFF:
                    raise ValueError('%016x: %s part over 4 GiB' % (r.id, what))
            if not (0 <= r.id <= _MASK):
                raise ValueError('bad id %r' % r.id)
        wide = self.wide()
        out = bytearray()
        if len(self.header_extra) != 56:
            raise ValueError('header_extra must be 56 bytes')
        out += struct.pack('<IIII', MAGIC, len(types), len(res), self.header_unk_0c) + self.header_extra
        for t in types:
            tf = self.type_fields.get(t) or TypeFields()
            out += struct.pack('<QQQII', tf.unk_00, t, sum(1 for r in res if r.type == t),
                               16 if tf.unk_18 is None else tf.unk_18, wide if tf.unk_1c is None else tf.unk_1c)
        for i, (r, (off, soff, goff)) in enumerate(zip(res, offs)):
            out += struct.pack('<QQQQQQQIIIIII', r.id, r.type, off, soff, goff, r.unk_28, r.unk_30,
                               len(r.data), len(r.stream), len(r.gpu),
                               16 if r.unk_44 is None else r.unk_44, wide if r.unk_48 is None else r.unk_48, i)
        gpu = bytearray(gpu_end)
        stream = bytearray(stream_end)
        for r, (off, soff, goff) in zip(res, offs):
            out += bytes(off - len(out))
            out += r.data
            if r.gpu:
                gpu[goff:goff + len(r.gpu)] = r.gpu
            if r.stream:
                stream[soff:soff + len(r.stream)] = r.stream
        pad_main = (not self.has_gpu()) if self.pad_main_end is None else self.pad_main_end
        if pad_main:
            out += bytes(align(len(out), MAIN_ALIGN) - len(out))
        if self.pad_gpu_end:
            gpu += bytes(align(len(gpu), GPU_ALIGN) - len(gpu))
        if self.pad_stream_end:
            stream += bytes(align(len(stream), STREAM_ALIGN) - len(stream))
        return bytes(out), bytes(gpu), bytes(stream)

    def write(self, path):
        """Write `path`, `path.gpu_resources` and `path.stream` (the folder must exist)."""
        main, gpu, stream = self.to_bytes()
        for p, b in ((path, main), (path + GPU_EXT, gpu), (path + STREAM_EXT, stream)):
            with open(p, 'wb') as f:
                f.write(b)
        return main, gpu, stream

    # ------------------------------------------------------------------ reading
    @classmethod
    def read(cls, path):
        """Read an archive from its main file's path (the .gpu_resources and .stream files may be missing: empty)."""
        def load(p):
            if not os.path.exists(p):
                return b''
            with open(p, 'rb') as f:
                return f.read()
        with open(path, 'rb') as f:
            main = f.read()
        return cls.parse(main, load(path + GPU_EXT), load(path + STREAM_EXT))

    @classmethod
    def parse(cls, main, gpu=b'', stream=b''):
        a = cls()
        dev = a.deviations
        if len(main) < HEADER_SIZE:
            raise FormatError('main file shorter than the 72-byte header')
        magic, nt, ne, a.header_unk_0c = struct.unpack_from('<IIII', main, 0)
        if magic != MAGIC:
            raise FormatError('bad magic 0x%08x' % magic)
        a.header_extra = bytes(main[16:72])
        toc_end = HEADER_SIZE + nt * TYPE_ROW_SIZE + ne * ENTRY_SIZE
        if len(main) < toc_end:
            raise FormatError('main file cut off inside its table of contents')
        rows = []
        o = HEADER_SIZE
        for _ in range(nt):
            unk_00, t, count, unk_18, unk_1c = struct.unpack_from('<QQQII', main, o)
            o += TYPE_ROW_SIZE
            rows.append((t, count))
            a.type_fields[t] = TypeFields(unk_00, unk_18, unk_1c)
        entries = []
        for i in range(ne):
            e = struct.unpack_from('<QQQQQQQIIIIII', main, o)
            o += ENTRY_SIZE
            rid, t, off, soff, goff, u28, u30, size, ssize, gsize, u44, u48, idx = e
            for what, start, n, blob in (('main', off, size, main), ('stream', soff, ssize, stream),
                                         ('gpu', goff, gsize, gpu)):
                if n and start + n > len(blob):
                    raise FormatError('entry %d (%016x): %s part %d+%d is past the end (%d)' % (i, rid, what, start, n, len(blob)))
            r = Resource(rid, t, bytes(main[off:off + size]), bytes(gpu[goff:goff + gsize]),
                         bytes(stream[soff:soff + ssize]), u28, u30, u44, u48)
            a.resources.append(r)
            entries.append(e)
        # ---- how does it compare with the canonical layout?
        # values the writer's rule produces anyway are dropped (None), so a resource moved elsewhere gets the rule
        wide = a.wide()
        for r in a.resources:
            if r.unk_44 == 16:
                r.unk_44 = None
            if r.unk_48 == wide:
                r.unk_48 = None
        for tf in a.type_fields.values():
            if tf.unk_18 == 16:
                tf.unk_18 = None
            if tf.unk_1c == wide:
                tf.unk_1c = None
        ids = [r.id for r in a.resources]
        if len(set(ids)) != len(ids):
            dev.append('duplicate resource ids')
        canon_types = a.type_order()
        if [t for t, _ in rows] != canon_types:
            dev.append('type rows are not one per type in ascending type id order')
        for t, count in rows:
            if count != sum(1 for r in a.resources if r.type == t):
                dev.append('type row %016x count %d does not match its entries' % (t, count))
        if a.ordered() != a.resources:
            dev.append('entries are not grouped by type in type-row order')
        for i, e in enumerate(entries):
            if e[12] != i:
                dev.append('entry %d has index %d' % (i, e[12]))
                break
        # trailing padding of the main file
        last_end = max([e[2] + e[7] for e in entries] + [toc_end])
        tail = main[last_end:]
        if any(tail):
            dev.append('non-zero bytes after the last resource in the main file')
        if len(main) == last_end:
            a.pad_main_end = False
        elif len(main) == align(last_end, MAIN_ALIGN):
            a.pad_main_end = True
        else:
            dev.append('main file has %d bytes after the last resource' % len(tail))
        if a.pad_main_end == (not a.has_gpu()):
            a.pad_main_end = None           # what the writer does anyway
        gpu_end = max([e[4] + e[9] for e in entries if e[9]] + [0])
        stream_end = max([e[3] + e[8] for e in entries if e[8]] + [0])
        for what, blob, end, al, attr in (('gpu', gpu, gpu_end, GPU_ALIGN, 'pad_gpu_end'),
                                          ('stream', stream, stream_end, STREAM_ALIGN, 'pad_stream_end')):
            if len(blob) == align(end, al):
                setattr(a, attr, True)
            elif len(blob) == end:
                setattr(a, attr, False)
            else:
                dev.append('%s file has %d bytes after its last resource' % (what, len(blob) - end))
        # wide value and the offsets: compare with what to_bytes would write
        if not dev:
            res, offs, _, _, _ = a.layout()
            for e, (off, soff, goff) in zip(entries, offs):
                if (e[2], e[3], e[4]) != (off, soff, goff):
                    dev.append('entry %016x is at %x/%x/%x, the canonical layout puts it at %x/%x/%x'
                               % (e[0], e[2], e[3], e[4], off, soff, goff))
                    break
            # padding between parts must be zeros
            covered = [(0, toc_end)] + [(e[2], e[2] + e[7]) for e in entries]
            covered.sort()
            pos = 0
            for s, t in covered:
                if s > pos and any(main[pos:s]):
                    dev.append('non-zero padding in the main file at %x' % pos)
                    break
                pos = max(pos, t)
            for what, blob, k_off, k_size in (('gpu', gpu, 4, 9), ('stream', stream, 3, 8)):
                spans = sorted((e[k_off], e[k_off] + e[k_size]) for e in entries if e[k_size])
                pos = 0
                for s, t in spans + [(len(blob), len(blob))]:
                    if s > pos and any(blob[pos:s]):
                        dev.append('non-zero padding in the %s file at %x' % (what, pos))
                        break
                    pos = max(pos, t)
        return a

    # ------------------------------------------------------------------ description
    def summary(self):
        lines = []
        res = self.ordered()
        main, gpu, stream = self.to_bytes()
        lines.append('%d types, %d resources; main %d B, gpu %d B, stream %d B; header +0x0c=%d extra=%s'
                     % (len(self.type_order()), len(res), len(main), len(gpu), len(stream), self.header_unk_0c,
                        self.header_extra.hex() if self.header_extra != DEFAULT_HEADER_EXTRA else '(0.5.1 default)'))
        for t in self.type_order():
            tf = self.type_fields.get(t) or TypeFields()
            lines.append('  type %-10s %016x x%d  (+0x18=%s +0x1c=%s)' % (type_name(t), t, sum(1 for r in res if r.type == t),
                                                                          tf.unk_18, tf.unk_1c))
        for i, r in enumerate(res):
            extra = ''
            if r.type == TYPE_LUA:
                try:
                    flag, text = r.lua()
                    extra = 'flag %d: %s' % (flag, text.split(b'\n', 1)[0][:70].decode('utf-8', 'replace'))
                except ValueError as e:
                    extra = str(e)
            lines.append('  %3d %016x %-8s main %7d gpu %8d stream %d  %s' % (i, r.id, r.type_name, len(r.data),
                                                                              len(r.gpu), len(r.stream), extra))
        if self.deviations:
            lines.append('  NOT CANONICAL: ' + '; '.join(self.deviations))
        return '\n'.join(lines)


def archives_in(path):
    """Every archive main file under `path` (a mod folder, an option folder or an archive)."""
    if os.path.isfile(path):
        return [path]
    out = []
    for root, dirs, files in os.walk(path):
        dirs.sort()
        for f in sorted(files):
            if f.endswith(GPU_EXT) or f.endswith(STREAM_EXT):
                continue
            if '.patch_' in f and f.rsplit('.patch_', 1)[1].isdigit():
                out.append(os.path.join(root, f))
    return out


def check_roundtrip(path):
    """Parse an archive and rewrite it; -> list of problems (empty: byte-identical, all three files)."""
    a = Archive.read(path)
    problems = list(a.deviations)
    main, gpu, stream = a.to_bytes()
    for what, p, b in (('main', path, main), ('gpu', path + GPU_EXT, gpu), ('stream', path + STREAM_EXT, stream)):
        orig = open(p, 'rb').read() if os.path.exists(p) else b''
        if orig != b:
            n = next((i for i in range(min(len(orig), len(b))) if orig[i] != b[i]), min(len(orig), len(b)))
            problems.append('%s differs (sizes %d vs %d, first difference at %x)' % (what, len(orig), len(b), n))
    return problems


def _main(argv):
    if len(argv) < 2 or argv[0] not in ('info', 'check'):
        print(__doc__)
        return 2
    bad = 0
    for p in argv[1:]:
        for ap in archives_in(p):
            if argv[0] == 'info':
                print(ap)
                print(Archive.read(ap).summary())
            else:
                probs = check_roundtrip(ap)
                print('%s %s' % ('ok  ' if not probs else 'FAIL', ap) + ('' if not probs else ': ' + '; '.join(probs)))
                bad += bool(probs)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(_main(sys.argv[1:]))
