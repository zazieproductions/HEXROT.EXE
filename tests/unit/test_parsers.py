from pathlib import Path
import hashlib
import shutil
import subprocess
import pytest
from backend.parsers.audio import analyze

FIX = Path(__file__).parents[1] / 'fixtures'


def test_reference_wav_real_structure_and_hash():
    p = FIX/'reference.wav'; result = analyze(p,p.name)
    assert result['sha256'] == hashlib.sha256(p.read_bytes()).hexdigest()
    assert result['format'] == 'WAV' and result['size'] == p.stat().st_size
    assert [c['name'] for c in result['chunks']] == ['RIFF','fmt ','LIST','data']
    assert result['facts']['sample_rate'] == 8000 and result['facts']['channels'] == 1
    assert result['facts']['bit_depth'] == 16 and result['facts']['duration'] == .25
    data_chunk=next(c for c in result['chunks'] if c['name']=='data')
    assert data_chunk['audio_offset']==data_chunk['offset']+8
    assert any(m['key']=='INAM' and m['value']=='HEXROT reference' for m in result['metadata'])
    assert not result['warnings']
    for chunk in result['chunks']:
        assert 0 <= chunk['offset'] < chunk['end'] <= p.stat().st_size


def test_fixture_structural_observations():
    def analysis(name): return analyze(FIX/name,name)
    assert analysis('reference.aiff')['facts']['sample_rate'] == 8000
    assert any('declares' in w['message'] for w in analysis('inconsistent_length.wav')['warnings'])
    assert any('declares' in w['message'] for w in analysis('truncated.wav')['warnings'])
    assert analysis('extension_mismatch.mp3')['extension_mismatch']
    assert any(h['kind']=='Duplicate metadata' for h in analysis('duplicate_info.wav')['heuristics'])
    assert analysis('trailing_bytes.wav')['trailing_bytes'] == len(b'HEXROT-TRAILING-BYTES')


@pytest.mark.skipif(shutil.which('ffmpeg') is None,reason='ffmpeg not installed')
def test_generated_flac_and_mp3_metadata(tmp_path):
    from mutagen.id3 import APIC, ID3, TIT2
    for extension in ('flac','mp3'):
        target=tmp_path/f'sample.{extension}'
        subprocess.run(['ffmpeg','-v','error','-y','-i',str(FIX/'reference.wav'),str(target)],check=True)
        if extension=='mp3':
            tags=ID3(target)
            tags.add(TIT2(encoding=3,text=['Real title']))
            tags.add(APIC(encoding=3,mime='image/png',type=3,desc='fixture',data=b'harmless-image-bytes'))
            tags.save(target)
        result=analyze(target,target.name)
        assert result['format'] == extension.upper()
        assert result['facts']['sample_rate'] == 8000
        assert result['chunks']
        if extension=='mp3':
            assert any('Real title' in m['value'] for m in result['metadata'])
            assert result['artwork'][0]['sha256'] == hashlib.sha256(b'harmless-image-bytes').hexdigest()


def test_untrusted_metadata_is_text_only(tmp_path):
    raw=(FIX/'reference.wav').read_bytes().replace(b'HEXROT reference',b'<script>alert(1)')
    path=tmp_path/'hostile.wav';path.write_bytes(raw)
    result=analyze(path,path.name)
    assert any('<script>' in item['value'] for item in result['metadata'])


# --- Malformed input resilience tests (v0.2.0) ---

def test_empty_file_does_not_crash_parser(tmp_path):
    """A zero-length file must not cause an exception or hang."""
    path = tmp_path / 'empty.wav'
    path.write_bytes(b'')
    result = analyze(path, path.name)
    assert result['size'] == 0
    assert result['format'] == 'Unknown'
    assert result['chunks'] == [] or all(0 <= c['offset'] for c in result['chunks'])


def test_truncated_wav_header(tmp_path):
    """A file with RIFF header but truncated body should produce a warning, not a crash."""
    # 14 bytes: RIFF + size + WAVE + 2 bytes of first chunk header (truncated)
    path = tmp_path / 'short.wav'
    path.write_bytes(b'RIFF\x20\x00\x00\x00WAVEfm')  # 14 bytes, fmt chunk header truncated
    result = analyze(path, path.name)
    assert result['format'] == 'WAV'
    assert any('truncated' in w['message'].lower() or 'unparsed' in w['message'].lower()
               or 'declares' in w['message'] for w in result['warnings'])


def test_zero_length_chunk_declared(tmp_path):
    """A chunk declaring zero bytes of body should be handled safely."""
    original = bytearray((FIX/'reference.wav').read_bytes())
    # Set the fmt chunk body size to 0 while keeping the chunk header
    # RIFF header at 0-7, WAVE at 8-11, fmt chunk header at 12-15, size at 16-19
    original[16:20] = b'\x00\x00\x00\x00'
    path = tmp_path / 'zero_fmt.wav'
    path.write_bytes(bytes(original))
    result = analyze(path, path.name)
    assert result['format'] == 'WAV'
    # Should not crash; fmt facts may be absent since the declared size is 0
    assert result['chunks']


