# keepitdry Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a semantic code search tool that indexes Python codebases and finds similar code by meaning, enforcing DRY development.

**Architecture:** Layered library (parser → embeddings → store → indexer/searcher) with a thin Click CLI and a Claude Code skill. Tree-sitter extracts code elements, Ollama generates embeddings locally, ChromaDB stores vectors per-project.

**Tech Stack:** Python 3.11+, tree-sitter + tree-sitter-python, ChromaDB, Ollama (mxbai-embed-large), Click, requests

**Spec:** `docs/superpowers/specs/2026-03-13-keepitdry-design.md`

---

## File Structure

```
knightwatch-kid/
├── src/keepitdry/
│   ├── __init__.py          # Package version
│   ├── parser.py            # CodeElement dataclass + tree-sitter extraction
│   ├── embeddings.py        # Ollama embedding client
│   ├── store.py             # ChromaDB per-project vector store
│   ├── indexer.py           # Orchestrates parse → embed → store
│   ├── searcher.py          # Query embedding + search + ranking
│   └── cli.py               # Click CLI entry point (`kid` command)
├── skill/
│   ├── SKILL.md             # Claude Code skill definition
│   └── skill.py             # Skill handler (calls library)
├── tests/
│   ├── conftest.py          # Shared fixtures (tmp dirs, fake embeddings)
│   ├── test_parser.py
│   ├── test_embeddings.py
│   ├── test_store.py
│   ├── test_indexer.py
│   ├── test_searcher.py
│   └── test_cli.py
├── pyproject.toml
└── .gitignore
```

**Note:** The spec placed the CLI in `cli/kid.py`, but keeping it inside the `keepitdry` package (`src/keepitdry/cli.py`) avoids packaging complexity. The CLI is still a thin Click wrapper — just importable without sys.path hacks.

**Known v1 simplifications:**
- `.gitignore` patterns are NOT parsed. File discovery uses a hardcoded skip-dirs list. Full `.gitignore` support is a follow-up.
- `--file` filter does exact file path match, not glob. Glob support is a follow-up.

**Dependency order:** parser → embeddings → store → indexer → searcher → CLI → skill

**Testing strategy:**
- **parser**: Real tree-sitter, parse known code strings
- **embeddings**: Mock `requests.post` (Ollama HTTP boundary)
- **store**: Real ChromaDB with temp directories (embedded, no server)
- **indexer**: Real parser + store, mock embeddings
- **searcher**: Real store (pre-populated), mock embeddings
- **CLI**: Click's `CliRunner`, mock library internals

---

## Chunk 1: Foundation

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/keepitdry/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[project]
name = "keepitdry"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "tree-sitter>=0.21",
    "tree-sitter-python>=0.21",
    "chromadb>=0.4",
    "requests>=2.31",
    "click>=8.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
]

[project.scripts]
kid = "keepitdry.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create .gitignore**

```
.keepitdry/
__pycache__/
*.egg-info/
dist/
build/
.venv/
*.pyc
.pytest_cache/
```

- [ ] **Step 3: Create src/keepitdry/__init__.py**

```python
"""keepitdry — semantic code search for DRY codebases."""

__version__ = "0.1.0"
```

- [ ] **Step 4: Create tests/__init__.py and tests/conftest.py**

`tests/__init__.py`: empty file.

`tests/conftest.py`:

```python
import pytest
from pathlib import Path


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project directory with sample Python files."""
    src = tmp_path / "example.py"
    src.write_text(
        'def greet(name: str) -> str:\n'
        '    """Say hello."""\n'
        '    return f"Hello, {name}"\n'
        '\n'
        '\n'
        'class Calculator:\n'
        '    """A simple calculator."""\n'
        '\n'
        '    def add(self, a: int, b: int) -> int:\n'
        '        return a + b\n'
        '\n'
        '    def subtract(self, a: int, b: int) -> int:\n'
        '        return a - b\n'
        '\n'
        '\n'
        'MAX_RETRIES = 3\n'
    )
    return tmp_path


@pytest.fixture
def fake_embed():
    """Return a function that produces deterministic fake embeddings."""
    def _embed(text: str) -> list[float]:
        # Deterministic: hash-based, 1024-dim
        import hashlib
        h = hashlib.sha256(text.encode()).digest()
        # Extend to 1024 floats by repeating hash
        raw = (h * 32)[:1024]
        return [float(b) / 255.0 for b in raw]
    return _embed
```

- [ ] **Step 5: Install in editable mode and verify**

Run: `pip install -e ".[dev]"` from project root.

Then: `python -c "import keepitdry; print(keepitdry.__version__)"` → `0.1.0`

Then: `pytest --co` → should collect 0 tests (no test files with tests yet)

- [ ] **Step 6: Update AGENTS.md scope section**

Update `AGENTS.md` to reflect that the CLI is now inside the package:
Change `- \`cli/\` is the \`kid\` CLI — a thin click wrapper over the library.`
to `- \`src/keepitdry/cli.py\` is the \`kid\` CLI — a thin click wrapper over the library.`

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .gitignore src/ tests/ AGENTS.md
git commit -m "feat: project scaffolding with pyproject.toml and package structure"
```

---

### Task 2: Parser — Function Extraction

**Files:**
- Create: `src/keepitdry/parser.py`
- Create: `tests/test_parser.py`

- [ ] **Step 1: Write the failing test**

`tests/test_parser.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_parser.py -v`
Expected: FAIL — `ImportError: cannot import name 'CodeElement' from 'keepitdry.parser'`

- [ ] **Step 3: Write minimal implementation**

`src/keepitdry/parser.py`:

```python
"""Tree-sitter Python code extraction."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import tree_sitter_python as tspython
from tree_sitter import Language, Parser

PY_LANGUAGE = Language(tspython.language())
_parser = Parser(PY_LANGUAGE)


@dataclass
class CodeElement:
    file_path: str
    element_name: str
    element_type: str  # "function" | "class" | "method" | "variable"
    signature: str
    docstring: str | None
    code_body: str
    line_number: int
    parent_chain: str


def _extract_docstring(body_node) -> str | None:
    """Extract docstring from the first statement in a body block."""
    if not body_node or body_node.child_count == 0:
        return None
    first = body_node.children[0]
    if first.type == "expression_statement" and first.child_count > 0:
        string_node = first.children[0]
        if string_node.type == "string":
            text = string_node.text.decode("utf8")
            # Strip quotes (""" or ' or ")
            for q in ('"""', "'''", '"', "'"):
                if text.startswith(q) and text.endswith(q):
                    return text[len(q):-len(q)].strip()
    return None


def _extract_signature(node) -> str:
    """Extract the def line (everything up to the colon)."""
    text = node.text.decode("utf8")
    # Take the first line up to and excluding the colon at end
    first_line = text.split("\n")[0]
    if first_line.rstrip().endswith(":"):
        return first_line.rstrip()[:-1].strip()
    return first_line.strip()


