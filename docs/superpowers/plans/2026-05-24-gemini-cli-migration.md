# Gemini CLI Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a migration path from Gemini CLI to Antigravity CLI by populating official migration docs in `docs/gcli-migration.md` and adding a new reusable skill `gemini-cli-migration` to automate setup.

**Architecture:** The skill uses an automated Python migration script (`scripts/migrate.py`) to parse and transform JSON configurations (migrating `mcpServers` and mapping `url`/`httpUrl` to `serverUrl`) and relocate global/workspace skill directories, backed by step-by-step instructions in `SKILL.md`.

**Tech Stack:** Python 3 (standard libraries `os`, `json`, `shutil`), Antigravity CLI skills model.

---

### Task 1: Update Migration Documentation

**Files:**
- Modify: `docs/gcli-migration.md`

- [ ] **Step 1: Write migration documentation**

Write the official documentation scraped from `https://antigravity.google/docs/gcli-migration` with site chrome removed.

```markdown
# Migrating from Gemini CLI

If you are an existing Gemini CLI user looking to migrate your workflow to Antigravity CLI, you have come to the right place. The guide below will help you get familiar with and up and running quickly in Antigravity CLI.

> [!NOTE]
> **TL;DR:** Antigravity CLI supports the majority of features from Gemini CLI. While there is not 100% feature parity, workflow defining features like Gemini CLI extensions (Antigravity plugins), Agent Skills, MCP servers, hooks, and subagents are all supported in Antigravity CLI.

On the first launch of Antigravity CLI, you should see Migration Options where you can choose to migrate your existing Gemini CLI extensions to the equivalent Antigravity Plugins.

> [!NOTE]
> Some Gemini CLI extensions cannot be migrated 1:1 to Antigravity plugins as some components (e.g., custom themes) are not currently supported.

For the majority of users, you can now get started using Antigravity CLI with the workflows you have come to love in Gemini CLI. Antigravity CLI loads in the same context files and global Agent Skills as Gemini CLI does.

---

## Gemini CLI Extensions → Antigravity Plugins

Since Gemini CLI launched extensions (a way to extend the CLI by bundling and sharing capabilities), the industry has standardized on the term plugins. Antigravity plugins are supported in Antigravity CLI.

Users should be prompted on the first launch of Antigravity CLI to have their extensions automatically migrated to plugins. You can also run an explicit command from your terminal to migrate them:

```bash
agy plugin import gemini
```

Running the `agy plugin import` command will search for each locally installed extension and convert them to an Antigravity plugin.

---

## Context Files (Rules)

Antigravity CLI supports the same context files as Gemini CLI:
* **Workspace Context:** Reads both `GEMINI.md` and `AGENTS.md` from your active workspace directory.
* **Global Context:** Automatically loads and enforces global constraints located at `~/.gemini/GEMINI.md`.

---

## Agent Skills

Agent Skills work in Antigravity CLI just as they do in Gemini CLI. They can be managed with the same `/skills` command and are also converted into slash commands allowing them to be manually invoked.

Global skills for Gemini CLI were located in `~/.gemini/skills/` and are shared with Antigravity CLI across all workspaces. No action is needed for global skills; they are picked up automatically.

Workspace-specific skills for Antigravity CLI are stored in `.agents/skills`, which means if you have project/workspace skills in a given project within the `.gemini/skills` folder, they will need to be moved to `.agents/skills`.

| Attribute | Gemini CLI | Antigravity CLI |
| :--- | :--- | :--- |
| **Location** | Global: `~/.gemini/skills/`<br>Workspace: `.gemini/skills/` or `.agents/skills/` | Global: `~/.gemini/antigravity-cli/skills/`<br>Workspace: `.agents/skills/` |
| **Management** | `/skills` | `/skills` |
| **Behavior** | Skills become slash commands | Skills become slash commands |

> [!NOTE]
> Antigravity CLI does not currently have an equivalent to the `gemini skills` command for managing Agent Skills on your terminal. You can create your own skills files manually or use `npx skills install`.

---

## MCP Servers

Antigravity CLI supports both local and remote MCP servers and provides the same `/mcp` command to manage them. The main difference from Gemini CLI is the file location where mcpServers are defined.

Antigravity and Antigravity CLI store MCP server configurations in a distinct `mcp_config.json` file, whereas Gemini CLI stores them inline in your `settings.json`.

> [!IMPORTANT]
> Antigravity CLI uses the `serverUrl` field instead of `url` (or the deprecated `httpUrl`) for remote MCP servers.

| Attribute | Gemini CLI | Antigravity CLI |
| :--- | :--- | :--- |
| **Location** | Global: `~/.gemini/settings.json`<br>Workspace: `.gemini/settings.json` | Global: `~/.gemini/antigravity-cli/mcp_config.json`<br>Workspace: `.agents/mcp_config.json` |
| **Management** | `/mcp` | `/mcp` |
```

