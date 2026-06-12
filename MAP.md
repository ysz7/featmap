<!-- featmap v1 -->
# Project: featmap

CLI tool for an AI-maintained project feature map (MAP.md).
Makes no LLM calls itself: files, parser, validator — the intelligence is the assistant's.

## Layer: CLI

Entry point: argument parsing, repo root discovery, exit codes.

### Commands init / check / links / version {#cli-commands}

**What:** Parses arguments, prints violations as `MAP.md:<line>: <CODE>` and returns exit codes (1 on errors, `--strict` for warnings).
**Files:** `src/featmap/cli.py`
**Depends:** [MAP.md parser](#map-parser), [Validator](#validator), [Reverse links](#reverse-links), [Initializer](#initializer)
**Status:** active

## Layer: Core

Deterministic parsing and validation of the map, no heuristics and no LLM.

### MAP.md parser {#map-parser}

**What:** Parses MAP.md line by line into a data model with line numbers; reports format rule violations F1-F10 as E1.
**Files:** `src/featmap/parser.py`
**Depends:** —
**Status:** active
**Used by:** <!-- autogen --> [Commands init / check / links / version](#cli-commands), [Validator](#validator), [Reverse links](#reverse-links)

### Validator {#validator}

**What:** Semantic checks on top of the model: E2-E4, W1-W4 and V10 (`check --staged`: a staged feature file without staged changes to its section).
**Files:** `src/featmap/validator.py`
**Depends:** [MAP.md parser](#map-parser), [Reverse links](#reverse-links), [Git utilities](#git-utils)
**Status:** active
**Used by:** <!-- autogen --> [Commands init / check / links / version](#cli-commands)

### Reverse links {#reverse-links}

**What:** Computes reverse edges from `**Depends:**` and regenerates `**Used by:**` lines without touching the rest of the file.
**Files:** `src/featmap/links.py`
**Depends:** [MAP.md parser](#map-parser)
**Status:** active
**Used by:** <!-- autogen --> [Commands init / check / links / version](#cli-commands), [Validator](#validator)

## Layer: Project integration

Artifacts that featmap places into the user's repository.

### Initializer {#initializer}

**What:** Idempotently creates MAP.md, the rules block between featmap:rules markers in AGENTS.md/CLAUDE.md, installs the pre-commit hook, prints the bootstrap prompt for non-empty projects.
**Files:** `src/featmap/initializer.py`, `src/featmap/templates/MAP.template.md`, `src/featmap/templates/agents_rules.md`, `src/featmap/templates/pre-commit`
**Depends:** —
**Status:** active
**Used by:** <!-- autogen --> [Commands init / check / links / version](#cli-commands)

### Git utilities {#git-utils}

**What:** Wrappers around subprocess git: repo root, staged file list, changed line ranges of the staged MAP.md diff.
**Files:** `src/featmap/gitutils.py`
**Depends:** —
**Status:** active
**Used by:** <!-- autogen --> [Validator](#validator)
