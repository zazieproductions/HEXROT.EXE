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
