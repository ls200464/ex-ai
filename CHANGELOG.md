# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `Docker` workflow building the backend and frontend images on every push and pull
  request, and publishing them to GitHub Container Registry from the default branch
  and from version tags. Both images are publicly pullable:
  `ghcr.io/ls200464/ex-ai-backend` and `ghcr.io/ls200464/ex-ai-frontend`.
- `.dockerignore` for both images, so a local `backend/.env` holding real API keys is
  never copied into a published layer.
- A "Run with Docker" section in the README.

### Fixed

- **The backend could not start with its default settings.** `DATABASE_URL` defaults
  to `sqlite+aiosqlite://`, but `aiosqlite` was in neither `requirements.txt` nor
  `pyproject.toml`, so importing `app.database` raised `ModuleNotFoundError`. This is
  the exact path the quick start follows.
- **The frontend image could not build.** The dependency stage ran
  `npm ci --only=production`, which omits `typescript`, `tailwindcss` and
  `@tailwindcss/postcss`; `next build` needs all three.
- **The containerised frontend could not reach the backend.** `rewrites()` hardcoded
  `http://localhost:8000`, which resolves to the frontend container itself. The target
  is now a build argument, baked as the Compose service name. Runtime environment
  variables cannot fix this: rewrites are resolved at build time.
- The backend image ran as root; it now runs as an unprivileged user.
- `docker-compose.yml` set `NEXT_PUBLIC_API_URL` at runtime, which has no effect
  because `NEXT_PUBLIC_*` values are inlined at build time. Removed, along with the
  obsolete `version` key.

## [0.1.0] - 2026-10-21

First tagged release. The goal of this version was to make the project usable and
reviewable as an open-source codebase, not to add features.

### Added

- `LICENSE` (MIT). The README already claimed MIT but no licence file existed, so
  the project was not legally open source.
- `LICENSE` declaration in `backend/pyproject.toml` and `frontend/package.json`.
- English `README.md`, with the original Chinese document kept as `README.zh-CN.md`.
- A test suite for the pure-logic modules: sender normalisation, chunking, the
  keyword-retrieval fallback, and structured-JSON extraction (43 tests).
- GitHub Actions workflow running the suite on Python 3.11 and 3.12 for every push
  and pull request.

### Fixed

- **Sender roles were assigned by substring match**, so a short target name
  captured an unrelated sender (`张三` also matched `张三丰`) and both were labelled
  the target. Matching is now ranked: exact, then equal after stripping an account
  identifier, then containment.
- **The account-identifier fallback was unreachable** whenever a chat had exactly
  two speakers, because an earlier branch returned `"other"` first.
- **Chunk overlap was unvalidated.** An overlap at least as large as `chunk_size`
  carried the whole previous chunk forward, so chunks grew instead of advancing and
  duplicated content multiplied quadratically. Overlap is now clamped below
  `chunk_size`, and a non-positive `chunk_size` is rejected.
- **`retrieved_memories` was always empty** in the chat SSE `done` event:
  `build_system_prompt` retrieved memories but returned only the prompt, so
  `Message.retrieved_memories` was never populated.
- **The fallback tokenizer pattern was malformed.** It was written as a
  single-quoted raw string containing `''`, which ended the literal early and
  concatenated a non-raw fragment with invalid escapes (`\[`, `\]`). It is now one
  `re.escape`-built constant shared by both tokenizers.
- **A single malformed stored embedding aborted the whole similarity search** with
  `ValueError`. Unparseable rows are now dropped. Rows whose dimension differs from
  the query (a switched embedding model) are treated as unusable instead of scoring
  `0.0` for every row and silently returning nothing.
- **JSON extraction raised the wrong exception.** An unclosed code fence raised
  `ValueError: substring not found` from `str.index`, and invalid JSON inside a
  fence leaked a raw `JSONDecodeError` out of the `except` handler. Both now raise a
  single descriptive `ValueError` with the parse error chained as its cause, and a
  complete JSON body inside an unclosed fence is recovered.

### Removed

- Unused `json` import in `app/services/embedding_service.py`.

[Unreleased]: https://github.com/ls200464/ex-ai/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ls200464/ex-ai/releases/tag/v0.1.0