- [ ] **Step 2: Commit documentation changes**

```bash
git add docs/gcli-migration.md
git commit -m "docs: add gemini-cli migration guide"
```

---

### Task 2: Initialize new Skill

**Files:**
- Create: `/Users/phi9t/.gemini/antigravity-cli/skills/gemini-cli-migration/`

- [ ] **Step 1: Run init_skill.py**

Run:
```bash
python3 /Users/phi9t/.gemini/antigravity-cli/skills/skill-creator/scripts/init_skill.py gemini-cli-migration --path /Users/phi9t/.gemini/antigravity-cli/skills --resources scripts --interface display_name="Gemini CLI Migration" --interface short_description="Migrate configs, skills, and MCPs from Gemini CLI to Antigravity CLI" --interface default_prompt="Help me migrate my settings and skills from Gemini CLI"
```

Expected: Command runs successfully, creating the skill folder, YAML frontmatter, and `agents/openai.yaml`.

- [ ] **Step 2: Commit initialized skill**

```bash
git add /Users/phi9t/.gemini/antigravity-cli/skills/gemini-cli-migration/
git commit -m "feat(skill): initialize gemini-cli-migration skill folder"
```

---

### Task 3: Implement Migration Script

**Files:**
- Create: `/Users/phi9t/.gemini/antigravity-cli/skills/gemini-cli-migration/scripts/migrate.py`

- [ ] **Step 1: Write python migration script**

Write the logic for converting MCP configs and migrating skills directories.

