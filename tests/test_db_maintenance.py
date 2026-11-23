"""Manutenção destrutiva dos bancos locais."""

from src.db.maintenance import delete_local_databases, local_database_files


def test_local_database_files_lists_active_backups_and_sync(tmp_path):
    data = tmp_path / 'data'
    data.mkdir()
    for name in (
        'hupomnemata.db',
        'hupomnemata.db-wal',
        'hupomnemata_conflict_20260101.db',
    ):
        (data / name).write_bytes(b'x')
    (data / 'backups').mkdir()
    (data / 'backups' / 'antigo.db').write_bytes(b'x')
    (data / 'sync').mkdir()
    (data / 'sync' / 'snapshot.db.gz').write_bytes(b'x')
    (data / 'sync' / 'last_synced_hash.txt').write_text('hash')

    files = {path.name for path in local_database_files(data)}
    assert 'hupomnemata.db' in files
    assert 'hupomnemata.db-wal' in files
    assert 'hupomnemata_conflict_20260101.db' in files
    assert 'antigo.db' in files
    assert 'snapshot.db.gz' in files
    assert 'last_synced_hash.txt' in files


def test_delete_local_databases_preserves_pdfs_and_preferences(tmp_path):
    data = tmp_path / 'data'
    data.mkdir()
    (data / 'hupomnemata.db').write_bytes(b'x')
    (data / 'hupomnemata.db-wal').write_bytes(b'x')
    (data / 'hupomnemata_conflict_20260101.db').write_bytes(b'x')
    (data / 'backups').mkdir()
    (data / 'backups' / 'antigo.db').write_bytes(b'x')
    (data / 'sync').mkdir()
    (data / 'sync' / 'snapshot.db.gz').write_bytes(b'x')
    (data / 'sync' / 'last_synced_hash.txt').write_text('hash')
    (data / 'pdfs').mkdir()
    (data / 'pdfs' / 'obra.pdf').write_bytes(b'pdf')
    (data / 'user_preferences.json').write_text('{}')

    removed = delete_local_databases(data, dispose_engine=False)

    assert not (data / 'hupomnemata.db').exists()
    assert not (data / 'hupomnemata.db-wal').exists()
    assert not (data / 'hupomnemata_conflict_20260101.db').exists()
    assert not (data / 'backups' / 'antigo.db').exists()
    assert not (data / 'sync' / 'snapshot.db.gz').exists()
    assert not (data / 'sync' / 'last_synced_hash.txt').exists()
    assert (data / 'pdfs' / 'obra.pdf').exists()
    assert (data / 'user_preferences.json').exists()
    assert all(path.name != 'obra.pdf' for path in removed)
