from pathlib import Path
import pytest
from backend.parsers.audio import analyze
from backend.mutation.engine import MutationError, generate

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