def test_oversized_declared_chunk_length(tmp_path):
    """A chunk declaring more bytes than the file contains must not cause OOM."""
    original = bytearray((FIX/'reference.wav').read_bytes())
    # Set the data chunk declared size to something larger than the file
    # Find the data chunk - it's typically the last chunk
    # For our fixture: RIFF(0-11), fmt(12-59), LIST(60-...), data(last chunk)
    # The data chunk header is at some offset; set its size to 0xFFFFFFFF
    data_offset = original.find(b'data')
    assert data_offset >= 0
    original[data_offset+4:data_offset+8] = b'\xff\xff\xff\xff'
    path = tmp_path / 'oversized.wav'
    path.write_bytes(bytes(original))
    result = analyze(path, path.name)
    assert result['format'] == 'WAV'
    assert any('declares' in w['message'] and 'only' in w['message'] for w in result['warnings'])


def test_duplicate_chunk_ids(tmp_path):
    """Two chunks with the same ID should both be parsed without confusion."""
    original = (FIX/'reference.wav').read_bytes()
    # Duplicate the entire data chunk by appending it
    data_offset = original.find(b'data')
    assert data_offset >= 0
    data_chunk = original[data_offset:]
    # Build a file with the data chunk appearing twice
    modified = bytearray(original[:data_offset])
    modified.extend(data_chunk)
    modified.extend(data_chunk)
    # Update RIFF container size
    import struct
    riff_size = len(modified) - 8
    struct.pack_into('<I', modified, 4, riff_size)
    path = tmp_path / 'dup_chunks.wav'
    path.write_bytes(bytes(modified))
    result = analyze(path, path.name)
    data_chunks = [c for c in result['chunks'] if c['name'] == 'data']
    assert len(data_chunks) >= 2


def test_malformed_text_encoding_in_metadata(tmp_path):
    """Non-UTF-8 bytes in metadata values must not crash the parser."""
    original = (FIX/'reference.wav').read_bytes()
    # Replace the metadata text with invalid UTF-8
    hostile = original.replace(b'HEXROT reference', b'\xff\xfe\x80\x81\x82\x83reference')
    path = tmp_path / 'bad_encoding.wav'
    path.write_bytes(hostile)
    result = analyze(path, path.name)
    # Should parse without crashing; metadata values are text-safe
    assert result['format'] == 'WAV'
    assert result['metadata']  # metadata fields should still be extracted


def test_extension_signature_mismatch(tmp_path):
    """A file whose signature doesn't match its extension should be flagged."""
    # The fixture extension_mismatch.mp3 is actually a WAV inside a .mp3 extension
    original = (FIX/'extension_mismatch.mp3').read_bytes()
    path = tmp_path / 'fake.mp3'
    path.write_bytes(original)
    result = analyze(path, path.name)
    # The file starts with RIFF/WAVE but has .mp3 extension
    assert result['format'] == 'WAV'
    assert result['extension_mismatch'] is True
    # Also test the reverse: MP3-like data in a .wav file
    import struct
    frame = b'TIT2' + struct.pack('>I', 5) + b'\x00\x00' + b'\x03text'
    mp3_data = b'ID3\x03\x00\x00' + bytes([0,0,0,len(frame)]) + frame + b'\xff\xfb\x90\x64' + bytes(100)
    path2 = tmp_path / 'fake.wav'
    path2.write_bytes(mp3_data)
    result2 = analyze(path2, path2.name)
    assert result2['format'] == 'MP3'
    assert result2['extension_mismatch'] is True


def test_zero_length_container_size(tmp_path):
    """A RIFF container with size=0 should be handled."""
    original = bytearray((FIX/'reference.wav').read_bytes())
    original[4:8] = b'\x00\x00\x00\x00'
    path = tmp_path / 'zero_container.wav'
    path.write_bytes(bytes(original))
    result = analyze(path, path.name)
    assert result['format'] == 'WAV'
    # Should not crash; chunks may be empty since container size is 0


def test_garbage_bytes_not_audio(tmp_path):
    """Random bytes that don't match any known format should be handled."""
    import random
    rng = random.Random(42)
    garbage = bytes(rng.randrange(256) for _ in range(1024))
    path = tmp_path / 'garbage.bin'
    path.write_bytes(garbage)
    result = analyze(path, path.name)
    assert result['format'] == 'Unknown'
    assert result['size'] == 1024


def test_truncated_flac_metadata(tmp_path):
    """A FLAC file truncated inside a metadata block should produce a warning."""
    # Minimal FLAC header + truncated STREAMINFO
    data = b'fLaC' + b'\x00\x00\x00\x10' + b'\x00' * 10  # claims 16 bytes but only 10 available
    path = tmp_path / 'truncated.flac'
    path.write_bytes(data)
    result = analyze(path, path.name)
    assert result['format'] == 'FLAC'
    assert any(w['severity'] in ('warning', 'error') for w in result['warnings'])


def test_single_byte_file(tmp_path):
    """A one-byte file should not crash any parser branch."""
    path = tmp_path / 'one.bin'
    path.write_bytes(b'X')
    result = analyze(path, path.name)
    assert result['size'] == 1
    assert result['format'] == 'Unknown'