```python
#!/usr/bin/env python3
import os
import json
import shutil
import sys

def migrate_mcp_config(src_file, dest_file):
    if not os.path.exists(src_file):
        print(f"No source MCP settings file found at {src_file}")
        return False
    try:
        with open(src_file, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading {src_file}: {e}")
        return False

    # Extract mcpServers configuration
    mcp_servers = data.get("mcpServers", {})
    if not mcp_servers:
        if "mcpServers" not in data:
            print(f"No 'mcpServers' configuration found in {src_file}")
            # If the format is just the MCP config direct
            if isinstance(data, dict) and any("command" in v or "url" in v for v in data.values()):
                mcp_servers = data
    
    # Rewrite keys for remote servers: url or httpUrl to serverUrl
    migrated_servers = {}
    for server_name, server_config in mcp_servers.items():
        if not isinstance(server_config, dict):
            continue
        migrated_config = server_config.copy()
        if "url" in migrated_config:
            migrated_config["serverUrl"] = migrated_config.pop("url")
        if "httpUrl" in migrated_config:
            migrated_config["serverUrl"] = migrated_config.pop("httpUrl")
        migrated_servers[server_name] = migrated_config

    if not migrated_servers:
        print("No servers parsed to migrate.")
        return False

    # Create destination directory if needed
    os.makedirs(os.path.dirname(dest_file), exist_ok=True)

    # Merge if dest_file already exists
    existing_config = {}
    if os.path.exists(dest_file):
        try:
            with open(dest_file, 'r') as f:
                existing_config = json.load(f)
        except Exception as e:
            print(f"Warning: could not parse existing destination config: {e}")

    # Merge mcpServers
    existing_mcp = existing_config.setdefault("mcpServers", {})
    existing_mcp.update(migrated_servers)

    try:
        with open(dest_file, 'w') as f:
            json.dump(existing_config, f, indent=2)
        print(f"Successfully migrated MCP configs to {dest_file}")
        return True
    except Exception as e:
        print(f"Error writing destination config: {e}")
        return False

def migrate_skills(src_dir, dest_dir):
    if not os.path.exists(src_dir):
        print(f"No skills folder found at {src_dir}")
        return False
    
    os.makedirs(dest_dir, exist_ok=True)
    migrated_any = False
    for item in os.listdir(src_dir):
        src_path = os.path.join(src_dir, item)
        dest_path = os.path.join(dest_dir, item)
        
        # Skip hidden files
        if item.startswith('.'):
            continue
            
        try:
            if os.path.isdir(src_path):
                if os.path.exists(dest_path):
                    shutil.rmtree(dest_path)
                shutil.copytree(src_path, dest_path)
            else:
                shutil.copy2(src_path, dest_path)
            print(f"Migrated skill: {item}")
            migrated_any = True
        except Exception as e:
            print(f"Failed to migrate {item}: {e}")
            
    return migrated_any

def main():
    home = os.path.expanduser("~")
    gemini_global_settings = os.path.join(home, ".gemini", "settings.json")
    gemini_global_skills = os.path.join(home, ".gemini", "skills")
    
    antigravity_global_config = os.path.join(home, ".gemini", "antigravity-cli", "mcp_config.json")
    antigravity_global_skills = os.path.join(home, ".gemini", "antigravity-cli", "skills")
    
    print("--- Starting Global Migration ---")
    migrate_mcp_config(gemini_global_settings, antigravity_global_config)
    migrate_skills(gemini_global_skills, antigravity_global_skills)
    
    print("\n--- Starting Workspace Migration ---")
    cwd = os.getcwd()
    gemini_local_settings = os.path.join(cwd, ".gemini", "settings.json")
    gemini_local_skills = os.path.join(cwd, ".gemini", "skills")
    
    antigravity_local_config = os.path.join(cwd, ".agents", "mcp_config.json")
    antigravity_local_skills = os.path.join(cwd, ".agents", "skills")
    
    migrate_mcp_config(gemini_local_settings, antigravity_local_config)
    migrate_skills(gemini_local_skills, antigravity_local_skills)
    
    print("\nMigration finished. Remember to run 'agy plugin import gemini' if you have plugins/extensions.")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Make migration script executable**

Run: `chmod +x /Users/phi9t/.gemini/antigravity-cli/skills/gemini-cli-migration/scripts/migrate.py`

- [ ] **Step 3: Commit migration script**

```bash
git add /Users/phi9t/.gemini/antigravity-cli/skills/gemini-cli-migration/scripts/migrate.py
git commit -m "feat(skill): implement migrate.py script for gemini migration"
```

---

### Task 4: Complete SKILL.md Instructions

**Files:**
- Modify: `/Users/phi9t/.gemini/antigravity-cli/skills/gemini-cli-migration/SKILL.md`

- [ ] **Step 1: Write SKILL.md**

Write the complete instruction file.

```markdown
---
name: gemini-cli-migration
description: Use when the user wants to migrate or configure tools, skills, or MCPs originally designed for the Gemini CLI into the Antigravity CLI (agy).
---

# Gemini CLI Migration Skill

This skill guides and automates the migration of legacy Gemini CLI configurations, skills, and plugins to Antigravity CLI (`agy`).

## Workflow

Follow these step-by-step instructions:

### 1. Check for Legacy Gemini CLI Setup
Verify if the legacy Gemini CLI files exist on the system or in the workspace:
- Global: `~/.gemini/settings.json` and `~/.gemini/skills/`
- Workspace: `.gemini/settings.json` and `.gemini/skills/`

