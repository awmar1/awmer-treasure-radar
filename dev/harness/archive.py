"""Minimal reader for Helldivers 2 patch archives (as Treasure Radar's build writes them and the mod manager deploys
them): the table of contents, Lua resources and textures (DX10 R8G8B8A8, one mip, pixels in .gpu_resources).

Layout: 72-byte header (u32 magic 0xF0000011, u32 type count, u32 entry count, ...), 32-byte type rows, 80-byte
entries (u64 id, u64 type, u64 offset, u64 stream offset, u64 gpu offset, 2 unused u64; u32 size, u32 stream size,
u32 gpu size, u32 alignment, u32 64, u32 index). A Lua resource is u32 length, u32 flag (2 = source text), the text.
A texture resource is a 0xC0-byte Stingray header, then a DDS header ("DDS ", height at +12, width at +16, mips at
+28, FourCC "DX10" at +84; the DX10 header at 0x140 starts with the DXGI format).
"""
import os
import struct

MAGIC = 0xF0000011
LUA_TYPE = 0xA14E8DFA2CD117E2
TEXTURE_TYPE = 0xCD4238C6A0C69E32
DXGI_NAMES = {28: 'R8G8B8A8_UNORM', 29: 'R8G8B8A8_UNORM_SRGB', 87: 'B8G8R8A8_UNORM', 91: 'B8G8R8A8_UNORM_SRGB'}


class Entry:
    __slots__ = ('id', 'type', 'offset', 'stream_offset', 'gpu_offset', 'size', 'stream_size', 'gpu_size', 'index')

    def __init__(self, raw):
        (self.id, self.type, self.offset, self.stream_offset, self.gpu_offset, _u1, _u2) = struct.unpack('<7Q', raw[:56])
        (self.size, self.stream_size, self.gpu_size, _align, _u3, self.index) = struct.unpack('<6I', raw[56:80])

    @property
    def hex(self):
        return '%016x' % self.id


class Patch:
    """One patch file (plus its .gpu_resources / .stream siblings, read lazily)."""

    def __init__(self, path):
        self.path = path
        with open(path, 'rb') as f:
            self.data = f.read()
        if len(self.data) < 72:
            raise ValueError('%s: too short for a patch header' % path)
        magic, ntypes, nentries = struct.unpack('<III', self.data[:12])
        if magic != MAGIC:
            raise ValueError('%s: not a patch archive (magic %08x)' % (path, magic))
        self.ntypes, self.nentries = ntypes, nentries
        base = 72 + ntypes * 32
        self.entries = [Entry(self.data[base + i * 80: base + i * 80 + 80]) for i in range(nentries)]
        self.by_id = {e.hex: e for e in self.entries}
        self._gpu = None

    @property
    def gpu(self):
        if self._gpu is None:
            p = self.path + '.gpu_resources'
            self._gpu = open(p, 'rb').read() if os.path.exists(p) else b''
        return self._gpu

    def of_type(self, typ):
        return [e for e in self.entries if e.type == typ]

    def lua_source(self, e):
        """The Lua source text of a Lua resource (bytes), or None if it isn't stored as source."""
        if isinstance(e, str):
            e = self.by_id[e.lower().rjust(16, '0')]
        raw = self.data[e.offset:e.offset + e.size]
        if len(raw) < 8:
            return None
        n, flag = struct.unpack('<II', raw[:8])
        if flag != 2:
            return None
        return raw[8:8 + n] if n <= len(raw) - 8 else raw[8:]

    def lua_resources(self):
        """[(hex id, source bytes)] for every Lua resource stored as source."""
        out = []
        for e in self.of_type(LUA_TYPE):
            src = self.lua_source(e)
            if src is not None:
                out.append((e.hex, src))
        return out

    def texture_info(self, e):
        t = self.data[e.offset:e.offset + e.size]
        if len(t) < 0x144 or t[0xC0:0xC4] != b'DDS ':
            return None
        h, w = struct.unpack('<II', t[0xC0 + 12:0xC0 + 20])
        mips = struct.unpack('<I', t[0xC0 + 28:0xC0 + 32])[0]
        fourcc = t[0xC0 + 84:0xC0 + 88]
        dxgi = struct.unpack('<I', t[0x140:0x144])[0] if fourcc == b'DX10' else None
        return {'w': w, 'h': h, 'mips': mips, 'fourcc': fourcc.decode('latin-1'), 'dxgi': dxgi}

    def texture_rgba(self, e):
        """(w, h, RGBA bytes top row first) of the top mip, or None for a format this reader doesn't know."""
        info = self.texture_info(e)
        if not info or info['dxgi'] not in DXGI_NAMES:
            return None
        w, h = info['w'], info['h']
        px = self.gpu[e.gpu_offset:e.gpu_offset + w * h * 4]
        if len(px) != w * h * 4:
            return None
        if info['dxgi'] in (87, 91):   # BGRA -> RGBA
            b = bytearray(px)
            b[0::4], b[2::4] = px[2::4], px[0::4]
            px = bytes(b)
        return w, h, px


def option_patch(mod_dir, option):
    """The patch_0 file of one option folder of a mod."""
    return os.path.join(mod_dir, option, '9ba626afa44a3aa3.patch_0')


if __name__ == '__main__':
    import sys
    p = Patch(sys.argv[1])
    print('%s: %d types, %d entries' % (p.path, p.ntypes, p.nentries))
    for hx, src in p.lua_resources():
        first = src.split(b'\n', 1)[0].decode('utf-8', 'replace')
        print('  lua %s %6d bytes  %s' % (hx, len(src), first[:90]))
    nt = 0
    for e in p.of_type(TEXTURE_TYPE):
        nt += 1
    print('  %d textures' % nt)


def write_lua_patch(path, resources):
    """A patch file holding only Lua source resources: [(hex id, source text or bytes)]. Laid out like the mod's own
    option archives (one type row, data from 16-byte aligned offsets), so the loader's discovery reads it."""
    ne = len(resources)
    head = struct.pack('<III', MAGIC, 1 if ne else 0, ne) + b'\0' * 60
    types = struct.pack('<IIQQII', 0, 0, LUA_TYPE, ne, 16, 16) if ne else b''
    off = 72 + len(types) + ne * 80
    off = (off + 15) // 16 * 16
    entries, blobs = b'', b''
    for i, (hx, src) in enumerate(resources):
        if isinstance(src, str):
            src = src.encode('utf-8')
        blob = struct.pack('<II', len(src), 2) + src
        entries += struct.pack('<7Q6I', int(hx, 16), LUA_TYPE, off + len(blobs), 0, 0, 0, 0, len(blob), 0, 0, 16, 16, i)
        blob += b'\0' * ((-len(blob)) % 16)
        blobs += blob
    pre = head + types + entries
    pre += b'\0' * (off - len(pre))
    with open(path, 'wb') as f:
        f.write(pre + blobs)
