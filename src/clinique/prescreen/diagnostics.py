import shutil


def check_cli(cmd):
    path = shutil.which(cmd)
    if path:
        return f"OK ({path})"
    return "Missing"


def run_diagnostics():
    print("==================================================")
    print(" Prescreen Copilot — Agent Diagnostic Report")
    print("==================================================")

    print("\n--- CLI Tool Status ---")
    status = check_cli("codex")
    print(f"  {'codex':<10}: {status}")

    print("\n--- Diagnostic Verdict ---")
    if "OK" in status:
        print("  Status: READY (Codex CLI available)")
        print("  LLM Judge will use Codex CLI.")
        return 0

    print("  Status: ERROR — Codex CLI not available!")
    print("  LLM Judge will fail. Install Codex:")
    print("    npm install -g @codex/cli")
    return 1


if __name__ == "__main__":
    raise SystemExit(run_diagnostics())
