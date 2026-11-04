import socket
import sqlite3
import sys
import pytest
from app.store import Store,fingerprint
from scripts import setup_central,run_central


def test_setup_creates_blank_real_ledger_and_viewer_then_preserves_data(tmp_path,monkeypatch):
    root=tmp_path/'central';monkeypatch.setattr(sys,'argv',['setup','--data',str(root)])
    secrets=iter(['Central-admin-test-pass','Central-admin-test-pass','Central-viewer-test-pass','Central-viewer-test-pass'])
    prompts=iter(['y','viewer'])
    monkeypatch.setattr(setup_central.getpass,'getpass',lambda *a:next(secrets))
    monkeypatch.setattr('builtins.input',lambda *a:next(prompts))
    setup_central.main()
    data=Store(root,read_only=True).read()
    assert not data['Events'] and not data['Parties']
    assert next(r['value'] for r in data['Info'] if r['key']=='mode')=='خالی'
    with sqlite3.connect(root/'auth.sqlite3') as db:
        assert db.execute('SELECT name,role FROM users ORDER BY name').fetchall()==[('admin','admin'),('viewer','viewer')]
    hashes=(fingerprint(root/'Mazandasht.xlsx'),fingerprint(root/'auth.sqlite3'))
    setup_central.main()  # no additional prompt or password reset
    assert hashes==(fingerprint(root/'Mazandasht.xlsx'),fingerprint(root/'auth.sqlite3'))


def test_setup_rejects_demo_before_creating_users(tmp_path,monkeypatch):
    store=Store(tmp_path,demo=True);before=fingerprint(store.path)
    monkeypatch.setattr(sys,'argv',['setup','--data',str(tmp_path)])
    with pytest.raises(SystemExit,match='Synthetic'):setup_central.main()
    assert not (tmp_path/'auth.sqlite3').exists() and before==fingerprint(store.path)


def test_launcher_refuses_missing_install_without_bootstrap(tmp_path,monkeypatch):
    root=tmp_path/'missing';monkeypatch.setattr(sys,'argv',['start','--data',str(root)])
    with pytest.raises(SystemExit,match='First run'):run_central.main()
    assert not root.exists()


def test_launcher_port_collision_does_not_kill_service():
    with socket.socket() as occupied:
        occupied.bind(('127.0.0.1',0));occupied.listen()
        port=occupied.getsockname()[1]
        with pytest.raises(SystemExit,match='occupied'):run_central.available('127.0.0.1',port)
        assert occupied.fileno()!=-1
