# .devloop — development loop tracking

Tactical execution tracking for RP Engine. This is the **doing** layer. It complements,
and does not duplicate, the strategic docs in `../docs/`:

| Layer | Lives in | Answers |
|---|---|---|
| Strategy — milestones | `../docs/ROADMAP.md` | *What are we building next, and why?* |
| Rationale — decisions | `../docs/DECISIONS.md` (ADRs) | *Why did we choose this?* |
| **Execution — this folder** | `.devloop/` | *What am I doing right now, and what did I already finish?* |

> **Note:** `.devloop/` is **gitignored** — it lives only on this machine, not in the repo
> or on any remote. History is preserved by the dated files in `archive/`, not by git.
> If you want git-level history + off-machine backup, un-ignore this folder (see bottom).

## Layout

```
.devloop/
  BOARD.md                          ← the kanban you glance at (VSCode "Markdown Kanban" extension)
  README.md                         ← this file
  epics/S###-<slug>.md              ← detailed checklist per ACTIVE epic
  archive/S###-YYYY-MM-DD-<slug>.md  ← FROZEN finished epics (evolution history)
```

## Story numbers

Every epic gets a stable **story id** `S###` (zero-padded, e.g. `S002`) so you can name
and link it from board cards, commits, and notes ("finished S003").

- The id is assigned **when the epic file is created** and **never changes** — it travels
  with the file into `archive/` (the archived name keeps both id and completion date).
- Ids are **monotonic**, not chronological-per-commit: they're assigned to epic *files*,
  so a done item that never had an epic file simply has no id.
- **Next number = max existing id + 1.** Find it with:

  ```bash
  ls .devloop/epics .devloop/archive | grep -oE 'S[0-9]+' | sort -u | tail -1
  ```

- Card format on the board leads with the id: `**S003** · <title> — <one-liner> → [epic](…)`.

## The board

`BOARD.md` renders as a drag-and-drop kanban with the VSCode extension
**Markdown Kanban** (`lowrank.vscode-markdown-kanban`) — install it, then "Open as
Kanban" on the file. Columns are `##` headers; cards are top-level list items. It's also
readable as plain markdown if you skip the extension.

Columns: **Backlog** → **Up Next** → **In Progress** → **Done (recent)**.

## Workflow

1. **New unit of work = an epic.** Anything bigger than a one-liner gets a file
   `epics/S###-<slug>.md` — take the next story number (see below), copy the shape of an
   archived one (goal, phases, checklists, verification), and put `# S### · <title>` as its
   H1. Add a card to **Backlog** in `BOARD.md` linking to it.
2. **Start it:** drag the card to **In Progress**. Keep the checklist in its epic file
   current as you go — that's your working scratchpad.
3. **Finish it:**
   - Move the epic file, keeping its id: `mv epics/S###-<slug>.md archive/S###-$(date +%F)-<slug>.md`
   - Add the frozen banner at the top (see any archived file), Status → ✅ COMPLETE.
   - Move the board card to **Done (recent)** with a one-line result + date; repoint the
     link at `archive/…`. Link the ADR if the epic produced one.
4. **Keep Done trim.** When "Done (recent)" gets long, delete older cards from the board —
   the full record already lives in `archive/`.

## Rules

- **Never edit an `archive/` file.** It is a historical record. Reopening work = a new epic.
- **One fact per place.** Roadmap milestones and ADRs are *linked* from cards, not copied.
- Small throwaway tasks can be a bare Backlog card with no epic file. Promote to an epic
  file the moment it grows phases or spans sessions.

## Optional: version this folder in git

If you'd rather have git history + backup for your dev loop, remove the `.devloop` line
from `../.gitignore` and commit the folder. The workflow above is unchanged; you just
additionally get a per-commit diff of the board and epics.
