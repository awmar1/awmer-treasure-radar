"""tex: PNG (RGBA) <-> Helldivers 2 texture resource, in the form Treasure Radar 0.5.1 ships its textures.

A texture resource has two parts:

  main part (in the archive's main file), 340 = 0x154 bytes
    0x000 u32  0
    0x004 u32  0
    0x008 u32  0xFFFFFFFF
    0x00C 15 x 12 bytes: stream mip table (u32 offset, u32 bytes, u16 height, u16 width), all zero = not streamed
    0x0C0 148 bytes: a DDS header with a DX10 extension:
          'DDS ', size 124, flags 0x100F (CAPS|HEIGHT|WIDTH|PITCH|PIXELFORMAT), height, width,
          pitch = width * 4, depth 0, mip count 1, 11 x u32 0,
          pixel format { 32, flags 4 (FOURCC), 'DX10', 5 x u32 0 }, caps 0x1000 (TEXTURE), caps2-4 0, reserved 0,
          DX10 { dxgiFormat 28 (R8G8B8A8_UNORM), dimension 3 (TEXTURE2D), misc 0, array size 1, misc2 0 }
  GPU part (in .gpu_resources), width * height * 4 bytes
    the pixels: rows top to bottom, R G B A bytes, no row padding, one mip level.

Every one of 0.5.1's 151 textures is exactly this with only width, height and pitch varying (sizes from 9x18 to
512x512, many not powers of two). That is what `encode` writes.

Limits (what `encode` accepts):
  - width and height 1 .. 16384 (the Direct3D 11 limit for a 2D texture); not powers of two is fine (0.5.1 has 53x44)
  - 8-bit PNGs of any color type (gray, gray+alpha, RGB, RGBA, palette with or without tRNS): converted to RGBA8
    without loss. 16-bit PNGs are refused (RGBA8 would lose bits), as are files that are not PNG.
  - one mip level, no streaming, no compression: a 512x512 texture costs 1 MiB in .gpu_resources.
    The game draws these with screen-GUI bitmaps; scaling a texture far below its size aliases (there are no mips).
  - dxgi 28 (R8G8B8A8_UNORM, the 0.5.1 format) or 29 (R8G8B8A8_UNORM_SRGB, same bytes, untested in game).

Usage:
  python -I tex.py info <file.png | resource.toc>
  python -I tex.py encode <in.png> <out.toc> <out.gpu>          write the two parts of a resource
  python -I tex.py decode <in.toc> <in.gpu> <out.png>           back to PNG (lossless)
  python -I tex.py selftest                                      random PNG -> texture -> PNG round trips
"""
import io
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '_pylib'))
from PIL import Image  # noqa: E402

TOC_SIZE = 0x154
DDS_AT = 0xC0
MAX_SIDE = 16384
DXGI_RGBA8 = 28
DXGI_RGBA8_SRGB = 29
FORMATS = {DXGI_RGBA8: 'R8G8B8A8_UNORM', DXGI_RGBA8_SRGB: 'R8G8B8A8_UNORM_SRGB'}
_PNG_SIG = b'\x89PNG\r\n\x1a\n'


class TextureError(Exception):
    pass


def check_size(width, height):
    if not (isinstance(width, int) and isinstance(height, int)):
        raise TextureError('size must be integers')
    if not (1 <= width <= MAX_SIDE and 1 <= height <= MAX_SIDE):
        raise TextureError('texture size %dx%d is outside 1..%d per side' % (width, height, MAX_SIDE))


def make_toc(width, height, dxgi=DXGI_RGBA8):
    """The 340-byte main part of a width x height RGBA8 texture."""
    check_size(width, height)
    if dxgi not in FORMATS:
        raise TextureError('unsupported dxgi format %r (supported: %s)' % (dxgi, FORMATS))
    head = struct.pack('<III', 0, 0, 0xFFFFFFFF) + bytes(15 * 12)
    dds = b'DDS ' + struct.pack('<7I', 124, 0x100F, height, width, width * 4, 0, 1) + bytes(11 * 4)
    dds += struct.pack('<II4s5I', 32, 4, b'DX10', 0, 0, 0, 0, 0)
    dds += struct.pack('<5I', 0x1000, 0, 0, 0, 0)
    dds += struct.pack('<5I', dxgi, 3, 0, 1, 0)
    toc = head + dds
    assert len(head) == DDS_AT and len(toc) == TOC_SIZE
    return toc


def parse_toc(toc):
    """Main part -> {'width', 'height', 'dxgi', 'mips', 'pitch', 'fourcc', 'canonical'}.

    'canonical' is True when the header is byte-for-byte what make_toc writes for that size and format."""
    if len(toc) < DDS_AT + 148 or toc[DDS_AT:DDS_AT + 4] != b'DDS ':
        raise TextureError('not a texture header (%d bytes, no DDS header at 0xC0)' % len(toc))
    size, flags, height, width, pitch, depth, mips = struct.unpack_from('<7I', toc, DDS_AT + 4)
    fourcc = toc[DDS_AT + 84:DDS_AT + 88]
    dxgi = struct.unpack_from('<I', toc, DDS_AT + 128)[0] if fourcc == b'DX10' else None
    info = {'width': width, 'height': height, 'dxgi': dxgi, 'mips': mips, 'pitch': pitch,
            'fourcc': fourcc.decode('latin-1')}
    try:
        info['canonical'] = toc == make_toc(width, height, dxgi)
    except TextureError:
        info['canonical'] = False
    return info


