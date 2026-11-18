import json
import socket
import subprocess
from pathlib import Path
import pytest
from backend.workers.isolation import isolated_command, isolation_status
from backend.workers.runner import execute
from backend.decoders.adapters import inventory

FIX = Path(__file__).parents[1]/'fixtures'/'reference.wav'
pytestmark = pytest.mark.skipif(not isolation_status()['available'],reason='OS sandbox unavailable')


def test_decoder_real_results_and_output_hash():
    tools={x['id'] for x in inventory() if x['available']}
    if 'ffmpeg' not in tools: pytest.skip('ffmpeg not installed')
    result=execute(FIX.resolve(),'ffmpeg',5,512)
    assert result['accepted'] and result['exit_code']==0 and result['output_sha256']
    assert result['invocation'][0].endswith('ffmpeg') and result['duration_seconds']>0
    assert result['infrastructure_error'] is None


def test_supervisor_distinguishes_signal_and_exit_code():
    if not Path('/bin/bash').exists(): pytest.skip('Linux diagnostic')
    for command, expected in [(['/bin/bash','-c','kill -SEGV $$'],-11),(['/bin/bash','-c','exit 139'],139)]:
        actual,_=isolated_command(FIX.resolve(),command)
        result=subprocess.run(actual,capture_output=True,text=True,timeout=5)
        assert json.loads(result.stdout)['returncode']==expected


def test_no_host_home_or_host_loopback_access(tmp_path):
    if not Path('/usr/bin/python3').exists(): pytest.skip('Linux diagnostic')
    secret=tmp_path/'private.txt';secret.write_text('private')
    listener=socket.socket(); listener.bind(('127.0.0.1',0));listener.listen()
    try:
        port=listener.getsockname()[1]
        code=("import pathlib,socket; "
              f"p=pathlib.Path({str(secret)!r}); print('readable',p.exists()); "
              "s=socket.socket();s.settimeout(.25); "
              f"print('connect',s.connect_ex(('127.0.0.1',{port})))")
        actual,_=isolated_command(FIX.resolve(),['/usr/bin/python3','-c',code])
        result=subprocess.run(actual,capture_output=True,text=True,timeout=5)
        payload=json.loads(result.stdout)
        assert payload['returncode']==0
        assert 'readable False' in payload['stdout'] and 'connect 0' not in payload['stdout']
    finally: listener.close()


def test_sndfile_info_zero_exit_can_still_mean_rejection(tmp_path):
    if not any(x['id']=='sndfile-info' and x['available'] for x in inventory()): pytest.skip('sndfile-info not installed')
    path=tmp_path/'invalid.wav';path.write_bytes(b'not an audio file')
    result=execute(path.resolve(),'sndfile-info',5,512)
    assert result['accepted'] is False
    assert 'Not able to open input file' in result['stdout'] or result['exit_code'] != 0
    if result['exit_code'] == 0: assert 'Not able to open input file' in result['stdout']
