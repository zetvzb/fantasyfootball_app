# Posit Connect Cloud deployment

This repository is ready for a Git-backed Posit Connect Cloud Streamlit deployment.

## Publish settings

1. Connect the GitHub repository in Posit Connect Cloud.
2. Select the branch to deploy.
3. Select **Streamlit** and use `app.py` as the primary file.
4. Select Python **3.9**. The repository also pins this in `.python-version` and `pyproject.toml`.
5. Keep `requirements.txt` beside `app.py`; Connect Cloud uses it to build the environment.
6. Configure environment variables in the content's Advanced settings:

   - `FANTASYPROS_API_KEY`: optional secret for rankings, projections, news, and injuries.
   - `FANTASYFOOTBALL_DATA_DIR`: writable runtime directory. Use storage that is durable across deployment restarts when available.
   - `FANTASYFOOTBALL_AUTH_MAPPINGS_JSON`: authenticated-user-to-manager mappings, keyed first by league and then by stable identity. Example: `{"league-key":{"posit-connect-cloud:subject-id":"manager-id"}}`.

Connect Cloud currently does not support Streamlit's `st.secrets` mechanism. This application reads secrets with `os.getenv`.

For privately shared Connect Cloud content, the app reads the `Posit-Connect-User-Session-Token` header and uses its stable `sub` claim. For Posit Connect Server it supports `Rstudio-Connect-Credentials`. Authenticated identities must have an explicit manager mapping; unmapped visitors fail closed. When neither trusted header is present, the existing local single-user fallback remains active.

## Preflight health check

Run this using the deployment environment before publishing:

```bash
python -m src.deployment
```

The check verifies Python 3.9, the dependency file, runtime-directory write access, and reports whether optional FantasyPros enrichment is configured. It never prints secret values.

## Runtime storage

All mutable league profiles, setup files, draft ledgers, private preferences, and context databases resolve beneath `FANTASYFOOTBALL_DATA_DIR`. If it is not configured, the application falls back to the repository's `data/` directory and reports that hosted data may be ephemeral.

Official references:

- <https://docs.posit.co/connect-cloud/user/content/streamlit.html>
- <https://docs.posit.co/connect-cloud/user/platform/python.html>
- <https://docs.posit.co/connect-cloud/user/publish/02-advanced.html>
- <https://docs.posit.co/connect-cloud/user/support/01-known-issues.html>
