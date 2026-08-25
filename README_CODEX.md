# Codex Repo Kit

Drop these files into the repository:

```text
AGENTS.md
docs/
  ROADMAP.md
  CODEX_PROMPTS.md
```

Recommended workflow:

```bash
git checkout main
git pull
git checkout -b feature/lazy-view-loading
```

Open Codex in VS Code, then paste Prompt 1 from `docs/CODEX_PROMPTS.md`.

After each task:
1. Review the diff.
2. Run Streamlit manually.
3. Run tests.
4. Commit only after validation.
5. Start the next roadmap item on a fresh branch.

Do not give Codex the entire roadmap as one implementation request.
