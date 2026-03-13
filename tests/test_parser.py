from keepitdry.parser import CodeElement, parse_file


def test_parse_simple_function(tmp_path):
    f = tmp_path / "example.py"
    f.write_text(
        'def greet(name: str) -> str:\n'
        '    """Say hello."""\n'
        '    return f"Hello, {name}"\n'
    )

    elements = parse_file(f, project_root=tmp_path)

    assert len(elements) == 1
    el = elements[0]
    assert isinstance(el, CodeElement)
    assert el.element_name == "greet"
    assert el.element_type == "function"
    assert el.file_path == "example.py"
    assert "name: str" in el.signature
    assert "-> str" in el.signature
    assert el.docstring == "Say hello."
    assert 'return f"Hello, {name}"' in el.code_body
    assert el.line_number == 1
    assert el.parent_chain == "example.py"


def test_parse_function_no_docstring(tmp_path):
    f = tmp_path / "nodoc.py"
    f.write_text("def add(a, b):\n    return a + b\n")

    elements = parse_file(f, project_root=tmp_path)

    assert len(elements) == 1
    assert elements[0].docstring is None
    assert elements[0].element_name == "add"


def test_parse_multiple_functions(tmp_path):
    f = tmp_path / "multi.py"
    f.write_text(
        "def foo():\n    pass\n\n"
        "def bar():\n    pass\n"
    )

    elements = parse_file(f, project_root=tmp_path)

    assert len(elements) == 2
    names = [e.element_name for e in elements]
    assert names == ["foo", "bar"]