def _extract_functions(root, file_path: str, parent_chain: str) -> list[CodeElement]:
    """Extract function definitions from direct children of root."""
    elements = []
    for child in root.children:
        node = child
        # Unwrap decorated definitions
        if node.type == "decorated_definition":
            for sub in node.children:
                if sub.type == "function_definition":
                    node = sub
                    break
            else:
                continue

        if node.type != "function_definition":
            continue

        name_node = node.child_by_field_name("name")
        if not name_node:
            continue

        name = name_node.text.decode("utf8")
        body = node.child_by_field_name("body")

        elements.append(CodeElement(
            file_path=file_path,
            element_name=name,
            element_type="function",
            signature=_extract_signature(node),
            docstring=_extract_docstring(body),
            code_body=node.text.decode("utf8"),
            line_number=node.start_point[0] + 1,  # 1-indexed
            parent_chain=parent_chain,
        ))

    return elements


def parse_file(path: Path, project_root: Path) -> list[CodeElement]:
    """Parse a Python file and extract code elements."""
    source = path.read_bytes()
    tree = _parser.parse(source)
    root = tree.root_node

    rel_path = str(path.relative_to(project_root))
    parent_chain = rel_path

    elements = []
    elements.extend(_extract_functions(root, rel_path, parent_chain))

    return elements
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_parser.py -v`
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/keepitdry/parser.py tests/test_parser.py
git commit -m "feat: parser with function extraction via tree-sitter"
```

---

### Task 3: Parser — Class & Method Extraction

**Files:**
- Modify: `tests/test_parser.py`
- Modify: `src/keepitdry/parser.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_parser.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_parser.py::test_parse_class_and_methods tests/test_parser.py::test_parse_decorated_class -v`
Expected: FAIL — no class elements returned

- [ ] **Step 3: Add class/method extraction to parser.py**

Add to `src/keepitdry/parser.py`:

```python
def _extract_class_signature(node) -> str:
    """Extract the class line (everything up to the colon)."""
    text = node.text.decode("utf8")
    first_line = text.split("\n")[0]
    if first_line.rstrip().endswith(":"):
        return first_line.rstrip()[:-1].strip()
    return first_line.strip()


def _extract_classes(root, file_path: str, parent_chain: str) -> list[CodeElement]:
    """Extract class definitions and their methods from direct children."""
    elements = []
    for child in root.children:
        node = child
        # Unwrap decorated definitions
        if node.type == "decorated_definition":
            for sub in node.children:
                if sub.type == "class_definition":
                    node = sub
                    break
            else:
                continue

        if node.type != "class_definition":
            continue

        name_node = node.child_by_field_name("name")
        if not name_node:
            continue

        class_name = name_node.text.decode("utf8")
        body = node.child_by_field_name("body")

        elements.append(CodeElement(
            file_path=file_path,
            element_name=class_name,
            element_type="class",
            signature=_extract_class_signature(node),
            docstring=_extract_docstring(body),
            code_body=node.text.decode("utf8"),
            line_number=node.start_point[0] + 1,
            parent_chain=parent_chain,
        ))

        # Extract methods from class body
        if body:
            class_chain = f"{parent_chain} > {class_name}"
            for method_child in body.children:
                method_node = method_child
                if method_node.type == "decorated_definition":
                    for sub in method_node.children:
                        if sub.type == "function_definition":
                            method_node = sub
                            break
                    else:
                        continue

                if method_node.type != "function_definition":
                    continue

                method_name_node = method_node.child_by_field_name("name")
                if not method_name_node:
                    continue

                method_name = method_name_node.text.decode("utf8")
                method_body = method_node.child_by_field_name("body")

                elements.append(CodeElement(
                    file_path=file_path,
                    element_name=f"{class_name}.{method_name}",
                    element_type="method",
                    signature=_extract_signature(method_node),
                    docstring=_extract_docstring(method_body),
                    code_body=method_node.text.decode("utf8"),
                    line_number=method_node.start_point[0] + 1,
                    parent_chain=class_chain,
                ))

    return elements
```

Update `parse_file` to include:
```python
elements.extend(_extract_classes(root, rel_path, parent_chain))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_parser.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/keepitdry/parser.py tests/test_parser.py
git commit -m "feat: parser extracts classes and methods with parent_chain"
```

---

### Task 4: Parser — Variable Extraction

**Files:**
- Modify: `tests/test_parser.py`
- Modify: `src/keepitdry/parser.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_parser.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_parser.py::test_parse_module_variables tests/test_parser.py::test_parse_full_file -v`
Expected: FAIL — no variable elements returned

- [ ] **Step 3: Add variable extraction to parser.py**

Add to `src/keepitdry/parser.py`:

```python
def _extract_variables(root, file_path: str, parent_chain: str) -> list[CodeElement]:
    """Extract module-level variable assignments from direct children."""
    elements = []
    for child in root.children:
        if child.type == "expression_statement":
            for sub in child.children:
                if sub.type == "assignment":
                    _extract_assignment(sub, file_path, parent_chain, elements)

    return elements


def _extract_assignment(node, file_path: str, parent_chain: str, elements: list):
    """Extract a single assignment as a variable CodeElement."""
    left = node.child_by_field_name("left")
    if not left:
        return

    # Only extract simple name assignments (not tuple unpacking, subscripts, etc.)
    if left.type != "identifier":
        return

    name = left.text.decode("utf8")

    elements.append(CodeElement(
        file_path=file_path,
        element_name=name,
        element_type="variable",
        signature=node.text.decode("utf8").split("\n")[0].strip(),
        docstring=None,
        code_body=node.text.decode("utf8"),
        line_number=node.start_point[0] + 1,
        parent_chain=parent_chain,
    ))
```

Update `parse_file` to include:
```python
elements.extend(_extract_variables(root, rel_path, parent_chain))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_parser.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/keepitdry/parser.py tests/test_parser.py
git commit -m "feat: parser extracts module-level variables"
```

---

### Task 5: Parser — Smart Chunking

**Files:**
- Modify: `tests/test_parser.py`
- Modify: `src/keepitdry/parser.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_parser.py`:

