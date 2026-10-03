"""Replay public user turns to inspect memory, without calling an agent or API.

Context totals exclude assistant replies, recall questions and User.md prompt
injection. This is a layer check, not the final two-agent benchmark.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from memory_store import CompactMemoryManager, UserProfileStore, estimate_tokens, extract_profile_updates


def check_suite(path: Path, threshold: int, keep: int) -> dict:
    conversations = json.loads(path.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as directory:
        store = UserProfileStore(Path(directory))
        manager = CompactMemoryManager(threshold, keep)
        raw_load = compact_load = turns = 0
        for conversation in conversations:
            history = []
            for turn in conversation["turns"]:
                turns += 1
                for key, value in extract_profile_updates(turn).items():
                    store.upsert_fact(conversation["user_id"], key, value)
                history.append(turn)
                manager.append(conversation["id"], "user", turn)
                context = manager.context(conversation["id"])
                raw_load += sum(estimate_tokens(text) for text in history)
                compact_load += estimate_tokens(context["summary"]) + sum(
                    estimate_tokens(item["content"]) for item in context["messages"]
                )
        user_id = conversations[-1]["user_id"]
        return {
            "dataset": path.name,
            "user_turns": turns,
            "profile": store.facts(user_id),
            "profile_bytes": store.file_size(user_id),
            "raw_context_tokens": raw_load,
            "compact_context_tokens": compact_load,
            "context_reduction_percent": round((1 - compact_load / raw_load) * 100, 2) if raw_load else 0,
            "compactions": sum(manager.compaction_count(item["id"]) for item in conversations),
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--threshold", type=int, default=2000)
    parser.add_argument("--keep", type=int, default=6)
    args = parser.parse_args()
    result = {
        "mode": "offline-memory-layer-only",
        "estimator": "ceil(stripped characters / 4)",
        "threshold_tokens": args.threshold,
        "keep_messages": args.keep,
        "suites": [check_suite(ROOT / "data" / name, args.threshold, args.keep)
                   for name in ("conversations.json", "advanced_long_context.json")],
    }
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
