from unittest.mock import patch

from keepitdry.searcher import Searcher


def test_searcher_returns_results(tmp_path, fake_embed):
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
        Indexer(tmp_path).index()

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
