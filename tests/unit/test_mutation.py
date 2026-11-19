from pathlib import Path
import pytest
from backend.parsers.audio import analyze
from backend.mutation.engine import MutationError, generate, generate_batch, STRATEGIES, BOUNDARY_STRATEGIES

FIX = Path(__file__).parents[1] / 'fixtures' / 'reference.wav'


def test_deterministic_strategies_and_exact_edit_offsets():
    data=FIX.read_bytes(); analysis=analyze(FIX,FIX.name)
    strategies=['header_boundary','chunk_length','truncation','duplicate_metadata','metadata_value','signature','trailing','chunk_order','seeded_bytes']
    for index,strategy in enumerate(strategies):
        first,history=generate(data,analysis,strategy,123,index)
        second,again=generate(data,analysis,strategy,123,index)
        assert first == second and history == again and first != data
        assert history['edits'] and all(0 <= edit['offset'] <= len(data) for edit in history['edits'])
        assert all(edit['before_sha256'] and edit['after_sha256'] for edit in history['edits'])
    assert FIX.read_bytes() == data


def test_limits_and_inapplicable_strategies():
    data=FIX.read_bytes(); analysis=analyze(FIX,FIX.name)
    with pytest.raises(MutationError): generate(data,analysis,'trailing',1,0,limit=len(data))
    with pytest.raises(MutationError): generate(data,analysis,'invalid_encoding',1,0)
    with pytest.raises(MutationError): generate(data,analysis,'seeded_bytes',1,0,region='not-a-region')


def test_duplicate_metadata_produces_real_duplicate(tmp_path):
    original=FIX.read_bytes(); analysis=analyze(FIX,FIX.name)
    variant,_=generate(original,analysis,'duplicate_metadata',5,0)
    path=tmp_path/'variant.wav';path.write_bytes(variant)
    result=analyze(path,path.name)
    assert any(h['kind']=='Duplicate metadata' for h in result['heuristics'])


def test_invalid_id3_encoding_marker(tmp_path):
    import struct
    # A complete ID3v2.3 text frame and a minimal MPEG-looking payload.
    frame=b'TIT2'+struct.pack('>I',5)+b'\0\0'+b'\x03text'
    tag=b'ID3\x03\0\0'+bytes([0,0,0,len(frame)])+frame+b'\xff\xfb\x90\x64'+bytes(100)
    path=tmp_path/'tag.mp3';path.write_bytes(tag)
    analysis=analyze(path,path.name)
    mutated,history=generate(tag,analysis,'invalid_encoding',9,0)
    output=tmp_path/'invalid.mp3';output.write_bytes(mutated)
    result=analyze(output,output.name)
    assert history['edits'][0]['offset']==20
    assert any(h['kind']=='Invalid ID3 text encoding marker' for h in result['heuristics'])


def test_metadata_size_is_bounded_and_reproducible(tmp_path):
    data=FIX.read_bytes(); analysis=analyze(FIX,FIX.name); lengths=set()
    for seed in range(20):
        variant,history=generate(data,analysis,'metadata_value',seed,0,metadata_size=8192)
        path=tmp_path/f'{seed}.wav';path.write_bytes(variant)
        result=analyze(path,path.name)
        field=next(m for m in result['metadata'] if m['key']=='INAM')
        lengths.add(field['byte_length'])
        assert history['metadata_size']==8192
    assert lengths=={0,8192}


# --- v0.2.0 mutation engine tests ---

def test_boundary_strategies_are_available():
    """All boundary-value strategies should be in the strategy list."""
    for strategy in ('boundary_min', 'boundary_max', 'boundary_off_by_one',
                     'zero_length_field', 'max_syncsafe', 'negative_duration'):
        assert strategy in STRATEGIES


def test_boundary_min_produces_valid_mutation():
    data = FIX.read_bytes(); analysis = analyze(FIX, FIX.name)
    mutated, history = generate(data, analysis, 'boundary_min', 42, 0)
    assert mutated != data
    assert history['strategy'] == 'boundary_min'
    assert history['edits']
    assert history['original_sha256'] == history['reproduction_inputs']['original_sha256']


def test_boundary_max_inflates_container():
    data = FIX.read_bytes(); analysis = analyze(FIX, FIX.name)
    mutated, history = generate(data, analysis, 'boundary_max', 42, 0)
    assert mutated != data
    # Container size at offset 4 should be larger than original
    assert int.from_bytes(mutated[4:8], 'little') > int.from_bytes(data[4:8], 'little')


def test_boundary_off_by_one():
    data = FIX.read_bytes(); analysis = analyze(FIX, FIX.name)
    mutated, history = generate(data, analysis, 'boundary_off_by_one', 42, 0)
    assert mutated != data
    assert history['edits'][0]['description'].endswith('(off-by-one)')


def test_zero_length_field_strategy():
    data = FIX.read_bytes(); analysis = analyze(FIX, FIX.name)
    mutated, history = generate(data, analysis, 'zero_length_field', 42, 0)
    assert mutated != data
    # The fmt chunk size should be zero
    fmt_offset = data.find(b'fmt ')
    assert fmt_offset >= 0
    assert int.from_bytes(mutated[fmt_offset+4:fmt_offset+8], 'little') == 0