def png_bit_depth(data):
    if data[:8] != _PNG_SIG or data[12:16] != b'IHDR':
        raise TextureError('not a PNG file')
    return data[24], data[25]          # bit depth, color type


def load_rgba(png):
    """PNG (path or bytes) -> (width, height, RGBA bytes). Refuses what would not round-trip exactly."""
    if isinstance(png, (bytes, bytearray)):
        data = bytes(png)
    else:
        with open(png, 'rb') as f:
            data = f.read()
    depth, ctype = png_bit_depth(data)
    if depth > 8:
        raise TextureError('16-bit PNG: save it with 8 bits per channel')
    im = Image.open(io.BytesIO(data))
    im.load()
    if getattr(im, 'n_frames', 1) > 1:
        raise TextureError('animated PNG: one frame per file, please')
    if im.mode != 'RGBA':
        im = im.convert('RGBA')
    check_size(im.width, im.height)
    return im.width, im.height, im.tobytes()


def encode(png, dxgi=DXGI_RGBA8):
    """PNG (path or bytes) -> (main part, GPU part)."""
    w, h, px = load_rgba(png)
    return make_toc(w, h, dxgi), px


def decode(toc, gpu):
    """(main part, GPU part) -> PIL RGBA image."""
    info = parse_toc(toc)
    if info['dxgi'] not in FORMATS:
        raise TextureError('cannot decode format %r' % (info['dxgi'],))
    if info['mips'] != 1:
        raise TextureError('cannot decode %d mips' % info['mips'])
    w, h = info['width'], info['height']
    if len(gpu) != w * h * 4:
        raise TextureError('GPU part is %d bytes, %dx%d RGBA8 needs %d' % (len(gpu), w, h, w * h * 4))
    return Image.frombytes('RGBA', (w, h), bytes(gpu))


def png_bytes(im):
    """PIL image -> PNG bytes (deterministic: no metadata)."""
    b = io.BytesIO()
    im.save(b, 'PNG', compress_level=9)
    return b.getvalue()


def decode_png(toc, gpu):
    return png_bytes(decode(toc, gpu))


def selftest(n=40, seed=1234):
    """Random RGBA images of many sizes: PNG -> texture -> PNG must give back the same pixels."""
    import random
    rnd = random.Random(seed)
    sizes = [(1, 1), (9, 18), (53, 44), (256, 96), (3, 1000), (1000, 3), (512, 512)] + \
            [(rnd.randint(1, 300), rnd.randint(1, 300)) for _ in range(n)]
    for w, h in sizes:
        px = rnd.randbytes(w * h * 4)
        png = png_bytes(Image.frombytes('RGBA', (w, h), px))
        toc, gpu = encode(png)
        assert gpu == px and len(toc) == TOC_SIZE, (w, h)
        info = parse_toc(toc)
        assert info['canonical'] and (info['width'], info['height']) == (w, h)
        back = decode_png(toc, gpu)
        assert load_rgba(back) == (w, h, px), (w, h)
    # other 8-bit color types become RGBA holding exactly the same colors
    for mode in ('L', 'LA', 'RGB', 'P', '1'):
        im = Image.frombytes('RGBA', (7, 5), rnd.randbytes(140)).convert(mode)
        toc, gpu = encode(png_bytes(im))
        assert decode(toc, gpu).tobytes() == im.convert('RGBA').tobytes(), mode
    # refusals
    for bad in (lambda: make_toc(0, 4), lambda: make_toc(16385, 1), lambda: encode(b'not a png'),
                lambda: encode(png_bytes(Image.new('I;16', (3, 3))))):
        try:
            bad()
        except TextureError:
            pass
        else:
            raise AssertionError('accepted something it must refuse')
    return len(sizes)


def _main(argv):
    if not argv:
        print(__doc__)
        return 2
    cmd = argv[0]
    try:
        if cmd == 'info' and len(argv) == 2:
            with open(argv[1], 'rb') as f:
                data = f.read()
            if data[:8] == _PNG_SIG:
                w, h, _ = load_rgba(data)
                print('%s: PNG %dx%d -> texture main 340 B, GPU %d B' % (argv[1], w, h, w * h * 4))
            else:
                print('%s: %r' % (argv[1], parse_toc(data)))
        elif cmd == 'encode' and len(argv) == 4:
            toc, gpu = encode(argv[1])
            with open(argv[2], 'wb') as f:
                f.write(toc)
            with open(argv[3], 'wb') as f:
                f.write(gpu)
        elif cmd == 'decode' and len(argv) == 4:
            with open(argv[1], 'rb') as f:
                toc = f.read()
            with open(argv[2], 'rb') as f:
                gpu = f.read()
            with open(argv[3], 'wb') as f:
                f.write(decode_png(toc, gpu))
        elif cmd == 'selftest':
            print('ok: %d PNG -> texture -> PNG round trips are lossless' % selftest())
        else:
            print(__doc__)
            return 2
    except TextureError as e:
        print('error: %s' % e)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(_main(sys.argv[1:]))