```python
from keepitdry.parser import chunk_elements, TOKEN_THRESHOLD


def test_small_element_not_chunked():
    el = CodeElement(
        file_path="f.py",
        element_name="small",
        element_type="function",
        signature="def small()",
        docstring=None,
        code_body="def small():\n    return 1",
        line_number=1,
        parent_chain="f.py",
    )

    result = chunk_elements([el])
    assert len(result) == 1
    assert result[0] is el


def test_large_class_is_chunked(tmp_path):
    # Build a class with many methods that exceeds TOKEN_THRESHOLD
    methods = []
    for i in range(30):
        methods.append(
            f"    def method_{i}(self):\n"
            f"        # This is method number {i} with enough text to add tokens\n"
            f"        value = {i} * 2 + {i}\n"
            f"        return value\n"
        )
    class_code = "class BigClass:\n" + "\n".join(methods)

    f = tmp_path / "big.py"
    f.write_text(class_code)

    elements = parse_file(f, project_root=tmp_path)
    chunked = chunk_elements(elements)

    # Methods should remain as individual elements
    methods_out = [e for e in chunked if e.element_type == "method"]
    assert len(methods_out) == 30

    # The class itself should be replaced with a signature-only summary
    # (since it exceeds the threshold)
    class_els = [e for e in chunked if e.element_type == "class"]
    assert len(class_els) == 1
    # The summary should NOT contain all 30 method bodies
    assert len(class_els[0].code_body) < len(class_code)


def test_chunk_preserves_parent_context():
    # Build a function body that definitely exceeds _CHAR_THRESHOLD (1600 chars)
    body = "    x = 1\n" * 200  # 2000 chars
    el = CodeElement(
        file_path="mod.py",
        element_name="BigFunc",
        element_type="function",
        signature="def BigFunc()",
        docstring=None,
        code_body="def BigFunc():\n" + body,
        line_number=1,
        parent_chain="mod.py",
    )

    result = chunk_elements([el])

    assert len(result) > 1, "Expected the function to be chunked"
    for chunk in result:
        assert chunk.parent_chain == "mod.py"
        assert "BigFunc" in chunk.element_name
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_parser.py::test_small_element_not_chunked -v`
Expected: FAIL — `ImportError: cannot import name 'chunk_elements'`

- [ ] **Step 3: Implement chunking**

Add to `src/keepitdry/parser.py`:

```python
# ~400 tokens ≈ ~1600 chars (rough 4 chars/token heuristic for code)
TOKEN_THRESHOLD = 400
_CHAR_THRESHOLD = TOKEN_THRESHOLD * 4


def chunk_elements(elements: list[CodeElement]) -> list[CodeElement]:
    """Split oversized elements into smaller chunks.

    Small elements pass through unchanged. Large functions are split by
    top-level statement boundaries. Large classes are replaced by a
    signature-only summary (methods are already extracted separately).
    """
    result = []
    for el in elements:
        if len(el.code_body) <= _CHAR_THRESHOLD:
            result.append(el)
            continue

        if el.element_type == "class":
            # Class body is too large — keep a signature-only summary.
            # Methods are already extracted as separate elements.
            result.append(CodeElement(
                file_path=el.file_path,
                element_name=el.element_name,
                element_type=el.element_type,
                signature=el.signature,
                docstring=el.docstring,
                code_body=el.signature + (":" if not el.signature.endswith(":") else "")
                          + (f'\n    """{el.docstring}"""' if el.docstring else ""),
                line_number=el.line_number,
                parent_chain=el.parent_chain,
            ))
        elif el.element_type == "function":
            # Split function body into chunks at line boundaries
            lines = el.code_body.split("\n")
            header = lines[0]  # def line
            body_lines = lines[1:]

            chunk_lines = []
            chunk_idx = 0
            for line in body_lines:
                chunk_lines.append(line)
                current_text = header + "\n" + "\n".join(chunk_lines)
                if len(current_text) >= _CHAR_THRESHOLD:
                    result.append(CodeElement(
                        file_path=el.file_path,
                        element_name=f"{el.element_name}[chunk_{chunk_idx}]",
                        element_type=el.element_type,
                        signature=el.signature,
                        docstring=el.docstring if chunk_idx == 0 else None,
                        code_body=current_text,
                        line_number=el.line_number,
                        parent_chain=el.parent_chain,
                    ))
                    chunk_lines = []
                    chunk_idx += 1

            if chunk_lines:
                current_text = header + "\n" + "\n".join(chunk_lines)
                if chunk_idx == 0:
                    # Didn't actually need chunking
                    result.append(el)
                else:
                    result.append(CodeElement(
                        file_path=el.file_path,
                        element_name=f"{el.element_name}[chunk_{chunk_idx}]",
                        element_type=el.element_type,
                        signature=el.signature,
                        docstring=None,
                        code_body=current_text,
                        line_number=el.line_number,
                        parent_chain=el.parent_chain,
                    ))
        else:
            # Variables or methods — unlikely to exceed threshold, but pass through
            result.append(el)

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_parser.py -v`
Expected: All 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/keepitdry/parser.py tests/test_parser.py
git commit -m "feat: smart chunking for oversized code elements"
```

---

## Chunk 2: Embeddings & Store

### Task 6: Embeddings — Text Construction

**Files:**
- Create: `src/keepitdry/embeddings.py`
- Create: `tests/test_embeddings.py`

- [ ] **Step 1: Write the failing test**

`tests/test_embeddings.py`:

```python
from keepitdry.embeddings import build_searchable_text
from keepitdry.parser import CodeElement


def test_build_searchable_text_full():
    el = CodeElement(
        file_path="utils.py",
        element_name="parse_config",
        element_type="function",
        signature="def parse_config(path: str) -> dict",
        docstring="Parse a YAML config file.",
        code_body="def parse_config(path: str) -> dict:\n    ...",
        line_number=1,
        parent_chain="utils.py",
    )

    text = build_searchable_text(el)

    assert "utils.py" in text
    assert "parse_config" in text
    assert "def parse_config(path: str) -> dict" in text
    assert "Parse a YAML config file." in text
    assert "def parse_config(path: str) -> dict:\n    ..." in text


def test_build_searchable_text_no_docstring():
    el = CodeElement(
        file_path="f.py",
        element_name="add",
        element_type="function",
        signature="def add(a, b)",
        docstring=None,
        code_body="def add(a, b):\n    return a + b",
        line_number=1,
        parent_chain="f.py",
    )

    text = build_searchable_text(el)

    assert "add" in text
    assert "def add(a, b)" in text
    # No "None" literal in text
    assert "None" not in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_embeddings.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_searchable_text'`

- [ ] **Step 3: Write minimal implementation**

`src/keepitdry/embeddings.py`:

```python
"""Ollama embedding client for mxbai-embed-large."""

from __future__ import annotations

from keepitdry.parser import CodeElement

OLLAMA_BASE_URL = "http://localhost:11434"
MODEL = "mxbai-embed-large"
EMBEDDING_DIM = 1024


def build_searchable_text(element: CodeElement) -> str:
    """Construct the text to embed for a code element.

    Format: parent_chain + element_name + signature + docstring + code_body
    """
    parts = [
        element.parent_chain,
        element.element_name,
        element.signature,
    ]
    if element.docstring:
        parts.append(element.docstring)
    parts.append(element.code_body)
    return "\n".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_embeddings.py -v`
Expected: 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/keepitdry/embeddings.py tests/test_embeddings.py
git commit -m "feat: searchable text construction for embeddings"
```

---

### Task 7: Embeddings — Ollama Client

**Files:**
- Modify: `src/keepitdry/embeddings.py`
- Modify: `tests/test_embeddings.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_embeddings.py`:

```python
from unittest.mock import patch, Mock
from keepitdry.embeddings import embed, batch_embed, check_ollama, OllamaError


def _mock_embed_response(texts=None, dim=1024):
    """Create a mock response for Ollama /api/embed endpoint."""
    # /api/embed returns {"embeddings": [[...], [...]]} for batch input
    count = len(texts) if texts else 1
    resp = Mock()
    resp.status_code = 200
    resp.json.return_value = {"embeddings": [[0.1] * dim for _ in range(count)]}
    resp.raise_for_status = Mock()
    return resp


