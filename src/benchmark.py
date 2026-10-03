from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
import hashlib
import json
from pathlib import Path
from statistics import mean
import sys
from tempfile import TemporaryDirectory
from typing import Any
import unicodedata
from uuid import uuid4

from agent_advanced import AdvancedAgent
from agent_baseline import BaselineAgent
from config import LabConfig, load_config


@dataclass
class BenchmarkRow:
    agent_name: str
    agent_tokens_only: int
    prompt_tokens_processed: int
    recall_score: float
    response_quality: float
    memory_growth_bytes: int
    compactions: int


def load_conversations(path: Path) -> list[dict[str, Any]]:
    """Read UTF-8 JSON and fail before running an invalid benchmark."""
    conversations = json.loads(path.read_text(encoding="utf-8-sig"))
    _validate_conversations(conversations)
    return conversations


def _nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _validate_expected(expected: Any) -> None:
    if not isinstance(expected, list) or not expected or not all(map(_nonempty_text, expected)):
        raise ValueError("expected_contains must be a non-empty list of non-empty strings.")


def _validate_conversations(conversations: Any) -> None:
    if not isinstance(conversations, list):
        raise ValueError("Dataset must be a list of conversations.")
    for index, conversation in enumerate(conversations):
        if not isinstance(conversation, dict):
            raise ValueError(f"Conversation {index} must be an object.")
        for key in ("id", "user_id"):
            if not _nonempty_text(conversation.get(key)):
                raise ValueError(f"Conversation {index}: {key} must be non-empty text.")
        turns = conversation.get("turns")
        if not isinstance(turns, list) or not all(map(_nonempty_text, turns)):
            raise ValueError(f"Conversation {index}: turns must be a list of non-empty strings.")
        questions = conversation.get("recall_questions")
        if not isinstance(questions, list):
            raise ValueError(f"Conversation {index}: recall_questions must be a list.")
        for question in questions:
            if not isinstance(question, dict) or not _nonempty_text(question.get("question")):
                raise ValueError(f"Conversation {index}: recall question must have non-empty text.")
            _validate_expected(question.get("expected_contains"))


def _normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def _match_count(answer: str, expected: list[str]) -> int:
    _validate_expected(expected)
    normalized = _normalize(answer)
    return sum(_normalize(fact) in normalized for fact in expected)


def recall_points(answer: str, expected: list[str]) -> float:
    """Substring recall: none = 0, some = 0.5, all = 1 (not semantic scoring)."""
    matched = _match_count(answer, expected)
    return 1.0 if matched == len(expected) else 0.5 if matched else 0.0


def heuristic_quality(answer: str, expected: list[str]) -> float:
    """Expected fact coverage on recall answers, not general response quality."""
    return _match_count(answer, expected) / len(expected)


def run_agent_benchmark(
    agent_name: str, agent, conversations: list[dict[str, Any]], config: LabConfig,
    *, records: list[dict[str, Any]] | None = None,
) -> BenchmarkRow:
    """Measure this run, scoring recall before later corrections enter memory.

    The caller owns the agent/state lifecycle; run_benchmarks supplies fresh
    agents and temporary state. Existing memory is measured as a byte delta.
    Both token columns include training and evaluation calls. Every recall
    question gets its own fresh thread, so answers cannot seed later questions.
    """
    _validate_conversations(conversations)
    users = {conversation["user_id"] for conversation in conversations}
    file_size = getattr(agent, "memory_file_size", lambda user: 0)
    before_bytes = sum(file_size(user) for user in users)
    trace = records if records is not None else []
    output_tokens = input_tokens = compactions = 0
    recalls: list[float] = []
    qualities: list[float] = []
    run_id = uuid4().hex

    def measure(conversation, thread_id, message, phase, expected=None):
        nonlocal output_tokens, input_tokens, compactions
        before_compactions = agent.compaction_count(thread_id)
        result = agent.reply(conversation["user_id"], thread_id, message)
        compact_delta = agent.compaction_count(thread_id) - before_compactions
        output_tokens += result["agent_tokens"]
        input_tokens += result["prompt_tokens"]
        compactions += compact_delta
        record = {
            "conversation_id": conversation["id"], "user_id": conversation["user_id"],
            "thread_id": thread_id, "phase": phase, "message": message,
            "answer": result["response"], "mode": result["mode"],
            "token_source": result["token_source"], "agent_tokens": result["agent_tokens"],
            "prompt_tokens": result["prompt_tokens"], "compactions_delta": compact_delta,
        }
        if expected is not None:
            recall = recall_points(result["response"], expected)
            quality = heuristic_quality(result["response"], expected)
            recalls.append(recall)
            qualities.append(quality)
            record.update(expected_contains=list(expected), recall_score=recall, response_quality=quality)
        trace.append(record)

    for index, conversation in enumerate(conversations):
        training_thread = f"{run_id}:conversation:{index}"
        for message in conversation["turns"]:
            measure(conversation, training_thread, message, "training")
        # Keep profile across conversations, but never defer scoring to suite end.
        for question_index, question in enumerate(conversation["recall_questions"]):
            measure(conversation, f"{run_id}:recall:{index}:{question_index}",
                    question["question"], "recall", question["expected_contains"])

    return BenchmarkRow(
        agent_name, output_tokens, input_tokens,
        mean(recalls) if recalls else 0.0, mean(qualities) if qualities else 0.0,
        sum(file_size(user) for user in users) - before_bytes, compactions,
    )


