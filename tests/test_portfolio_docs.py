from pathlib import Path


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
    ):
        assert "({0})".format(filename) in readme
