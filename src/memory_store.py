from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from profile_extraction import extract_profile_updates


def estimate_tokens(text: str) -> int:
    """Deterministic character heuristic, not an API billing tokenizer."""
    return (len(text.strip()) + 3) // 4


@dataclass
class UserProfileStore:
    """One editable UTF-8 profile per user, persisted independently of threads."""

    root_dir: Path

    def path_for(self, user_id: str) -> Path:
        if not user_id or not re.fullmatch(r"[\w-]{1,64}", user_id):
            raise ValueError("user_id must contain 1–64 letters, digits, underscores or hyphens.")
        reserved = re.fullmatch(r"(?:con|prn|aux|nul|com[1-9]|lpt[1-9])", user_id, re.I)
        if re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", user_id) and not reserved:
            folder = user_id
        else:
            # '~' is outside the canonical user-id alphabet, separating namespaces.
            folder = "~" + hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:20]
        root = self.root_dir.resolve()
        path = (root / folder / "User.md").resolve()
        if not path.is_relative_to(root):
            raise ValueError("Profile path must stay inside the profile root.")
        return path

    def read_text(self, user_id: str) -> str:
        path = self.path_for(user_id)
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def write_text(self, user_id: str, content: str) -> Path:
        path = self.path_for(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=".User-", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
            os.replace(temp_name, path)
        finally:
            Path(temp_name).unlink(missing_ok=True)
        return path

    def edit_text(self, user_id: str, search_text: str, replacement: str) -> bool:
        if not search_text:
            raise ValueError("search_text must not be empty.")
        original = self.read_text(user_id)
        if search_text not in original:
            return False
        updated = original.replace(search_text, replacement, 1)
        if updated == original:
            return False
        self.write_text(user_id, updated)
        return True

    def file_size(self, user_id: str) -> int:
        path = self.path_for(user_id)
        return path.stat().st_size if path.exists() else 0

    def facts(self, user_id: str) -> dict[str, str]:
        return dict(re.findall(r"^- ([a-z][a-z0-9_]*): (.+)$", self.read_text(user_id), re.M))

    def upsert_fact(self, user_id: str, key: str, value: str) -> bool:
        """Replace a field and duplicate stale lines; preserve other notes."""
        if not re.fullmatch(r"[a-z][a-z0-9_]*", key) or not value.strip() or "\n" in value or "\r" in value:
            raise ValueError("Facts require a valid key and a non-empty single-line value.")
        value = value.strip()
        original = self.read_text(user_id)
        lines = original.splitlines()
        matching = [line for line in lines if line.startswith(f"- {key}: ")]
        new_line = f"- {key}: {value}"
        if matching == [new_line]:
            return False
        lines = [line for line in lines if not line.startswith(f"- {key}: ")]
        if not lines:
            lines = ["# User profile", ""]
        lines.append(new_line)
        self.write_text(user_id, "\n".join(lines) + "\n")
        return True


def _summary_parts(summary: str) -> tuple[dict[str, str], list[str]]:
    lines = summary.splitlines()
    facts = {}
    if lines and lines[0].startswith("Facts: "):
        try:
            data = json.loads(lines[0][7:])
            if isinstance(data, dict):
                facts = {key: value for key, value in data.items() if isinstance(value, str)}
        except (ValueError, TypeError):
            pass
    notes = [line[2:] for line in lines[2:] if line.startswith("- ")]
    return facts, notes


def summarize_messages(messages: list[dict[str, str]], max_items: int = 6) -> str:
    """Retain profile facts plus short notes; summaries may lose fine detail."""
    if type(max_items) is not int or max_items <= 0:
        raise ValueError("max_items must be a positive integer.")
    if not messages:
        return ""
    facts: dict[str, str] = {}
    notes: list[str] = []
    for message in messages:
        role, content = message["role"], message["content"]
        if role == "memory":
            prior_facts, prior_notes = _summary_parts(content)
            facts.update(prior_facts)
            notes.extend(prior_notes)
            continue
        if role == "user":
            facts.update(extract_profile_updates(content))
        snippet = " ".join(content.split())[:160]
        note = f"{role}: {snippet}"
        if note in notes:
            notes.remove(note)
        notes.append(note)
    selected = notes[-max_items:]
    return "Facts: " + json.dumps(facts, ensure_ascii=False, sort_keys=True) + "\nNotes:\n" + "\n".join(
        "- " + note for note in selected
    )


@dataclass
class CompactMemoryManager:
    """Per-thread bounded history; the trigger threshold is not a hard ceiling."""

    threshold_tokens: int
    keep_messages: int
    state: dict[str, dict[str, object]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if any(type(value) is not int or value <= 0 for value in (self.threshold_tokens, self.keep_messages)):
            raise ValueError("Compact threshold and keep_messages must be positive integers.")

    def append(self, thread_id: str, role: str, content: str) -> None:
        current = self.state.setdefault(thread_id, {"messages": [], "summary": "", "compactions": 0})
        messages = current["messages"]
        messages.append({"role": role, "content": content})
        before = estimate_tokens(current["summary"]) + sum(estimate_tokens(item["content"]) for item in messages)
        if before <= self.threshold_tokens or len(messages) <= self.keep_messages:
            return
        older, recent = messages[:-self.keep_messages], messages[-self.keep_messages:]
        inputs = ([{"role": "memory", "content": current["summary"]}] if current["summary"] else []) + older
        summary = summarize_messages(inputs, max_items=min(6, max(1, self.threshold_tokens // 120)))
        # Reserve budget for notes, without deleting recognized profile facts.
        summary_facts, notes = _summary_parts(summary)
        header = "Facts: " + json.dumps(summary_facts, ensure_ascii=False, sort_keys=True) + "\nNotes:\n"
        budget = max(0, self.threshold_tokens - len(header))
        note_text = "\n".join("- " + note for note in notes)
        summary = header + note_text[:budget]
        after = estimate_tokens(summary) + sum(estimate_tokens(item["content"]) for item in recent)
        if after < before:
            current.update(messages=recent, summary=summary, compactions=current["compactions"] + 1)

    def context(self, thread_id: str) -> dict[str, object]:
        return deepcopy(self.state.get(thread_id, {"messages": [], "summary": "", "compactions": 0}))

    def compaction_count(self, thread_id: str) -> int:
        return self.state.get(thread_id, {}).get("compactions", 0)
