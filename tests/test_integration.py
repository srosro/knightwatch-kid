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
