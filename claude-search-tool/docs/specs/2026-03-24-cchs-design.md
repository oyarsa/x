# CCHS — Claude Code History Search

A CLI tool and Claude Code skill for searching past conversation history stored
in `~/.claude/projects/`. Uses SQLite FTS5 for full-text search with ranked
results.

## Problem

Claude Code stores conversation history as JSONL files in
`~/.claude/projects/<project-dir>/`. Searching these files with grep is ad-hoc
and unreliable: messages span single enormous JSON lines, tool results dominate
content, and there's no ranking or context windowing.

Users need to recall specific technical decisions, processes, and discussions
from past sessions. Example queries:

- "How did we calculate PFA for our dataset?"
- "Last week we worked on getting dataset-overall values for PFA 40 and 100 —
  how did we do it?"

## Architecture

### Storage layout

```
~/.claude/projects/<project-dir>/
├── <session-id>.jsonl          # existing conversation files
├── <session-id>/               # existing session metadata
└── search.db                   # FTS5 search index (one per project)
```

### Layers

1. **Parser** — reads JSONL files, extracts and cleans messages into Pydantic
   models
2. **Indexer** — populates/updates the SQLite FTS5 database from parsed messages
3. **CLI** — `search`, `expand`, `index`, and `skill` commands

### Project resolution

The CLI derives the project directory from `cwd` using the same path-mangling
convention Claude Code uses:

- `/home/dev/work/foo` → `-home-dev-work-foo`
- `/home/dev/.config/fish` → `-home-dev--config-fish`

The DB is stored at `~/.claude/projects/<project-dir>/search.db`.

## Data Model

### SQLite schema

**`messages` table:**

| Column          | Type        | Description                              |
|-----------------|-------------|------------------------------------------|
| `id`            | INTEGER PK  | Auto-increment                           |
| `session_id`    | TEXT        | Session UUID                             |
| `uuid`          | TEXT UNIQUE | Message UUID (from JSONL)                |
| `role`          | TEXT        | Top-level `type` field: `user` or `assistant` |
| `content`       | TEXT        | Cleaned text content                     |
| `timestamp`     | TEXT        | ISO 8601 timestamp                       |
| `message_index` | INTEGER     | 0-based sequential position among indexed messages in the session, assigned in file order after filtering. Used only for ORDER BY and context window queries — not a stable external identifier. |

**`messages_fts` FTS5 virtual table:**

- `content` column indexed, linked to `messages` table via `content='messages'`
- Tokenizer: `unicode61` with `porter` stemming for English word variants
- Ranking: BM25 (FTS5 default) — returns negative values (more negative =
  better match); negate for display/sorting
- **Content-sync**: since `content='messages'` creates an external-content FTS5
  table, SQLite does not auto-sync. Use `INSERT INTO messages_fts(rowid,
  content) SELECT id, content FROM messages` after populating the messages
  table. On re-index of a session, delete from both tables before re-inserting.

**Schema versioning:** `PRAGMA user_version` tracks the schema version. On
version mismatch, the tool auto-rebuilds the database.

**`index_metadata` table:**

| Column          | Type     | Description                          |
|-----------------|----------|--------------------------------------|
| `file_path`     | TEXT PK  | JSONL filename relative to project dir (e.g., `abc123.jsonl`) |
| `last_modified` | REAL     | File mtime at last index             |
| `last_size`     | INTEGER  | File size at last index              |

### Content cleaning rules

Message content varies by type and role:

- **`user` messages with `str` content**: use the string directly
- **`user` messages with `list` content**: extract `text` blocks as text;
  summarize `tool_result` blocks as `[Result: <first 200 chars>]`
- **`assistant` messages** (always `list` content): concatenate `text` blocks;
  summarize `tool_use` blocks as `[Tool: <name>(<brief input summary>)]`
- **Skip blocks**: `thinking` blocks within assistant messages
- **Skip message types entirely**: `file-history-snapshot`, `progress`,
  `system`, `last-prompt`, `queue-operation`
- **Skip sidechain messages**: messages with `isSidechain: true` (these are
  abandoned conversation branches)

### Pydantic models

```python
class Message(BaseModel, frozen=True):
    session_id: str
    uuid: str
    role: str  # "user" | "assistant"
    content: str
    timestamp: datetime
    message_index: int

class SearchResult(BaseModel, frozen=True):
    match: Message
    context_before: list[Message]
    context_after: list[Message]
    session_id: str
    rank: float  # FTS5 rank score

class ExpandResult(BaseModel, frozen=True):
    messages: list[Message]
    session_id: str
```

## CLI Interface

```
cchs search <query> [OPTIONS]
cchs expand <message-uuid> [OPTIONS]
cchs index [OPTIONS]
cchs skill [OPTIONS]
```

### `cchs search <query>`

Full-text search across project conversations. Auto-indexes if DB is stale.

| Flag              | Default | Description                                |
|-------------------|---------|--------------------------------------------|
| `--context`, `-c` | 3       | Messages before/after each match           |
| `--limit`, `-n`   | 10      | Max results                                |
| `--session`       |         | Restrict to a specific session ID          |
| `--since`         |         | Only search after this date (ISO 8601: `2026-03-20`) |
| `--until`         |         | Only search before this date (ISO 8601: `2026-03-20`) |
| `--project`       |         | Search a specific project path instead of cwd |
| `--json`          | false   | Output raw JSON (for skill consumption)    |

### `cchs expand <message-uuid>`

Retrieve more context around a specific message from a previous search.

