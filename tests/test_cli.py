from unittest.mock import patch
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
