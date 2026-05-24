from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ChecklistAudit:
    complete_sections: tuple[str, ...]
    incomplete_sections: tuple[str, ...]
    blocked_requirements: tuple[str, ...]
    goal_complete: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "complete_sections": list(self.complete_sections),
            "incomplete_sections": list(self.incomplete_sections),
            "blocked_requirements": list(self.blocked_requirements),
            "goal_complete": self.goal_complete,
        }


def audit_release_checklist(path: str | Path) -> ChecklistAudit:
    current_section: str | None = None
    section_items: dict[str, list[tuple[bool, str]]] = {}
    for line in Path(path).read_text().splitlines():
        if line.startswith("## "):
            current_section = line.removeprefix("## ").strip()
            section_items.setdefault(current_section, [])
            continue
        match = re.match(r"^- \[(?P<mark>[ xX])\] (?P<text>.+)$", line)
        if match and current_section is not None:
            checked = match.group("mark").lower() == "x"
            text = match.group("text").strip()
            section_items[current_section].append((checked, text))

    complete_sections: list[str] = []
    incomplete_sections: list[str] = []
    blocked: list[str] = []
    for section, items in section_items.items():
        if items and all(checked for checked, _ in items):
            complete_sections.append(section)
        elif items:
            incomplete_sections.append(section)
            blocked.extend(_requirement_id(section, text) for checked, text in items if not checked)

    return ChecklistAudit(
        complete_sections=tuple(complete_sections),
        incomplete_sections=tuple(incomplete_sections),
        blocked_requirements=tuple(blocked),
        goal_complete=not blocked,
    )


def _requirement_id(section: str, text: str) -> str:
    section_id = re.sub(r"[^a-zA-Z0-9]+", "_", section).strip("_").lower()
    item_id = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return f"{section_id}__{item_id}"
