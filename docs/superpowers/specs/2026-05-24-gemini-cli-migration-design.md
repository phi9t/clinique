# Design Spec: Gemini CLI to Antigravity CLI Migration

**Date**: 2026-05-24
**Status**: Proposed

## 1. Goal
Add the official Gemini CLI (`gcli`) migration documentation to `docs/gcli-migration.md` and create a reusable Antigravity CLI skill to automate and guide the installation/configuration of tools, skills, and MCPs designed for Gemini CLI into the Antigravity CLI (`agy`).

## 2. Proposed Changes

### 2.1 Documentation Update
We will replace the placeholder in [gcli-migration.md](file:///Users/phi9t/CodeBase/clinique/docs/gcli-migration.md) with the fully rendered and cleaned documentation scraped from the official site.

### 2.2 Skill: `gemini-cli-migration`
We will create a new skill in the global skills directory:
`/Users/phi9t/.gemini/antigravity-cli/skills/gemini-cli-migration/`

The skill structure will be:
```
gemini-cli-migration/
├── SKILL.md
├── agents/
│   └── openai.yaml
└── scripts/
    └── migrate.py
```

#### 2.2.1 `scripts/migrate.py`
A Python script that handles the configuration conversion and file relocation:
- **Global Migration**:
  - Locates `~/.gemini/settings.json`.
  - Extract the `mcpServers` section, rewriting keys `url` and `httpUrl` to `serverUrl`.
  - Merges into `~/.gemini/antigravity-cli/mcp_config.json`.
  - Copies global skills from `~/.gemini/skills/` to `~/.gemini/antigravity-cli/skills/`.
- **Workspace Migration** (if run within a workspace directory):
  - Locates `.gemini/settings.json` and moves/migrates it to `.agents/mcp_config.json`.
  - Relocates `.gemini/skills/` to `.agents/skills/`.
  - Performs validation checks on the resulting JSON files.

#### 2.2.2 `SKILL.md`
Contains clear, step-by-step instructions for the agent:
1. Detect whether the user has a legacy Gemini CLI environment (global or local workspace).
2. Invoke the migration script: `python3 scripts/migrate.py`.
3. Check and import plugins using `agy plugin import gemini`.
4. Verify config validity and list the migrated resources.

## 3. Verification Plan
- **Unit/Manual Tests**:
  - Run `migrate.py` with mock `settings.json` input containing remote and local MCP servers.
  - Run the `quick_validate.py` tool on the new skill to ensure it conforms to skill constraints.
  - Check that the output `mcp_config.json` validates as correct JSON with converted `serverUrl` keys.
