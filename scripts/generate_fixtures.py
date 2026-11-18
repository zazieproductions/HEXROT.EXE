"""Generate small, harmless, deterministic audio fixtures without external files."""
from pathlib import Path
import math
import struct

ROOT = Path(__file__).resolve().parents[1] / 'tests' / 'fixtures'


def chunk(name: bytes, body: bytes, endian: str = '<') -> bytes:
    return name + struct.pack(endian + 'I', len(body)) + body + (b'\0' if len(body) & 1 else b'')


def generate() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    rate = 8000
    samples = b''.join(struct.pack('<h', int(5000 * math.sin(2 * math.pi * 440 * i / rate))) for i in range(rate // 4))
    fmt = chunk(b'fmt ', struct.pack('<HHIIHH', 1, 1, rate, rate * 2, 2, 16))
    info = chunk(b'LIST', b'INFO' + chunk(b'INAM', b'HEXROT reference\0') + chunk(b'IART', b'Church of Malware\0') + chunk(b'ICMT', b'Harmless generated fixture\0'))
    data = chunk(b'data', samples)
    body = b'WAVE' + fmt + info + data
    wav = b'RIFF' + struct.pack('<I', len(body)) + body
    (ROOT / 'reference.wav').write_bytes(wav)
    public = ROOT.parents[1] / 'public' / 'fixtures'
    public.mkdir(parents=True, exist_ok=True)
    (public / 'reference.wav').write_bytes(wav)
    # Declared data length exceeds the available bytes.
    bad = bytearray(wav)
    data_offset = wav.index(b'data', 12)
    struct.pack_into('<I', bad, data_offset + 4, len(samples) + 512)
    (ROOT / 'inconsistent_length.wav').write_bytes(bad)
    (ROOT / 'truncated.wav').write_bytes(wav[:-137])
    (ROOT / 'extension_mismatch.mp3').write_bytes(wav)
    dup_info = chunk(b'LIST', b'INFO' + chunk(b'INAM', b'First title\0') + chunk(b'INAM', b'Second title\0'))
    dup_body = b'WAVE' + fmt + dup_info + data
    (ROOT / 'duplicate_info.wav').write_bytes(b'RIFF' + struct.pack('<I', len(dup_body)) + dup_body)
    (ROOT / 'trailing_bytes.wav').write_bytes(wav + b'HEXROT-TRAILING-BYTES')
    # 80-bit extended representation of 8000.0, followed by big-endian PCM.
    extended_8000 = bytes.fromhex('400bfa00000000000000')
    comm = chunk(b'COMM', struct.pack('>hIh', 1, len(samples) // 2, 16) + extended_8000, '>')
    be_samples = b''.join(samples[i:i+2][::-1] for i in range(0, len(samples), 2))
    ssnd = chunk(b'SSND', struct.pack('>II', 0, 0) + be_samples, '>')
    aiff_body = b'AIFF' + comm + chunk(b'NAME', b'HEXROT reference', '>') + ssnd
    (ROOT / 'reference.aiff').write_bytes(b'FORM' + struct.pack('>I', len(aiff_body)) + aiff_body)

if __name__ == '__main__':
    generate()
    print(f'Generated fixtures in {ROOT}')