def format_rows(rows: list[BenchmarkRow]) -> str:
    """Use the lab's required columns; percentages share a 0–1 scale."""
    header = ("| Agent | Agent tokens only | Prompt tokens processed | Cross-session recall | "
              "Response quality | Memory growth (bytes) | Compactions |")
    lines = [header, "|---|---:|---:|---:|---:|---:|---:|"]
    for row in rows:
        lines.append(
            f"| {row.agent_name} | {row.agent_tokens_only} | {row.prompt_tokens_processed} | "
            f"{row.recall_score:.2%} | {row.response_quality:.2%} | {row.memory_growth_bytes} | {row.compactions} |"
        )
    return "\n".join(lines)


def run_benchmarks(config: LabConfig) -> dict[str, Any]:
    """Run original fixtures with fresh state per agent/suite, leaving demo intact."""
    payload: dict[str, Any] = {
        "mode": config.mode, "token_source": "heuristic",
        "quality_source": "expected_contains fact coverage on recall answers; no LLM judge",
        "recall_source": "normalized substring match: none=0, partial=0.5, all=1",
        "token_scope": "all completed training and recall calls; excludes extraction/summary/judge cost",
        "state": "temporary, isolated per agent and suite",
        "compact_threshold_tokens": config.compact_threshold_tokens,
        "compact_keep_messages": config.compact_keep_messages,
        "suites": [],
    }
    if config.mode == "live":
        payload["model"] = {"provider": config.model.provider, "name": config.model.model_name}
    for title, filename in (
        ("Standard Benchmark", "conversations.json"),
        ("Long-Context Stress Benchmark", "advanced_long_context.json"),
    ):
        dataset = config.data_dir / filename
        conversations = load_conversations(dataset)
        suite: dict[str, Any] = {
            "name": title, "dataset": f"data/{filename}",
            "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
            "conversations": len(conversations),
            "turns": sum(len(c["turns"]) for c in conversations),
            "recall_questions": sum(len(c["recall_questions"]) for c in conversations),
            "rows": [], "agents": {},
        }
        for name, cls in (("Baseline", BaselineAgent), ("Advanced", AdvancedAgent)):
            with TemporaryDirectory(prefix="day17-benchmark-") as state:
                isolated = replace(config, state_dir=Path(state))
                agent = cls(isolated, force_offline=config.mode == "offline")
                records: list[dict[str, Any]] = []
                row = run_agent_benchmark(name, agent, conversations, isolated, records=records)
                suite["rows"].append(asdict(row))
                suite["agents"][name] = {
                    "phase_totals": {
                        phase: {
                            "calls": sum(r["phase"] == phase for r in records),
                            "agent_tokens": sum(r["agent_tokens"] for r in records if r["phase"] == phase),
                            "prompt_tokens": sum(r["prompt_tokens"] for r in records if r["phase"] == phase),
                            "compactions": sum(r["compactions_delta"] for r in records if r["phase"] == phase),
                        }
                        for phase in ("training", "recall")
                    },
                    "profiles": {
                        user: agent.profile_store.read_text(user)
                        for user in sorted({c["user_id"] for c in conversations})
                    } if isinstance(agent, AdvancedAgent) else {},
                    "records": records,
                }
        payload["suites"].append(suite)
    return payload


def _positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Day 17 memory benchmark (offline by default).")
    parser.add_argument("--mode", choices=("offline", "live"), default="offline",
                        help="live explicitly calls the configured model; all scores stay heuristic")
    parser.add_argument("--compact-threshold", type=_positive_int)
    parser.add_argument("--keep-messages", type=_positive_int)
    parser.add_argument("--output", type=Path, help="save UTF-8 JSON evidence")
    args = parser.parse_args(argv)
    config = load_config(Path(__file__).resolve().parent.parent)
    config = replace(config, mode=args.mode,
                     compact_threshold_tokens=args.compact_threshold or config.compact_threshold_tokens,
                     compact_keep_messages=args.keep_messages or config.compact_keep_messages)
    payload = run_benchmarks(config)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(f"Mode: {config.mode}. Tokens: heuristic. Quality: recall fact coverage, no LLM judge.")
    print("Token columns include training + recall. State is temporary and isolated.\n")
    for suite in payload["suites"]:
        print(suite["name"])
        print(format_rows([BenchmarkRow(**row) for row in suite["rows"]]))
        baseline, advanced = suite["rows"]
        if baseline["prompt_tokens_processed"]:
            reduction = 1 - advanced["prompt_tokens_processed"] / baseline["prompt_tokens_processed"]
            print(f"Advanced prompt reduction vs Baseline: {reduction:.2%}\n")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Evidence: {args.output.resolve()}")


if __name__ == "__main__":
    main()
