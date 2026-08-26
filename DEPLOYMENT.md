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
   - `FANTASYFOOTBALL_DATA_DIR`: writable runtime working directory.
   - `FANTASYFOOTBALL_STATE_URL`: required on Connect Cloud; an HTTPS object endpoint that accepts authenticated `GET` and `PUT` requests for the application state archive.
   - `FANTASYFOOTBALL_STATE_TOKEN`: optional bearer token for that state endpoint.
   - `FANTASYFOOTBALL_AUTH_MAPPINGS_JSON`: authenticated-user-to-manager mappings, keyed first by league and then by stable identity. Example: `{"league-key":{"posit-connect-cloud:subject-id":"manager-id"}}`.
   - `OPENAI_API_KEY`: optional; enables AI-polished explanations of already-computed recommendations.
   - `OPENAI_EXPLANATION_MODEL`: optional model override; defaults to `gpt-5.4`.

Connect Cloud currently does not support Streamlit's `st.secrets` mechanism. This application reads secrets with `os.getenv`.

For privately shared Connect Cloud content, the app reads the `Posit-Connect-User-Session-Token` header and uses its stable `sub` claim. For Posit Connect Server it supports `Rstudio-Connect-Credentials`. Authenticated identities must have an explicit manager mapping; unmapped visitors fail closed. When neither trusted header is present, the existing local single-user fallback remains active.

## Preflight health check

Run this using the deployment environment before publishing:

```bash
python -m src.deployment
```

The check verifies Python 3.9, the dependency file, runtime-directory write access, and reports whether optional FantasyPros enrichment is configured. It never prints secret values.

## Runtime storage

All mutable league profiles, setup files, draft ledgers, and private preferences resolve beneath `FANTASYFOOTBALL_DATA_DIR`. Connect Cloud only retains runtime-written local files while the content remains active, so the application restores these files from `FANTASYFOOTBALL_STATE_URL` on startup and checkpoints them after state changes. Writes use the object's ETag to reject a stale concurrent writer instead of silently overwriting newer state. The bearer token is never placed in the archive or health-check output.

The object endpoint is deliberately provider-neutral. It must return `404` for an uninitialized object, return an `ETag` with successful reads/writes, and enforce `If-Match` on updates. A failed restore stops startup; a failed checkpoint surfaces as a write failure so a draft cannot appear durable when it is not. Player-context caches are intentionally rebuildable and excluded from the durable archive.

Official references:

- <https://docs.posit.co/connect-cloud/user/content/streamlit.html>
- <https://docs.posit.co/connect-cloud/user/platform/python.html>
- <https://docs.posit.co/connect-cloud/user/publish/02-advanced.html>
- <https://docs.posit.co/connect-cloud/user/support/01-known-issues.html>
- <https://docs.posit.co/connect-cloud/user/platform/system.html>
- <https://docs.posit.co/connect/user/structuring-content/>
- <https://docs.posit.co/connect/admin/process-management/>
