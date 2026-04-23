from keepitdry.swift_parser import parse_swift_file


def test_parse_top_level_function(tmp_path):
    f = tmp_path / "util.swift"
    f.write_text(
        "func greet(name: String) -> String {\n"
        '    return "Hello, \\(name)"\n'
        "}\n"
    )

    elements = parse_swift_file(f, project_root=tmp_path)

    assert len(elements) == 1
    el = elements[0]
    assert el.element_name == "greet"
    assert el.element_type == "function"
    assert el.file_path == "util.swift"
    assert "greet" in el.signature
    assert el.line_number == 1
    assert el.parent_chain == "util.swift"


def test_parse_doc_comment_triple_slash(tmp_path):
    f = tmp_path / "doc.swift"
    f.write_text(
        "/// Returns the user's current status.\n"
        "/// Never `nil` once boot completes.\n"
        "func currentStatus() -> String {\n"
        '    return "ok"\n'
        "}\n"
    )

    elements = parse_swift_file(f, project_root=tmp_path)

    assert len(elements) == 1
    assert "Returns the user's current status." in (elements[0].docstring or "")


def test_parse_struct_with_properties_and_methods(tmp_path):
    f = tmp_path / "point.swift"
    f.write_text(
        "struct Point: Equatable {\n"
        "    let x: Double\n"
        "    let y: Double\n"
        "    func magnitude() -> Double {\n"
        "        return (x * x + y * y).squareRoot()\n"
        "    }\n"
        "}\n"
    )

    elements = parse_swift_file(f, project_root=tmp_path)
    types = {e.element_type for e in elements}
    assert "class" in types  # struct classified as class-like
    assert "method" in types
    assert "variable" in types

    struct = [e for e in elements if e.element_type == "class"][0]
    assert struct.element_name == "Point"

    method = [e for e in elements if e.element_type == "method"][0]
    assert method.element_name == "Point.magnitude"
    assert method.parent_chain == "point.swift > Point"


def test_parse_enum_with_computed_property(tmp_path):
    """PreparingPhase-style enum with computed .label — the DRY-violation shape."""
    f = tmp_path / "phase.swift"
    f.write_text(
        "enum Phase: Equatable {\n"
        "    case starting\n"
        "    case connecting\n"
        "\n"
        "    var label: String {\n"
        "        switch self {\n"
        '        case .starting: return "Starting Plow..."\n'
        '        case .connecting: return "Connecting..."\n'
        "        }\n"
        "    }\n"
        "}\n"
    )

    elements = parse_swift_file(f, project_root=tmp_path)

    # We should see the enum as a class-like element
    enums = [e for e in elements if e.element_type == "class"]
    assert len(enums) == 1
    assert enums[0].element_name == "Phase"

    # Computed property should be classified as method (it has a body) so DRY
    # queries against "label" computed properties surface it.
    label_entries = [e for e in elements if e.element_name == "Phase.label"]
    assert len(label_entries) == 1
    assert label_entries[0].element_type == "method"
    assert "Starting Plow" in label_entries[0].code_body


def test_parse_extension(tmp_path):
    f = tmp_path / "ext.swift"
    f.write_text(
        "extension String {\n"
        "    func reversedTwice() -> String {\n"
        "        return String(self.reversed().reversed())\n"
        "    }\n"
        "}\n"
    )

    elements = parse_swift_file(f, project_root=tmp_path)

    exts = [e for e in elements if e.element_type == "class"]
    assert len(exts) == 1
    assert exts[0].element_name == "extension String"

    methods = [e for e in elements if e.element_type == "method"]
    assert len(methods) == 1
    assert methods[0].element_name == "extension String.reversedTwice"


def test_parse_class_with_init(tmp_path):
    f = tmp_path / "cls.swift"
    f.write_text(
        "class Counter {\n"
        "    var value: Int\n"
        "    init(start: Int) {\n"
        "        self.value = start\n"
        "    }\n"
        "    func increment() {\n"
        "        value += 1\n"
        "    }\n"
        "}\n"
    )

    elements = parse_swift_file(f, project_root=tmp_path)
    names = {e.element_name for e in elements}
    assert "Counter" in names
    assert "Counter.init" in names
    assert "Counter.increment" in names


def test_parse_protocol(tmp_path):
    f = tmp_path / "proto.swift"
    f.write_text(
        "protocol Drawable {\n"
        "    func draw()\n"
        "    var color: String { get }\n"
        "}\n"
    )

    elements = parse_swift_file(f, project_root=tmp_path)
    names = {e.element_name for e in elements}
    assert "Drawable" in names
