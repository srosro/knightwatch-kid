from unittest.mock import patch

from keepitdry.indexer import discover_python_files, FileHashTracker, Indexer


def test_discover_python_files(tmp_path):
    (tmp_path / "a.py").write_text("x = 1")
    (tmp_path / "b.py").write_text("y = 2")
    (tmp_path / "readme.md").write_text("# hi")

    files = discover_python_files(tmp_path)

    assert len(files) == 2
    names = [f.name for f in files]
    assert "a.py" in names
    assert "b.py" in names
    assert "readme.md" not in names


def test_discover_skips_excluded_dirs(tmp_path):
    (tmp_path / "good.py").write_text("x = 1")

    for d in ["__pycache__", ".venv", "node_modules", ".keepitdry"]:
        excluded = tmp_path / d
        excluded.mkdir()
        (excluded / "skip.py").write_text("z = 3")

    files = discover_python_files(tmp_path)

    assert len(files) == 1
    assert files[0].name == "good.py"


def test_discover_nested_files(tmp_path):
    sub = tmp_path / "pkg" / "sub"
    sub.mkdir(parents=True)
    (sub / "deep.py").write_text("x = 1")
    (tmp_path / "top.py").write_text("y = 2")

    files = discover_python_files(tmp_path)

    assert len(files) == 2
    names = [str(f.relative_to(tmp_path)) for f in files]
    assert "top.py" in names
    assert "pkg/sub/deep.py" in names


def test_hash_tracker_detects_new_files(tmp_path):
    tracker = FileHashTracker(
        tmp_path / ".keepitdry" / "file_hashes.json", project_root=tmp_path
    )
    f = tmp_path / "new.py"
    f.write_text("x = 1")

    assert tracker.has_changed(f)


def test_hash_tracker_detects_unchanged(tmp_path):
    tracker = FileHashTracker(
        tmp_path / ".keepitdry" / "file_hashes.json", project_root=tmp_path
    )
    f = tmp_path / "stable.py"
    f.write_text("x = 1")

    tracker.update(f)
    tracker.save()

    tracker2 = FileHashTracker(
        tmp_path / ".keepitdry" / "file_hashes.json", project_root=tmp_path
    )
    assert not tracker2.has_changed(f)


def test_hash_tracker_detects_modified(tmp_path):
    tracker = FileHashTracker(
        tmp_path / ".keepitdry" / "file_hashes.json", project_root=tmp_path
    )
    f = tmp_path / "mod.py"
    f.write_text("x = 1")
    tracker.update(f)
    tracker.save()

    f.write_text("x = 2")

    tracker2 = FileHashTracker(
        tmp_path / ".keepitdry" / "file_hashes.json", project_root=tmp_path
    )
    assert tracker2.has_changed(f)


def test_hash_tracker_stale_files(tmp_path):
    tracker = FileHashTracker(
        tmp_path / ".keepitdry" / "file_hashes.json", project_root=tmp_path
    )

    f1 = tmp_path / "keep.py"
    f1.write_text("x = 1")
    f2 = tmp_path / "delete.py"
    f2.write_text("y = 2")

    tracker.update(f1)
    tracker.update(f2)
    tracker.save()

    # Keys are relative paths now
    current_keys = {"keep.py"}
    stale = tracker.stale_files(current_keys)

    assert "delete.py" in stale
    assert "keep.py" not in stale


def test_indexer_indexes_project(tmp_path, fake_embed):
    (tmp_path / "app.py").write_text(
        "def hello():\n    return 'hi'\n"
    )

    with patch("keepitdry.indexer.embed_module.batch_embed") as mock_embed:
        mock_embed.side_effect = lambda texts: [fake_embed(t) for t in texts]

        indexer = Indexer(tmp_path)
        stats = indexer.index()

    assert stats["files_indexed"] == 1
    assert stats["elements_indexed"] > 0


def test_indexer_incremental_skip(tmp_path, fake_embed):
    (tmp_path / "app.py").write_text("def hello():\n    return 'hi'\n")

    with patch("keepitdry.indexer.embed_module.batch_embed") as mock_embed:
        mock_embed.side_effect = lambda texts: [fake_embed(t) for t in texts]

        indexer = Indexer(tmp_path)
        indexer.index()

        mock_embed.reset_mock()
        stats = indexer.index()

    assert stats["files_indexed"] == 0
    assert stats["files_skipped"] == 1


def test_indexer_removes_stale_entries(tmp_path, fake_embed):
    f = tmp_path / "old.py"
    f.write_text("def old_func():\n    pass\n")

    with patch("keepitdry.indexer.embed_module.batch_embed") as mock_embed:
        mock_embed.side_effect = lambda texts: [fake_embed(t) for t in texts]

        indexer = Indexer(tmp_path)
        indexer.index()
        assert indexer.store.count() > 0

        f.unlink()
        stats = indexer.index()

    assert stats["stale_removed"] > 0
    assert indexer.store.count() == 0


def test_indexer_clear(tmp_path, fake_embed):
    (tmp_path / "app.py").write_text("x = 1\n")

    with patch("keepitdry.indexer.embed_module.batch_embed") as mock_embed:
        mock_embed.side_effect = lambda texts: [fake_embed(t) for t in texts]

        indexer = Indexer(tmp_path)
        indexer.index()
        assert indexer.store.count() > 0

        indexer.clear()

    assert indexer.store.count() == 0
