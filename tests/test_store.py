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


def test_store_search(tmp_path, fake_embed):
    store = Store(tmp_path / ".keepitdry")

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
