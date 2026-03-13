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