def test_negative_duration_strategy():
    data = FIX.read_bytes(); analysis = analyze(FIX, FIX.name)
    mutated, history = generate(data, analysis, 'negative_duration', 42, 0)
    assert mutated != data
    # WAV: sample rate should be zero
    fmt_offset = data.find(b'fmt ')
    assert fmt_offset >= 0
    assert int.from_bytes(mutated[fmt_offset+16:fmt_offset+20], 'little') == 0
    # AIFF: numSampleFrames begins two bytes into the COMM body, after channels.
    aiff = Path(__file__).parents[1] / 'fixtures' / 'reference.aiff'
    aiff_data = aiff.read_bytes(); aiff_analysis = analyze(aiff, aiff.name)
    aiff_mutated, _ = generate(aiff_data, aiff_analysis, 'negative_duration', 42, 0)
    comm = next(c for c in aiff_analysis['chunks'] if c['name'] == 'COMM')
    frames = aiff_mutated[comm['offset']+10:comm['offset']+14]
    assert frames == b'\x00\x00\x00\x00'
    assert aiff_mutated != aiff_data


def test_boundary_strategies_fail_gracefully_on_mp3(tmp_path):
    """Boundary strategies that need WAV structure should raise MutationError for MP3."""
    import struct
    frame = b'TIT2' + struct.pack('>I', 5) + b'\0\0' + b'\x03text'
    tag = b'ID3\x03\0\0' + bytes([0,0,0,len(frame)]) + frame + b'\xff\xfb\x90\x64' + bytes(100)
    # Write to a real temp file so analyze() can read it
    mp3_path = tmp_path / 'test.mp3'
    mp3_path.write_bytes(tag)
    analysis = analyze(mp3_path, mp3_path.name)
    assert analysis['format'] == 'MP3'
    # boundary_min, boundary_max require WAV/AIFF/FLAC chunks
    with pytest.raises(MutationError):
        generate(tag, analysis, 'boundary_min', 1, 0)
    with pytest.raises(MutationError):
        generate(tag, analysis, 'boundary_max', 1, 0)
    # zero_length_field works with MP3 (sets ID3 tag size to zero), but boundary_off_by_one needs WAV
    with pytest.raises(MutationError):
        generate(tag, analysis, 'boundary_off_by_one', 1, 0)
    # negative_duration needs WAV/AIFF format
    with pytest.raises(MutationError):
        generate(tag, analysis, 'negative_duration', 1, 0)


def test_generate_batch_deduplication():
    """Batch generation with deduplication should skip duplicate hashes."""
    data = FIX.read_bytes(); analysis = analyze(FIX, FIX.name)
    # Use a single strategy that's deterministic: same seed + index always produces same output
    results = generate_batch(data, analysis, 5, 42, ['signature'], deduplicate=True)
    # signature always replaces first 4 bytes with 'XROT' — all 5 would be identical
    assert len(results) == 1  # Only the first one survives dedup


def test_generate_batch_without_deduplication():
    """Without deduplication, all requested mutations are produced."""
    data = FIX.read_bytes(); analysis = analyze(FIX, FIX.name)
    results = generate_batch(data, analysis, 3, 42, ['signature'], deduplicate=False)
    assert len(results) == 3


def test_generate_batch_mixed_strategies():
    """Mixed strategies should cycle correctly."""
    data = FIX.read_bytes(); analysis = analyze(FIX, FIX.name)
    results = generate_batch(data, analysis, 6, 42, ['header_boundary', 'truncation'], deduplicate=False)
    assert len(results) == 6
    strategies_used = [h['strategy'] for _, h in results]
    assert strategies_used == ['header_boundary', 'truncation', 'header_boundary', 'truncation', 'header_boundary', 'truncation']


def test_mutation_history_contains_reproduction_inputs():
    """Every mutation history must contain enough information to reproduce."""
    data = FIX.read_bytes(); analysis = analyze(FIX, FIX.name)
    mutated, history = generate(data, analysis, 'header_boundary', 7, 3)
    assert 'reproduction_inputs' in history
    ri = history['reproduction_inputs']
    assert ri['seed'] == 7
    assert ri['strategy'] == 'header_boundary'
    assert ri['index'] == 3
    assert ri['original_sha256'] == history['original_sha256']
    # Verify reproducibility using the recorded inputs
    replay, replay_history = generate(data, analysis, ri['strategy'], ri['seed'], ri['index'],
                                       ri['size_limit'], ri['region'], ri['metadata_size'])
    assert replay == mutated


def test_original_file_preserved():
    """Mutation must never modify the original bytes."""
    original = FIX.read_bytes()
    original_hash = original.hex()
    analysis = analyze(FIX, FIX.name)
    for i, strategy in enumerate(['header_boundary', 'chunk_length', 'truncation', 'signature', 'trailing']):
        generate(original, analysis, strategy, 99, i)
    assert FIX.read_bytes().hex() == original_hash