### 2. Run the Automated Migration Script
Execute the migration script to copy and convert MCP settings and skills:
```bash
python3 /Users/phi9t/.gemini/antigravity-cli/skills/gemini-cli-migration/scripts/migrate.py
```

### 3. Migrate Plugins/Extensions
Run the Antigravity CLI command to import legacy plugins:
```bash
agy plugin import gemini
```

### 4. Verification
Confirm that configuration files are valid and contain converted fields:
- Check `~/.gemini/antigravity-cli/mcp_config.json` for proper syntax and verified key conversion (e.g. `serverUrl` used instead of `url`/`httpUrl`).
- Check `.agents/mcp_config.json` for workspace configurations if applicable.
```

- [ ] **Step 2: Commit SKILL.md changes**

```bash
git add /Users/phi9t/.gemini/antigravity-cli/skills/gemini-cli-migration/SKILL.md
git commit -m "feat(skill): complete SKILL.md instructions"
```

---

### Task 5: Validation & Testing

**Files:**
- Create: `/Users/phi9t/CodeBase/clinique/scratch/test_migrate_input.json`
- Create: `/Users/phi9t/CodeBase/clinique/scratch/test_migrate.py`

- [ ] **Step 1: Run skill validation tool**

Run: `python3 /Users/phi9t/.gemini/antigravity-cli/skills/skill-creator/scripts/quick_validate.py /Users/phi9t/.gemini/antigravity-cli/skills/gemini-cli-migration`
Expected: Validates successfully without errors.

- [ ] **Step 2: Create mock input and test runner**

Create `/Users/phi9t/CodeBase/clinique/scratch/test_migrate_input.json`:
```json
{
  "mcpServers": {
    "sqlite": {
      "command": "uv",
      "args": ["run", "mcp-server-sqlite"]
    },
    "web-search": {
      "url": "https://mcp.example.com/search"
    },
    "legacy-http": {
      "httpUrl": "http://mcp.legacy.com/api"
    }
  }
}
```

Create `/Users/phi9t/CodeBase/clinique/scratch/test_migrate.py`:
```python
import os
import json
import shutil
import sys

# Add migrate script path to sys.path
sys.path.insert(0, "/Users/phi9t/.gemini/antigravity-cli/skills/gemini-cli-migration/scripts")
import migrate

def run_test():
    test_input = "/Users/phi9t/CodeBase/clinique/scratch/test_migrate_input.json"
    test_output = "/Users/phi9t/CodeBase/clinique/scratch/test_migrate_output.json"
    
    if os.path.exists(test_output):
        os.remove(test_output)
        
    print("Testing migration function...")
    res = migrate.migrate_mcp_config(test_input, test_output)
    assert res is True
    
    with open(test_output, 'r') as f:
        out_data = json.load(f)
        
    servers = out_data.get("mcpServers", {})
    assert "sqlite" in servers
    assert "web-search" in servers
    assert "legacy-http" in servers
    
    assert servers["web-search"].get("serverUrl") == "https://mcp.example.com/search"
    assert "url" not in servers["web-search"]
    
    assert servers["legacy-http"].get("serverUrl") == "http://mcp.legacy.com/api"
    assert "httpUrl" not in servers["legacy-http"]
    
    print("All tests passed successfully!")

if __name__ == "__main__":
    run_test()
```

- [ ] **Step 3: Run the test runner**

Run: `python3 /Users/phi9t/CodeBase/clinique/scratch/test_migrate.py`
Expected: "All tests passed successfully!" printed.

- [ ] **Step 4: Cleanup scratch test files**

Run: `rm /Users/phi9t/CodeBase/clinique/scratch/test_migrate_input.json /Users/phi9t/CodeBase/clinique/scratch/test_migrate_output.json /Users/phi9t/CodeBase/clinique/scratch/test_migrate.py`
Expected: Files deleted, workspace clean.
