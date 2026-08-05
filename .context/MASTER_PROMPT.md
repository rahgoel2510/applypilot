# 🧠 Master Prompt — Context-First Development

> Paste this at the start of every AI session (Kiro, Cursor, Copilot, etc.) to enforce persistent context tracking.

---

## The Prompt

```
You are working on a project with a persistent context system.

RULES — follow these without exception:

1. CONTEXT FIRST
   - Before doing ANYTHING, read `.context/contextGraph.db` if it exists.
   - If it doesn't exist, create the `.context/` folder and generate `contextGraph.db` by scanning the entire project.

2. DOCUMENT EVERY CHANGE
   - After EVERY modification (code, config, architecture, dependency), update the relevant section in `contextGraph.db`:
     • New file? → Add to `fileMap` with role + description.
     • Removed file? → Remove from `fileMap`.
     • New dependency? → Update `techStack.dependencies`.
     • New pattern/convention? → Add to `patterns` or `conventions`.
     • Architectural decision? → Append to `decisions` with reason + date.
     • Bug found? → Add to `knownIssues`.
     • Bug fixed? → Remove from `knownIssues`, log in `sessionLog`.

3. SESSION LOGGING
   - At the end of every response that modifies the project, append a concise entry to `sessionLog`:
     ```json
     { "date": "YYYY-MM-DD", "summary": "What was done" }
     ```

4. NEVER LOSE CONTEXT
   - If you add a new module, it MUST appear in `fileMap`.
   - If you change how something works, update `architecture` or `dataFlow`.
   - If you make a tradeoff or decision, it MUST go in `decisions`.
   - If the user tells you something important about the project, capture it.

5. CONTEXT GRAPH SCHEMA
   - `_meta` → version, format, lastUpdated, generatedBy
   - `project` → name, version, description, author, repo
   - `techStack` → runtime, language, framework, dependencies, tools
   - `architecture` → pattern, phases, execution flow, entry points
   - `fileMap` → every source file with { role, description, imports, exports }
   - `dataFlow` → inputs → intermediates → outputs
   - `patterns` → recurring design patterns in the codebase
   - `conventions` → naming, formatting, error handling rules
   - `environment` → required/optional env vars
   - `scripts` → available CLI commands
   - `knownIssues` → current bugs, limitations, TODOs
   - `decisions` → { decision, reason, date, alternatives_considered }
   - `sessionLog` → chronological history of all sessions

6. FOR NEW PROJECTS
   - Generate contextGraph.db immediately after scaffolding.
   - Include even initial decisions ("chose React over Vue because X").
   - Track the project from day zero.

7. FOR EXISTING PROJECTS
   - Scan the full project tree first.
   - Read package.json / Cargo.toml / requirements.txt / go.mod etc.
   - Read key entry points and infer architecture.
   - Generate contextGraph.db capturing current state.
   - Mark anything uncertain with "NEEDS_VERIFICATION".

8. KEEP IT COMPACT
   - Descriptions should be 1-2 sentences max.
   - No prose paragraphs. Factual, scannable, machine-readable.
   - JSON format. No markdown in the .db file.

Your goal: ANY new AI session that reads contextGraph.db should be able to work on this project as if it built it from scratch. Zero context loss. Ever.
```

---

## Quick Setup Commands

### New Project
```bash
mkdir .context
# Then paste the master prompt in your AI tool and say:
# "Scan this project and generate .context/contextGraph.db"
```

### Existing Project
```bash
mkdir .context
# Then paste the master prompt and say:
# "This is an existing project. Scan everything and generate .context/contextGraph.db"
```

---

## Auto-Refresh: update.js

Keep contextGraph.db in sync with your project:

```bash
# Full refresh (after manual changes)
node .context/update.js

# Dry-run — see what changed without writing
node .context/update.js --check

# Watch mode — auto-update on file changes
node .context/update.js --watch
```

### Git Hook (Optional)

Add to `.git/hooks/pre-commit`:
```bash
#!/bin/bash
node .context/update.js
git add .context/contextGraph.db
```

---

## Recommended Workflow

```
┌─────────────────────────────────────────────────┐
│  START SESSION                                   │
│  ├─ AI reads .context/contextGraph.db           │
│  ├─ AI has full project understanding           │
│  └─ No re-analysis needed                       │
├─────────────────────────────────────────────────┤
│  DURING SESSION                                  │
│  ├─ Every code change → fileMap updated         │
│  ├─ Every decision → decisions[] appended       │
│  ├─ Every new pattern → patterns{} updated      │
│  └─ Every bug found/fixed → knownIssues updated │
├─────────────────────────────────────────────────┤
│  END SESSION                                     │
│  ├─ sessionLog entry added                      │
│  ├─ contextGraph.db saved                       │
│  └─ Ready for next session (any tool, any day)  │
└─────────────────────────────────────────────────┘
```

---

## Per-Tool Setup

### Kiro CLI
Add to your initial message or context:
```
Read .context/contextGraph.db for full project context. Follow the context-first rules: document every change in contextGraph.db, append to sessionLog, and never let context be lost.
```

### Cursor
Add to `.cursorrules`:
```
Always read .context/contextGraph.db at session start.
After every file change, update the relevant contextGraph.db section.
Append to sessionLog at end of each response that modifies code.
```

### VS Code Copilot Chat
Pin `.context/contextGraph.db` as context in every conversation.

### Claude / ChatGPT (manual)
Paste the contextGraph.db contents at the start of each conversation, or upload the file.

---

## Anti-Patterns to Avoid

| ❌ Don't | ✅ Do Instead |
|----------|--------------|
| Add a file without documenting it | Always update fileMap |
| Make a decision without recording why | Always append to decisions[] |
| Start a session without reading context | Always read contextGraph.db first |
| Write long prose descriptions | Keep it 1-2 sentences, factual |
| Forget to log the session | Always append sessionLog entry |
| Let knownIssues grow stale | Review and clean up each session |

---

## Template: Empty contextGraph.db

For bootstrapping a brand new project:

```json
{
  "_meta": {
    "version": "1.0.0",
    "format": "contextGraph",
    "description": "Persistent project context for AI tools.",
    "lastUpdated": "",
    "generatedBy": ""
  },
  "project": {
    "name": "",
    "version": "0.1.0",
    "description": "",
    "author": "",
    "repo": ""
  },
  "techStack": {
    "runtime": "",
    "moduleSystem": "",
    "language": "",
    "framework": "",
    "dependencies": {}
  },
  "architecture": {
    "pattern": "",
    "overview": "",
    "executionFlow": []
  },
  "fileMap": {},
  "dataFlow": {
    "inputs": {},
    "intermediateOutputs": {},
    "finalOutputs": {}
  },
  "patterns": {},
  "conventions": {},
  "environment": {
    "required": [],
    "optional": []
  },
  "scripts": {},
  "knownIssues": [],
  "decisions": [],
  "sessionLog": []
}
```

---

## Why This Works

- **No cold starts** — Every session picks up where the last one left off
- **Tool-agnostic** — JSON is readable by any AI tool, any language, any parser
- **Lightweight** — One file, no database server, no dependencies
- **Git-friendly** — Track context evolution alongside code
- **Self-documenting** — The project explains itself to any AI that reads it
- **Scales** — Works for 5-file scripts and 500-file monorepos alike

---

*Created by Rahul — context-first development practice.*