def test_check_ollama_success():
    with patch("keepitdry.embeddings.requests.get") as mock_get:
        mock_get.return_value = Mock(status_code=200)
        # Should not raise
        check_ollama()


def test_check_ollama_failure():
    import pytest
    import requests as req
    with patch("keepitdry.embeddings.requests.get") as mock_get:
        mock_get.side_effect = req.ConnectionError("refused")
        with pytest.raises(OllamaError, match="Ollama"):
            check_ollama()


def test_embed_single():
    with patch("keepitdry.embeddings.requests.post") as mock_post:
        mock_post.return_value = _mock_embed_response(["hello world"])

        vec = embed("hello world")

        assert len(vec) == 1024
        assert all(isinstance(v, float) for v in vec)
        mock_post.assert_called_once()


def test_batch_embed():
    texts = ["text one", "text two", "text three"]
    with patch("keepitdry.embeddings.requests.post") as mock_post:
        mock_post.return_value = _mock_embed_response(texts)

        vecs = batch_embed(texts)

        assert len(vecs) == 3
        assert all(len(v) == 1024 for v in vecs)
        # batch_embed should make a single API call, not one per text
        mock_post.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_embeddings.py::test_embed_single -v`
Expected: FAIL — `ImportError: cannot import name 'embed'`

- [ ] **Step 3: Implement Ollama client**

Add to `src/keepitdry/embeddings.py`:

```python
import requests


class OllamaError(Exception):
    """Raised when Ollama is unreachable or returns an error."""


def check_ollama() -> None:
    """Verify Ollama server is running and reachable."""
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        resp.raise_for_status()
    except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as e:
        raise OllamaError(
            f"Ollama is not reachable at {OLLAMA_BASE_URL}. "
            "Make sure Ollama is running: https://ollama.ai"
        ) from e


def embed(text: str) -> list[float]:
    """Generate embedding for a single text."""
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/embed",
        json={"model": MODEL, "input": text},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["embeddings"][0]


