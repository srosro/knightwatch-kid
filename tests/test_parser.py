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


def test_parse_class_and_methods(tmp_path):
    f = tmp_path / "calc.py"
    f.write_text(
        'class Calculator:\n'
        '    """A calculator."""\n'
        '\n'
        '    def add(self, a: int, b: int) -> int:\n'
        '        return a + b\n'
        '\n'
        '    def subtract(self, a: int, b: int) -> int:\n'
        '        return a - b\n'
    )

    elements = parse_file(f, project_root=tmp_path)

    types = {e.element_type for e in elements}
    assert "class" in types
    assert "method" in types

    cls = [e for e in elements if e.element_type == "class"][0]
    assert cls.element_name == "Calculator"
    assert cls.docstring == "A calculator."
    assert cls.parent_chain == "calc.py"
    assert "class Calculator" in cls.signature

    methods = [e for e in elements if e.element_type == "method"]
    assert len(methods) == 2
    assert methods[0].element_name == "Calculator.add"
    assert methods[0].parent_chain == "calc.py > Calculator"
    assert methods[1].element_name == "Calculator.subtract"


def test_parse_decorated_class(tmp_path):
    f = tmp_path / "decorated.py"
    f.write_text(
        "from dataclasses import dataclass\n\n"
        "@dataclass\n"
        "class Point:\n"
        "    x: float\n"
        "    y: float\n"
    )

    elements = parse_file(f, project_root=tmp_path)

    classes = [e for e in elements if e.element_type == "class"]
    assert len(classes) == 1
    assert classes[0].element_name == "Point"


def test_parse_module_variables(tmp_path):
    f = tmp_path / "config.py"
    f.write_text(
        'MAX_RETRIES = 3\n'
        'DEFAULT_TIMEOUT: int = 30\n'
        'API_URL = "https://example.com"\n'
    )

    elements = parse_file(f, project_root=tmp_path)

    assert len(elements) == 3
    assert all(e.element_type == "variable" for e in elements)
    names = [e.element_name for e in elements]
    assert "MAX_RETRIES" in names
    assert "DEFAULT_TIMEOUT" in names
    assert "API_URL" in names

    max_r = [e for e in elements if e.element_name == "MAX_RETRIES"][0]
    assert max_r.signature == "MAX_RETRIES = 3"
    assert max_r.parent_chain == "config.py"


def test_parse_full_file(tmp_path):
    """Test parsing a file with functions, classes, and variables."""
    f = tmp_path / "mixed.py"
    f.write_text(
        'VERSION = "1.0"\n'
        '\n'
        'def helper():\n'
        '    pass\n'
        '\n'
        'class Service:\n'
        '    def run(self):\n'
        '        pass\n'
    )

    elements = parse_file(f, project_root=tmp_path)

    types = [e.element_type for e in elements]
    assert "variable" in types
    assert "function" in types
    assert "class" in types
    assert "method" in types
    assert len(elements) == 4
