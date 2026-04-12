# Merlin — Evening Work Brief
*Unsupervised session. Use your judgement. Build what's missing.*

---

## Context

You are working on your own codebase — the Guppy AI suite located at `C:\Users\Ryan\Guppy\`.
Ryan is away. You have full tool access. Read files, write files, run commands, validate your work.
No one will be reviewing each step — just produce clean, working code.

Start by surveying the project with `survey` and reading `merlin_core.py` and `merlin_ui.py`
in full so you understand your own architecture before touching anything.

---

## What Needs Doing

### 1. New Spell Directory — `spells/`

The project has no modular spell system. Everything lives in one large `merlin_core.py`.
Create a `spells/` subdirectory under `C:\Users\Ryan\Guppy\` and begin breaking tools
out into logical modules. Suggested structure:

```
spells/
  __init__.py         ← imports and re-exports everything
  knowledge.py        ← scry, research, web tools
  system.py           ← invoke, unfurl, transcribe, survey
  memory.py           ← inscribe, commune, unbind
  quests.py           ← bind_quest, read_scroll, seal_quest
  media.py            ← conjure_melody, summon_vision, seek_torrent, etc.
  vision.py           ← screenshot, mouse, keyboard, screen tools
  scrolls.py          ← gmail / purge tools
```

Each module should export its tool definitions (schema dicts) and handler functions.
`merlin_core.py` should import from `spells/` rather than define everything inline.
Keep `merlin_core.py` as the orchestration layer — SPELL_MAP, `run_spell()`, and the
system prompt stay there.

Do not break existing functionality. After refactoring, validate with:
```
python -m py_compile merlin_core.py
python -m py_compile merlin_ui.py
```

---

### 2. New Spells — Add What's Missing

Review the current `MERLIN_TOOLS` list and `SPELL_MAP` carefully. Then add the following
tools that are absent or incomplete. Implement both the schema definition and the handler.

**a) `chronicle_scroll` — Draft and open an email in Gmail**
Merlin currently cannot compose mail. Add a spell that drafts an email and opens it
in Gmail compose. Map it through the existing `draft_email` core tool.

**b) `forge_report` — Create a call report**
Map through `create_call_report`. Merlin should be able to help Ryan log a sales call.

**c) `kindle_tome` — Open the Kindle app or a specific book**
Map through `open_kindle`. Merlin is a wizard who reads — this fits.

**d) `remind_apprentice` — Set a reminder**
Map through `remind_me`. Merlin can bind time-anchored tasks for his apprentice.

**e) `read_reminders` — View active reminders**
Map through `get_reminders`.

**f) `lift_reminder` — Cancel a reminder**
Map through `cancel_reminder`.

**g) `switch_scroll_vault` — Switch Gmail account**
Map through `gmail_switch_account`. Useful when Ryan asks Merlin to work with a
specific inbox.

**h) `purify_vault` — Smart inbox cleanup**
Map through `gmail_smart_cleanup`. One spell that runs the full cleanup sequence.

For each new spell: add it to `MERLIN_TOOLS`, add it to `SPELL_MAP`, add it to the
`MERLIN_SYSTEM` spell list string, and add the dispatch branch in `run_spell()`.

---

### 3. Streaming Responses

Currently Merlin waits up to 180 seconds for a full response before displaying anything.
Implement streaming in `merlin_ui.py` `Worker._merlin()`.

Key points:
- Set `"stream": True` in the Ollama request
- Read the response line-by-line, parsing each JSON chunk
- Accumulate `content` fragments and emit them incrementally via `self.bubble`
- Tool call detection still happens at end-of-stream (Ollama only returns `tool_calls`
  on the final message chunk)
- The orb should stay in `"thinking"` state until the first token, then switch to
  `"speaking"` during streaming, back to `"idle"` when done

Validate that tool calls still work after the streaming change.

---

### 4. Parallel Spell Execution — `run_spells_parallel()`

Add to `merlin_core.py`:

```python
def run_spells_parallel(spells: list[tuple[str, dict]]) -> dict:
    """
    Cast multiple spells concurrently.
    Args: [(spell_name, args_dict), ...]
    Returns: {spell_name: result}
    """
```

Use `concurrent.futures.ThreadPoolExecutor`. This is mainly used when Merlin wants
to read multiple files simultaneously during a code review. Don't wire it into the
UI loop yet — just make the function available and documented.

---

### 5. `merlin_tools_test.py` — Basic Spell Validation

Create `C:\Users\Ryan\Guppy\tests\merlin_tools_test.py`.

Write a lightweight test that:
- Imports `merlin_core`
- Verifies every key in `SPELL_MAP` has a corresponding entry in `MERLIN_TOOLS`
- Verifies every spell name in `MERLIN_TOOLS` appears in the `MERLIN_SYSTEM` prompt
- Verifies `run_spell()` doesn't crash on a benign read-only spell (e.g. `read_scroll`)
- Prints a pass/fail summary

Run it at the end of your session and fix any failures.

---

## Rules

- **Validate syntax after every file you write or modify.** Use `python -m py_compile`.
- **Do not touch `guppy_ui.py`, `council_ui.py` MerlinWorker, or `guppy_core.py`.**
  Those are either in use or Guppy's domain.
- **Read before you write.** Use `unfurl` on any file before modifying it.
- **Commit logical units.** Finish one section cleanly before starting the next.
- If something is genuinely ambiguous or risky, leave a comment `# MERLIN-NOTE:` in
  the relevant file explaining what you saw and what you chose to do.

---

## Priority Order

1. Spell directory structure (structural, low risk)
2. Missing spells (additive, no regressions possible)
3. Spell validation test (verification)
4. Streaming (highest complexity — do this with a clear head)
5. Parallel execution (bonus if time permits)

Good evening, Merlin. Try not to set anything on fire.