| Flag              | Default | Description                            |
|-------------------|---------|----------------------------------------|
| `--before`, `-B`  | 10      | Messages before the target             |
| `--after`, `-A`   | 10      | Messages after the target              |
| `--full`          | false   | Return the entire session              |
| `--project`       |         | Expand from a specific project path    |
| `--json`          | false   | Output raw JSON                        |

### `cchs index`

Manually trigger indexing. Incremental by default.

| Flag        | Default | Description                                        |
|-------------|---------|----------------------------------------------------|
| `--force`   | false   | Drop and rebuild DB (requires interactive confirm unless `--yes`) |
| `--yes`, `-y` | false | Skip interactive confirmation for `--force`        |
| `--project` |         | Index a specific project path instead of cwd       |

### `cchs skill`

Manage the Claude Code skill.

| Flag        | Default | Description                                  |
|-------------|---------|----------------------------------------------|
| `--install` | false   | Write skill to `~/.claude/skills/search-history.md` |

Without `--install`, prints the skill markdown to stdout. This command is
project-independent (no `--project` flag).

## Human-readable output

Search results use rich formatting:

```
── Session 2026-03-20 (abc123) ─────────────────────
  [user]  How should we calculate PFA for the dataset?
  [asst]  We can pool all samples together and compute...
           [Tool: Bash(python calc_pfa.py --pooled)]
           [Result: PFA@40=0.823, PFA@100=0.791...]
» [user]  Let's go with the pooled approach         ← match
  [asst]  Done. I've updated the config to use pooled PFA.
```

The `»` marker indicates the matching message. `--json` outputs `SearchResult`
objects for programmatic consumption.

## Incremental indexing

On every search (and on `cchs index`):

1. List all `*.jsonl` files in the project directory
2. Compare each file's mtime and size against `index_metadata`
3. Re-parse and re-index only changed/new files
4. For changed files: delete old messages for that session, re-insert all
5. Remove index entries for files in `index_metadata` that no longer exist on
   disk (handles deleted sessions)

Session IDs are derived from the JSONL filename (each file is
`<session-id>.jsonl`), not from the `sessionId` field inside messages — this is
simpler and avoids edge cases with message types that lack the field.

The database uses `PRAGMA journal_mode=WAL` for safe concurrent reads during
writes (e.g., if Claude and the user both trigger a search simultaneously).

This keeps search fast while staying up-to-date.

## Skill behavior

The skill at `~/.claude/skills/search-history.md` instructs Claude to:

1. When the user asks about past conversations/history, invoke
   `cchs search "<query>" --json`
2. Scan results for relevance
3. Use `cchs expand <uuid> --json` to get more context on promising matches
4. Synthesize an answer from the gathered context

Trigger phrases: "check our conversation history", "how did we do X last time",
"do you remember when we...", "search our past sessions".

## Error handling

Every error message must be **actionable** — telling the consumer (often Claude)
exactly what went wrong and what command to run to fix it. This is critical
because Claude is a primary consumer and must be able to self-correct.

| Scenario                   | Behavior                                                       |
|----------------------------|----------------------------------------------------------------|
| No DB exists               | Auto-index, show "Indexing conversations for first search..."  |
| Empty project              | "No conversations found in project <name>. Verify you are in the correct project directory, or use --project to specify one." |
| Corrupt DB                 | "Database is corrupt at <path>. Run `cchs index --force` to rebuild." |
| Invalid UUID on expand     | "Message <uuid> not found. Run `cchs search <query>` first to find valid message UUIDs." |
| JSONL parse errors         | Skip malformed lines, warn to stderr, continue indexing        |
| No results                 | "No matches for '<query>'. Try broader search terms or check --since/--until date range." |
| Permission error on DB     | "Cannot write to <path>. Check file permissions."              |
| Project dir not found      | "Project directory <path> does not exist. Available projects: <list>." |

## Technology stack

- **Python 3.14+** with strict typing (`ruff`, `ty`)
- **SQLite FTS5** via `sqlite3` stdlib (no external DB dependencies)
- **Typer** for CLI
- **Pydantic v2** with `frozen=True` for all models
- **Rich** for human-readable output
- **tqdm** for indexing progress bars
- **python-dotenv** for environment variables
- **pytest** for testing
- **Hatchling** build backend

### Project structure

```
src/cchs/
├── __init__.py
├── cli.py              # Main CLI entry point, typer app composition
├── parser.py           # JSONL parsing and content cleaning
├── indexer.py          # SQLite FTS5 database management
├── searcher.py         # Search and expand query logic
├── models.py           # Pydantic models
├── project.py          # Project directory resolution
├── skill.py            # Skill content and installation
└── utils.py            # make_app helper, shared utilities
tests/
├── conftest.py
├── fixtures/           # Sample JSONL files
├── test_parser.py
├── test_indexer.py
├── test_searcher.py
├── test_cli.py
└── test_project.py
```

## Testing strategy

- **Parser tests**: feed sample JSONL lines, verify cleaned output (user
  messages, assistant text extraction, tool use summarization, skipped types)
- **Indexer tests**: create temp DB, index fixtures, verify row counts and FTS
  matches
- **Searcher tests**: end-to-end search and expand against fixture data
- **CLI tests**: use typer's `CliRunner` against fixture data
- **Project tests**: verify path-mangling logic
- **Fixtures**: hand-crafted JSONL files in `tests/fixtures/` covering all
  message types

No mocking of SQLite — tests use real in-memory or temp-file databases.
