from keepitdry.indexer import discover_python_files, FileHashTracker


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
    tracker = FileHashTracker(tmp_path / ".keepitdry" / "file_hashes.json")
    f = tmp_path / "new.py"
    f.write_text("x = 1")

    assert tracker.has_changed(f)


def test_hash_tracker_detects_unchanged(tmp_path):
    tracker = FileHashTracker(tmp_path / ".keepitdry" / "file_hashes.json")
    f = tmp_path / "stable.py"
    f.write_text("x = 1")

    tracker.update(f)
    tracker.save()

    tracker2 = FileHashTracker(tmp_path / ".keepitdry" / "file_hashes.json")
    assert not tracker2.has_changed(f)


def test_hash_tracker_detects_modified(tmp_path):
    tracker = FileHashTracker(tmp_path / ".keepitdry" / "file_hashes.json")
    f = tmp_path / "mod.py"
    f.write_text("x = 1")
    tracker.update(f)
    tracker.save()

    f.write_text("x = 2")

    tracker2 = FileHashTracker(tmp_path / ".keepitdry" / "file_hashes.json")
    assert tracker2.has_changed(f)


def test_hash_tracker_stale_files(tmp_path):
    tracker = FileHashTracker(tmp_path / ".keepitdry" / "file_hashes.json")

    f1 = tmp_path / "keep.py"
    f1.write_text("x = 1")
    f2 = tmp_path / "delete.py"
    f2.write_text("y = 2")

    tracker.update(f1)
    tracker.update(f2)
    tracker.save()

    current_files = {str(f1)}
    stale = tracker.stale_files(current_files)

    assert str(f2) in stale
    assert str(f1) not in stale
