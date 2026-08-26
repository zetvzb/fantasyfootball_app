from pathlib import Path
import struct


ROOT = Path(__file__).resolve().parents[1]


def test_portfolio_documents_cover_required_system_boundaries():
    required = {
        "docs/ARCHITECTURE.md": ("```mermaid", "Lazy view", "Persistence"),
        "docs/DATA_AND_RAG.md": ("Source precedence", "retrieval", "provenance"),
        "docs/DECISION_ENGINES.md": ("Keeper", "Live auction", "Simulation"),
        "docs/RELIABILITY_AND_DEPLOYMENT.md": (
            "```mermaid",
            "recovery",
            "Posit Connect",
        ),
    }
    for relative, phrases in required.items():
        content = (ROOT / relative).read_text(encoding="utf-8")
        assert all(phrase.lower() in content.lower() for phrase in phrases)


def test_readme_links_each_portfolio_document():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for filename in (
        "docs/ARCHITECTURE.md",
        "docs/DATA_AND_RAG.md",
        "docs/DECISION_ENGINES.md",
        "docs/RELIABILITY_AND_DEPLOYMENT.md",
        "DEPLOYMENT.md",
        "docs/SCREENSHOTS.md",
    ):
        assert "({0})".format(filename) in readme


def test_portfolio_screenshots_are_real_nonempty_png_files():
    for filename in (
        "portfolio-pre-draft.png",
        "portfolio-keeper-comparison.png",
        "portfolio-keeper-combinations.png",
        "portfolio-draft-mode.png",
    ):
        path = ROOT / "docs" / "assets" / filename
        content = path.read_bytes()
        assert content.startswith(b"\x89PNG\r\n\x1a\n")
        width, height = struct.unpack(">II", content[16:24])
        assert width >= 1400
        assert height >= 1000
        assert len(content) >= 50000
