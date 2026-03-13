from keepitdry.indexer import discover_python_files


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