def batch_embed(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for multiple texts."""
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/embed",
        json={"model": MODEL, "input": texts},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["embeddings"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_embeddings.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/keepitdry/embeddings.py tests/test_embeddings.py
git commit -m "feat: Ollama embedding client with health check"
```

---

### Task 8: Store — ChromaDB Init & Upsert

**Files:**
- Create: `src/keepitdry/store.py`
- Create: `tests/test_store.py`

- [ ] **Step 1: Write failing tests**

`tests/test_store.py`:

```python
from keepitdry.store import Store


def test_store_init(tmp_path):
    store = Store(tmp_path / ".keepitdry")
    assert store.collection is not None


def test_store_upsert_and_count(tmp_path, fake_embed):
    store = Store(tmp_path / ".keepitdry")

    store.upsert(
        ids=["elem_1", "elem_2"],
        embeddings=[fake_embed("one"), fake_embed("two")],
        metadatas=[
            {"file_path": "a.py", "element_type": "function", "element_name": "foo", "line_number": 1},
            {"file_path": "b.py", "element_type": "class", "element_name": "Bar", "line_number": 5},
        ],
        documents=["def foo(): pass", "class Bar: pass"],
    )

    assert store.count() == 2


def test_store_upsert_is_idempotent(tmp_path, fake_embed):
    store = Store(tmp_path / ".keepitdry")
    meta = {"file_path": "a.py", "element_type": "function", "element_name": "foo", "line_number": 1}
    vec = fake_embed("foo")

    store.upsert(ids=["elem_1"], embeddings=[vec], metadatas=[meta], documents=["v1"])
    store.upsert(ids=["elem_1"], embeddings=[vec], metadatas=[meta], documents=["v2"])

    assert store.count() == 1


def test_store_delete(tmp_path, fake_embed):
    store = Store(tmp_path / ".keepitdry")
    meta = {"file_path": "a.py", "element_type": "function", "element_name": "foo", "line_number": 1}
    store.upsert(ids=["elem_1"], embeddings=[fake_embed("x")], metadatas=[meta], documents=["code"])

    store.delete(ids=["elem_1"])

    assert store.count() == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_store.py -v`
Expected: FAIL — `ImportError: cannot import name 'Store'`

- [ ] **Step 3: Implement store**

`src/keepitdry/store.py`:

```python
"""ChromaDB per-project vector store."""

from __future__ import annotations

from pathlib import Path

import chromadb


COLLECTION_NAME = "keepitdry"


class Store:
    """Manages a ChromaDB collection for a single project."""

    def __init__(self, db_path: Path):
        self._client = chromadb.PersistentClient(path=str(db_path))
        self.collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
        documents: list[str],
    ) -> None:
        """Insert or update elements in the store."""
        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents,
        )

    def delete(self, ids: list[str]) -> None:
        """Delete elements by ID."""
        self.collection.delete(ids=ids)

    def count(self) -> int:
        """Return total number of stored elements."""
        return self.collection.count()

    def clear(self) -> None:
        """Delete the collection and recreate it."""
        self._client.delete_collection(COLLECTION_NAME)
        self.collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_store.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/keepitdry/store.py tests/test_store.py
git commit -m "feat: ChromaDB store with upsert, delete, count"
```

---

### Task 9: Store — Search & Metadata Filtering

**Files:**
- Modify: `tests/test_store.py`
- Modify: `src/keepitdry/store.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_store.py`:

```python
def test_store_search(tmp_path, fake_embed):
    store = Store(tmp_path / ".keepitdry")

    # Insert 3 elements with known embeddings
    store.upsert(
        ids=["a", "b", "c"],
        embeddings=[fake_embed("query target"), fake_embed("something else"), fake_embed("unrelated")],
        metadatas=[
            {"file_path": "a.py", "element_type": "function", "element_name": "target", "line_number": 1},
            {"file_path": "b.py", "element_type": "class", "element_name": "Other", "line_number": 1},
            {"file_path": "c.py", "element_type": "function", "element_name": "unrelated", "line_number": 1},
        ],
        documents=["target code", "other code", "unrelated code"],
    )

    results = store.search(query_embedding=fake_embed("query target"), limit=3)

    assert len(results) <= 3
    # First result should be the exact match
    assert results[0]["id"] == "a"
    assert "distance" in results[0]


def test_store_search_with_type_filter(tmp_path, fake_embed):
    store = Store(tmp_path / ".keepitdry")
    vec = fake_embed("same")

    store.upsert(
        ids=["func1", "class1"],
        embeddings=[vec, vec],
        metadatas=[
            {"file_path": "a.py", "element_type": "function", "element_name": "foo", "line_number": 1},
            {"file_path": "a.py", "element_type": "class", "element_name": "Bar", "line_number": 10},
        ],
        documents=["code1", "code2"],
    )

    results = store.search(
        query_embedding=vec,
        limit=10,
        where={"element_type": "function"},
    )

    assert len(results) == 1
    assert results[0]["id"] == "func1"


def test_store_search_with_file_filter(tmp_path, fake_embed):
    store = Store(tmp_path / ".keepitdry")
    vec = fake_embed("same")

    store.upsert(
        ids=["e1", "e2"],
        embeddings=[vec, vec],
        metadatas=[
            {"file_path": "api/routes.py", "element_type": "function", "element_name": "get", "line_number": 1},
            {"file_path": "models/user.py", "element_type": "function", "element_name": "save", "line_number": 1},
        ],
        documents=["code1", "code2"],
    )

    results = store.search(
        query_embedding=vec,
        limit=10,
        where={"file_path": "api/routes.py"},
    )

    assert len(results) == 1
    assert results[0]["id"] == "e1"


def test_store_delete_by_file(tmp_path, fake_embed):
    store = Store(tmp_path / ".keepitdry")
    vec = fake_embed("x")

    store.upsert(
        ids=["e1", "e2", "e3"],
        embeddings=[vec, vec, vec],
        metadatas=[
            {"file_path": "old.py", "element_type": "function", "element_name": "a", "line_number": 1},
            {"file_path": "old.py", "element_type": "function", "element_name": "b", "line_number": 5},
            {"file_path": "keep.py", "element_type": "function", "element_name": "c", "line_number": 1},
        ],
        documents=["c1", "c2", "c3"],
    )

    store.delete_by_file("old.py")

    assert store.count() == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_store.py::test_store_search -v`
Expected: FAIL — `AttributeError: 'Store' object has no attribute 'search'`

- [ ] **Step 3: Add search and filtering**

Add to `src/keepitdry/store.py` `Store` class:

```python
    def search(
        self,
        query_embedding: list[float],
        limit: int = 5,
        where: dict | None = None,
    ) -> list[dict]:
        """Search for similar elements. Returns list of result dicts."""
        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": min(limit, self.count()) if self.count() > 0 else limit,
        }
        if where:
            kwargs["where"] = where

        results = self.collection.query(**kwargs)

        items = []
        if results["ids"] and results["ids"][0]:
            for i, id_ in enumerate(results["ids"][0]):
                item = {
                    "id": id_,
                    "distance": results["distances"][0][i] if results["distances"] else None,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "document": results["documents"][0][i] if results["documents"] else "",
                }
                items.append(item)
        return items

    def delete_by_file(self, file_path: str) -> None:
        """Delete all elements belonging to a specific file."""
        self.collection.delete(where={"file_path": file_path})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_store.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/keepitdry/store.py tests/test_store.py
git commit -m "feat: store search with metadata filtering and delete_by_file"
```

---

## Chunk 3: Indexer & Searcher

### Task 10: Indexer — File Discovery

**Files:**
- Create: `src/keepitdry/indexer.py`
- Create: `tests/test_indexer.py`

- [ ] **Step 1: Write failing tests**

`tests/test_indexer.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_indexer.py -v`
Expected: FAIL — `ImportError: cannot import name 'discover_python_files'`

- [ ] **Step 3: Implement file discovery**

`src/keepitdry/indexer.py`:

```python
"""Orchestrates the index pipeline: parse → embed → store."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

SKIP_DIRS = frozenset({
    ".keepitdry", "__pycache__", "node_modules", ".venv",
    ".git", ".tox", ".mypy_cache", ".pytest_cache",
})


def discover_python_files(root: Path) -> list[Path]:
    """Find all .py files under root, skipping excluded directories."""
    files = []
    for path in sorted(root.rglob("*.py")):
        rel_parts = path.relative_to(root).parts
        if any(part in SKIP_DIRS for part in rel_parts):
            continue
        files.append(path)
    return files
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_indexer.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/keepitdry/indexer.py tests/test_indexer.py
git commit -m "feat: file discovery with directory exclusion"
```

---

### Task 11: Indexer — File Hash Tracking

**Files:**
- Modify: `tests/test_indexer.py`
- Modify: `src/keepitdry/indexer.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_indexer.py`:

```python
from keepitdry.indexer import FileHashTracker


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

    # Reload from disk
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

    # Only keep.py still exists
    current_files = {str(f1)}
    stale = tracker.stale_files(current_files)

    assert str(f2) in stale
    assert str(f1) not in stale
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_indexer.py::test_hash_tracker_detects_new_files -v`
Expected: FAIL — `ImportError: cannot import name 'FileHashTracker'`

- [ ] **Step 3: Implement FileHashTracker**

Add to `src/keepitdry/indexer.py`:

```python
class FileHashTracker:
    """Track file content hashes for incremental indexing."""

    def __init__(self, path: Path):
        self._path = path
        self._hashes: dict[str, str] = {}
        if path.exists():
            self._hashes = json.loads(path.read_text())

    def _compute_hash(self, file_path: Path) -> str:
        return hashlib.sha256(file_path.read_bytes()).hexdigest()

    def has_changed(self, file_path: Path) -> bool:
        """Check if a file is new or modified since last update."""
        current = self._compute_hash(file_path)
        return self._hashes.get(str(file_path)) != current

    def update(self, file_path: Path) -> None:
        """Record the current hash of a file."""
        self._hashes[str(file_path)] = self._compute_hash(file_path)

    def remove(self, file_path: str) -> None:
        """Remove a file from tracking."""
        self._hashes.pop(file_path, None)

    def stale_files(self, current_files: set[str]) -> list[str]:
        """Return tracked files that no longer exist in current_files."""
        return [f for f in self._hashes if f not in current_files]

    def save(self) -> None:
        """Persist hashes to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._hashes))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_indexer.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/keepitdry/indexer.py tests/test_indexer.py
git commit -m "feat: file hash tracker for incremental indexing"
```

---

### Task 12: Indexer — Full Pipeline

**Files:**
- Modify: `tests/test_indexer.py`
- Modify: `src/keepitdry/indexer.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_indexer.py`:

```python
from unittest.mock import patch
from keepitdry.indexer import Indexer


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

        # Second index should skip unchanged files
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

        # Delete the file
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_indexer.py::test_indexer_indexes_project -v`
Expected: FAIL — `ImportError: cannot import name 'Indexer'`

- [ ] **Step 3: Implement Indexer**

Add to `src/keepitdry/indexer.py`:

```python
from keepitdry.parser import parse_file, chunk_elements, CodeElement
from keepitdry.store import Store
from keepitdry import embeddings as embed_module


class Indexer:
    """Orchestrates parse → embed → store for a project."""

    def __init__(self, project_root: Path):
        self.root = project_root
        self.db_path = project_root / ".keepitdry"
        self.store = Store(self.db_path)
        self._tracker = FileHashTracker(self.db_path / "file_hashes.json")

    def index(self, clear: bool = False) -> dict:
        """Index the project. Returns stats dict."""
        if clear:
            self.clear()

        py_files = discover_python_files(self.root)
        current_paths = {str(f) for f in py_files}

        # Remove stale entries
        stale = self._tracker.stale_files(current_paths)
        for stale_path in stale:
            rel = str(Path(stale_path).relative_to(self.root))
            self.store.delete_by_file(rel)
            self._tracker.remove(stale_path)

        files_indexed = 0
        files_skipped = 0
        total_elements = 0

        for py_file in py_files:
            if not self._tracker.has_changed(py_file):
                files_skipped += 1
                continue

            # Parse
            elements = parse_file(py_file, project_root=self.root)
            elements = chunk_elements(elements)

            if not elements:
                self._tracker.update(py_file)
                continue

            # Remove old entries for this file before upserting new ones
            rel_path = str(py_file.relative_to(self.root))
            self.store.delete_by_file(rel_path)

            # Build searchable texts and embed
            texts = [embed_module.build_searchable_text(el) for el in elements]
            embeddings = embed_module.batch_embed(texts)

            # Upsert
            ids = [f"{el.file_path}::{el.element_name}::{el.line_number}" for el in elements]
            metadatas = [
                {
                    "file_path": el.file_path,
                    "element_type": el.element_type,
                    "element_name": el.element_name,
                    "line_number": el.line_number,
                    "parent_chain": el.parent_chain,
                    "signature": el.signature,
                }
                for el in elements
            ]
            documents = [el.code_body for el in elements]

            self.store.upsert(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=documents,
            )

            self._tracker.update(py_file)
            files_indexed += 1
            total_elements += len(elements)

        self._tracker.save()

        return {
            "files_indexed": files_indexed,
            "files_skipped": files_skipped,
            "elements_indexed": total_elements,
            "stale_removed": len(stale),
        }

    def clear(self) -> None:
        """Remove all indexed data."""
        self.store.clear()
        self._tracker = FileHashTracker(self.db_path / "file_hashes.json")
        if (self.db_path / "file_hashes.json").exists():
            (self.db_path / "file_hashes.json").unlink()

    def stats(self) -> dict:
        """Return index statistics."""
        return {
            "total_elements": self.store.count(),
            "db_path": str(self.db_path),
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_indexer.py -v`
Expected: All 11 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/keepitdry/indexer.py tests/test_indexer.py
git commit -m "feat: indexer pipeline with incremental indexing and stale removal"
```

---

### Task 13: Searcher

**Files:**
- Create: `src/keepitdry/searcher.py`
- Create: `tests/test_searcher.py`

- [ ] **Step 1: Write failing tests**

`tests/test_searcher.py`:

```python
from unittest.mock import patch
from keepitdry.searcher import Searcher


def test_searcher_returns_results(tmp_path, fake_embed):
    # Set up: index a project, then search
    from keepitdry.indexer import Indexer

    (tmp_path / "funcs.py").write_text(
        "def parse_yaml(path):\n"
        "    \"\"\"Parse a YAML config file.\"\"\"\n"
        "    pass\n"
        "\n"
        "def send_email(to, subject):\n"
        "    \"\"\"Send an email notification.\"\"\"\n"
        "    pass\n"
    )

    with patch("keepitdry.indexer.embed_module.batch_embed") as mock_batch:
        mock_batch.side_effect = lambda texts: [fake_embed(t) for t in texts]

        indexer = Indexer(tmp_path)
        indexer.index()

    with patch("keepitdry.searcher.embed_module.embed") as mock_embed:
        mock_embed.side_effect = lambda text: fake_embed(text)

        searcher = Searcher(tmp_path)
        results = searcher.search("parse config from yaml", limit=5)

    assert len(results) > 0
    assert "similarity" in results[0]
    assert "file_path" in results[0]
    assert "element_name" in results[0]
    assert "code" in results[0]
    assert 0 <= results[0]["similarity"] <= 1


def test_searcher_with_type_filter(tmp_path, fake_embed):
    from keepitdry.indexer import Indexer

    (tmp_path / "mixed.py").write_text(
        "MAX = 100\n"
        "\n"
        "def process():\n"
        "    pass\n"
        "\n"
        "class Handler:\n"
        "    def run(self):\n"
        "        pass\n"
    )

    with patch("keepitdry.indexer.embed_module.batch_embed") as mock_batch:
        mock_batch.side_effect = lambda texts: [fake_embed(t) for t in texts]
        Indexer(tmp_path).index()

    with patch("keepitdry.searcher.embed_module.embed") as mock_embed:
        mock_embed.side_effect = lambda text: fake_embed(text)

        searcher = Searcher(tmp_path)
        results = searcher.search("anything", element_type="function")

    types = {r["element_type"] for r in results}
    assert types == {"function"}


def test_searcher_empty_index(tmp_path, fake_embed):
    with patch("keepitdry.searcher.embed_module.embed") as mock_embed:
        mock_embed.side_effect = lambda text: fake_embed(text)

        searcher = Searcher(tmp_path)
        results = searcher.search("anything")

    assert results == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_searcher.py -v`
Expected: FAIL — `ImportError: cannot import name 'Searcher'`

- [ ] **Step 3: Implement searcher**

`src/keepitdry/searcher.py`:

```python
"""Query embedding + search + ranking."""

from __future__ import annotations

from pathlib import Path

from keepitdry import embeddings as embed_module
from keepitdry.store import Store


class Searcher:
    """Search a project's indexed code elements."""

    def __init__(self, project_root: Path):
        self.root = project_root
        self.store = Store(project_root / ".keepitdry")

    def search(
        self,
        query: str,
        limit: int = 5,
        element_type: str | None = None,
        file_path: str | None = None,
    ) -> list[dict]:
        """Search for code elements similar to query text."""
        if self.store.count() == 0:
            return []

        query_vec = embed_module.embed(query)

        where = {}
        if element_type:
            where["element_type"] = element_type
        if file_path:
            where["file_path"] = file_path

        raw = self.store.search(
            query_embedding=query_vec,
            limit=limit,
            where=where if where else None,
        )

        results = []
        for item in raw:
            meta = item["metadata"]
            results.append({
                "file_path": meta.get("file_path", ""),
                "element_name": meta.get("element_name", ""),
                "element_type": meta.get("element_type", ""),
                "line_number": meta.get("line_number", 0),
                "signature": meta.get("signature", ""),
                "parent_chain": meta.get("parent_chain", ""),
                "code": item.get("document", ""),
                "similarity": max(0.0, 1.0 - item["distance"]) if item["distance"] is not None else 0.0,
            })

        return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_searcher.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/keepitdry/searcher.py tests/test_searcher.py
git commit -m "feat: searcher with query embedding, ranking, and metadata filters"
```

---

## Chunk 4: CLI & Skill

### Task 14: CLI — index & find Commands

**Files:**
- Create: `src/keepitdry/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

`tests/test_cli.py`:

```python
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from keepitdry.cli import main


def test_cli_index(tmp_path, fake_embed):
    (tmp_path / "app.py").write_text("def hello():\n    pass\n")

    runner = CliRunner()

    with patch("keepitdry.embeddings.check_ollama"), \
         patch("keepitdry.indexer.embed_module.batch_embed") as mock_embed:
        mock_embed.side_effect = lambda texts: [fake_embed(t) for t in texts]
        result = runner.invoke(main, ["index", str(tmp_path)])

    assert result.exit_code == 0
    assert "indexed" in result.output.lower() or "element" in result.output.lower()


def test_cli_find(tmp_path, fake_embed):
    (tmp_path / "utils.py").write_text(
        "def parse_config(path):\n"
        "    \"\"\"Parse config.\"\"\"\n"
        "    pass\n"
    )

    runner = CliRunner()

    # First index
    with patch("keepitdry.embeddings.check_ollama"), \
         patch("keepitdry.indexer.embed_module.batch_embed") as mock_batch:
        mock_batch.side_effect = lambda texts: [fake_embed(t) for t in texts]
        runner.invoke(main, ["index", str(tmp_path)])

    # Then search
    with patch("keepitdry.embeddings.check_ollama"), \
         patch("keepitdry.searcher.embed_module.embed") as mock_embed:
        mock_embed.side_effect = lambda text: fake_embed(text)
        result = runner.invoke(main, ["find", "parse config", "--project", str(tmp_path)])

    assert result.exit_code == 0
    assert "parse_config" in result.output


def test_cli_find_no_index(tmp_path, fake_embed):
    runner = CliRunner()

    with patch("keepitdry.embeddings.check_ollama"), \
         patch("keepitdry.searcher.embed_module.embed") as mock_embed:
        mock_embed.side_effect = lambda text: fake_embed(text)
        result = runner.invoke(main, ["find", "anything", "--project", str(tmp_path)])

    assert result.exit_code == 0
    assert "no results" in result.output.lower() or result.output.strip() == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'cli'`

Note: You may need to adjust the import or add `cli/` to the Python path. In `pyproject.toml`, the `[project.scripts]` entry handles this for installed use. For tests, add `cli/` to `sys.path` in conftest or adjust the import. The simplest fix: add `cli/__init__.py` (empty file) and ensure `cli/` is in the package find path.

- [ ] **Step 3: Implement CLI**

`src/keepitdry/cli.py`:

```python
"""kid CLI — semantic code search for DRY codebases."""

from __future__ import annotations

from pathlib import Path

import click

from keepitdry import embeddings as embed_module
from keepitdry.indexer import Indexer
from keepitdry.searcher import Searcher


@click.group()
def main():
    """kid — keep it dry. Semantic code search."""
    pass


@main.command()
@click.argument("project", default=".", type=click.Path(exists=True, path_type=Path))
@click.option("--clear", is_flag=True, help="Clear index before rebuilding.")
def index(project: Path, clear: bool):
    """Index a project directory."""
    project = project.resolve()
    embed_module.check_ollama()

    indexer = Indexer(project)
    stats = indexer.index(clear=clear)

    click.echo(f"Indexed {stats['files_indexed']} files, "
               f"{stats['elements_indexed']} elements. "
               f"Skipped {stats['files_skipped']} unchanged files.")
    if stats["stale_removed"]:
        click.echo(f"Removed {stats['stale_removed']} stale entries.")


@main.command()
@click.argument("query")
@click.option("--project", default=".", type=click.Path(exists=True, path_type=Path),
              help="Project directory to search.")
@click.option("--limit", default=5, help="Max results.")
@click.option("--type", "element_type", default=None, help="Filter by element type.")
@click.option("--file", "file_path", default=None, help="Filter by file path.")
def find(query: str, project: Path, limit: int, element_type: str | None, file_path: str | None):
    """Search for similar code elements."""
    project = Path(project).resolve()
    embed_module.check_ollama()

    searcher = Searcher(project)
    results = searcher.search(
        query=query,
        limit=limit,
        element_type=element_type,
        file_path=file_path,
    )

    if not results:
        click.echo("No results found.")
        return

    for i, r in enumerate(results, 1):
        score = r["similarity"]
        click.echo(f"\n{'─' * 60}")
        click.echo(f"  [{i}] {r['element_name']}  ({r['element_type']})  "
                    f"score: {score:.3f}")
        click.echo(f"  {r['file_path']}:{r['line_number']}")
        click.echo(f"  {r['signature']}")
        # Show first few lines of code
        code_lines = r["code"].split("\n")
        preview = "\n".join(code_lines[:8])
        if len(code_lines) > 8:
            preview += f"\n  ... ({len(code_lines) - 8} more lines)"
        click.echo(f"\n{preview}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: All 3 tests PASS

Note: Since the CLI is inside the `keepitdry` package, no sys.path hacks are needed.

- [ ] **Step 5: Commit**

```bash
git add src/keepitdry/cli.py tests/test_cli.py
git commit -m "feat: kid CLI with index and find commands"
```

---

### Task 15: CLI — stats & clean Commands

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `cli/kid.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_cli.py`:

```python
def test_cli_stats(tmp_path, fake_embed):
    (tmp_path / "app.py").write_text("def hello():\n    pass\n")

    runner = CliRunner()

    with patch("keepitdry.embeddings.check_ollama"), \
         patch("keepitdry.indexer.embed_module.batch_embed") as mock_embed:
        mock_embed.side_effect = lambda texts: [fake_embed(t) for t in texts]
        runner.invoke(main, ["index", str(tmp_path)])

    result = runner.invoke(main, ["stats", "--project", str(tmp_path)])

    assert result.exit_code == 0
    assert "element" in result.output.lower()


def test_cli_clean(tmp_path, fake_embed):
    (tmp_path / "app.py").write_text("x = 1\n")

    runner = CliRunner()

    with patch("keepitdry.embeddings.check_ollama"), \
         patch("keepitdry.indexer.embed_module.batch_embed") as mock_embed:
        mock_embed.side_effect = lambda texts: [fake_embed(t) for t in texts]
        runner.invoke(main, ["index", str(tmp_path)])

    result = runner.invoke(main, ["clean", str(tmp_path)])

    assert result.exit_code == 0
    assert "removed" in result.output.lower() or "clean" in result.output.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py::test_cli_stats tests/test_cli.py::test_cli_clean -v`
Expected: FAIL — `Usage: main [OPTIONS] COMMAND` (commands don't exist yet)

- [ ] **Step 3: Add stats and clean commands**

Add to `src/keepitdry/cli.py`:

```python
@main.command()
@click.option("--project", default=".", type=click.Path(exists=True, path_type=Path),
              help="Project directory.")
def stats(project: Path):
    """Show index statistics."""
    project = Path(project).resolve()
    indexer = Indexer(project)
    s = indexer.stats()
    click.echo(f"Total elements: {s['total_elements']}")
    click.echo(f"Index path: {s['db_path']}")


@main.command()
@click.argument("project", default=".", type=click.Path(exists=True, path_type=Path))
def clean(project: Path):
    """Remove the project index."""
    project = project.resolve()
    indexer = Indexer(project)
    indexer.clear()
    click.echo("Index cleaned.")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/keepitdry/cli.py tests/test_cli.py
git commit -m "feat: kid CLI stats and clean commands"
```

---

### Task 16: Claude Code Skill

**Files:**
- Create: `skill/SKILL.md`
- Create: `skill/skill.py`

- [ ] **Step 1: Create SKILL.md**

`skill/SKILL.md`:

```markdown
---
name: keepitdry
description: Search before writing — enforce DRY by finding similar code semantically
---

# keepitdry

Before writing any new function, class, or significant code block:

1. Run `kid find "<description of what you're about to write>"` in the project directory
2. Review the results:
   - **Similarity > 0.7**: Reuse or extend the existing code
   - **Similarity 0.5–0.7**: Consider whether the existing code can be adapted
   - **No results or < 0.5**: Proceed with writing new code
3. After writing new code, re-index: `kid index .`

## Setup

Requires `kid` CLI installed (`pip install keepitdry`) and Ollama running locally with `mxbai-embed-large`.

## Commands

- `kid index [path]` — Index a project (incremental, fast on re-runs)
- `kid find "query"` — Search for similar code
- `kid find "query" --type function` — Filter by element type
- `kid find "query" --file "api/*.py"` — Filter by file path
- `kid stats` — Show index info
- `kid clean` — Remove index
```

- [ ] **Step 2: Create skill.py**

`skill/skill.py`:

```python
"""Skill handler for Claude Code integration."""

from __future__ import annotations

import subprocess
import sys


def run_kid(args: list[str]) -> str:
    """Run a kid CLI command and return output."""
    result = subprocess.run(
        ["kid", *args],
        capture_output=True,
        text=True,
    )
    return result.stdout + result.stderr


def search_before_writing(description: str, project: str = ".") -> str:
    """Search for existing code before writing new code."""
    return run_kid(["find", description, "--project", project])


def reindex(project: str = ".") -> str:
    """Re-index after writing new code."""
    return run_kid(["index", project])
```

- [ ] **Step 3: Commit**

```bash
git add skill/
git commit -m "feat: Claude Code skill for search-before-writing workflow"
```

---

## Chunk 5: Integration & Polish

### Task 17: End-to-End Smoke Test

**Files:**
- Modify: `tests/conftest.py` (if needed)
- Create: `tests/test_integration.py`

This test verifies the full pipeline works together. It requires mocking only the Ollama embedding calls.

- [ ] **Step 1: Write the integration test**

`tests/test_integration.py`:

```python
"""End-to-end integration test for the full pipeline."""

from unittest.mock import patch
from pathlib import Path
from keepitdry.indexer import Indexer
from keepitdry.searcher import Searcher


def test_full_pipeline(tmp_path, fake_embed):
    """Index a project, search it, verify results make sense."""
    # Create a small project
    (tmp_path / "utils.py").write_text(
        'def parse_yaml_config(path: str) -> dict:\n'
        '    """Parse a YAML configuration file and return its contents."""\n'
        '    import yaml\n'
        '    with open(path) as f:\n'
        '        return yaml.safe_load(f)\n'
    )
    (tmp_path / "email.py").write_text(
        'def send_notification(to: str, subject: str, body: str) -> bool:\n'
        '    """Send an email notification."""\n'
        '    pass\n'
    )
    (tmp_path / "models.py").write_text(
        'class UserModel:\n'
        '    """Represents a user in the system."""\n'
        '\n'
        '    def __init__(self, name: str, email: str):\n'
        '        self.name = name\n'
        '        self.email = email\n'
        '\n'
        '    def to_dict(self) -> dict:\n'
        '        return {"name": self.name, "email": self.email}\n'
    )

    # Index
    with patch("keepitdry.indexer.embed_module.batch_embed") as mock_batch:
        mock_batch.side_effect = lambda texts: [fake_embed(t) for t in texts]
        indexer = Indexer(tmp_path)
        stats = indexer.index()

    assert stats["files_indexed"] == 3
    assert stats["elements_indexed"] > 0

    # Search
    with patch("keepitdry.searcher.embed_module.embed") as mock_embed:
        mock_embed.side_effect = lambda text: fake_embed(text)
        searcher = Searcher(tmp_path)

        results = searcher.search("parse config from yaml file")

    assert len(results) > 0
    # All results should have required fields
    for r in results:
        assert "file_path" in r
        assert "element_name" in r
        assert "similarity" in r
        assert "code" in r
        assert 0 <= r["similarity"] <= 1

    # Search with type filter
    with patch("keepitdry.searcher.embed_module.embed") as mock_embed:
        mock_embed.side_effect = lambda text: fake_embed(text)

        class_results = searcher.search("user model", element_type="class")

    assert len(class_results) > 0, "Expected at least one class result"
    class_types = {r["element_type"] for r in class_results}
    assert class_types == {"class"}

    # Verify incremental: re-index skips unchanged
    with patch("keepitdry.indexer.embed_module.batch_embed") as mock_batch:
        mock_batch.side_effect = lambda texts: [fake_embed(t) for t in texts]
        stats2 = indexer.index()

    assert stats2["files_indexed"] == 0
    assert stats2["files_skipped"] == 3

    # Verify stats
    s = indexer.stats()
    assert s["total_elements"] > 0
```

- [ ] **Step 2: Run the integration test**

Run: `pytest tests/test_integration.py -v`
Expected: PASS

- [ ] **Step 3: Run all tests**

Run: `pytest -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: end-to-end integration test for full pipeline"
```

---

### Task 18: Package Polish

**Files:**
- Modify: `pyproject.toml` (finalize entry point, verify)
- Verify: `pip install -e ".[dev]"` works
- Verify: `kid --help` works

- [ ] **Step 1: Verify package installs and CLI works**

```bash
pip install -e ".[dev]"
kid --help
```

Expected: Shows help with `index`, `find`, `stats`, `clean` commands.

- [ ] **Step 2: Run full test suite one final time**

```bash
pytest -v
```

Expected: All tests PASS

- [ ] **Step 3: Final commit if any adjustments were needed**

```bash
git add -u
git commit -m "chore: finalize package configuration"
```

---

## Summary

| Task | Module | What it builds |
|------|--------|---------------|
| 1 | — | Project scaffolding, pyproject.toml, .gitignore |
| 2 | parser | CodeElement dataclass + function extraction |
| 3 | parser | Class & method extraction with parent_chain |
| 4 | parser | Module-level variable extraction |
| 5 | parser | Smart chunking (~400 token threshold) |
| 6 | embeddings | Searchable text construction |
| 7 | embeddings | Ollama client (embed, batch_embed, health check) |
| 8 | store | ChromaDB init, upsert, count, delete |
| 9 | store | Search with cosine similarity + metadata filtering |
| 10 | indexer | File discovery with directory exclusion |
| 11 | indexer | File hash tracker for incremental indexing |
| 12 | indexer | Full pipeline: parse → embed → store + stale removal |
| 13 | searcher | Query embedding + search + ranking |
| 14 | cli | `kid index` and `kid find` commands |
| 15 | cli | `kid stats` and `kid clean` commands |
| 16 | skill | SKILL.md + skill.py for Claude Code |
| 17 | — | End-to-end integration test |
| 18 | — | Package polish and verification |
