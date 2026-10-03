"""Six real generation calls, synthetic facts, temporary state, no raw SDK errors."""
from __future__ import annotations

import argparse
from dataclasses import replace
import json
import os
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_advanced import AdvancedAgent
from agent_baseline import BaselineAgent
from benchmark import recall_points
from config import LabConfig, load_config


def run_check(config: LabConfig) -> dict:
    from langsmith import tracing_context
    result = {"mode": "live", "provider": config.model.provider,
              "model": config.model.model_name, "state": "temporary",
              "facts": "synthetic-demo", "token_source": "heuristic",
              "records": [], "checks": {}, "status": "failed"}
    with TemporaryDirectory(prefix="day17-live-") as directory, tracing_context(enabled=False):
        live_config = replace(config, mode="live", state_dir=Path(directory))

        def build():
            agents = {"Baseline": BaselineAgent(live_config), "Advanced": AdvancedAgent(live_config)}
            for agent in agents.values():
                if config.model.provider in ("openai", "custom", "openrouter"):
                    agent.langchain_agent = agent.langchain_agent.bind(max_completion_tokens=256, timeout=30)
            return agents

        phase = "build"
        try:
            agents = build()
            for phase, thread, message in (
                ("training", "one", "Mình tên Lan. Mình ở Huế. Ghi nhớ giúp mình, trả lời bằng một câu ngắn."),
                ("recall_after_restart", "two", "Mình tên gì và đang ở đâu? Trả lời ngắn gọn."),
                ("technical", "three", "Giải thích short-term memory trong AI agent bằng một câu, có ví dụ."),
            ):
                if phase == "recall_after_restart":
                    agents = build()
                for name, agent in agents.items():
                    reply = agent.reply("live_demo_lan", thread, message)
                    result["records"].append({"agent": name, "phase": phase, "message": message, **reply})
                    print(f"{phase}: {name} completed", flush=True)
            recall_answers = {r["agent"]: r["response"] for r in result["records"] if r["phase"] == "recall_after_restart"}
            result["checks"] = {
                "six_live_responses": len(result["records"]) == 6 and all(r["mode"] == "live" for r in result["records"]),
                "baseline_has_no_profile_recall": recall_points(recall_answers["Baseline"], ["Lan", "Huế"]) == 0,
                "advanced_recalls_after_restart": recall_points(recall_answers["Advanced"], ["Lan", "Huế"]) == 1,
            }
            result["status"] = "passed" if all(result["checks"].values()) else "failed"
        except Exception as exc:
            error = {"phase": phase, "type": type(exc).__name__}
            status = getattr(exc, "status_code", None)
            if isinstance(status, int):
                error["http_status"] = status
            code = getattr(exc, "code", None)
            if isinstance(code, str) and re.fullmatch(r"[a-zA-Z0-9_-]{1,60}", code):
                error["code"] = code
            result["error"] = error
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "PHAN_5_LIVE.json")
    parser.add_argument("--model", help="override the model for this check only")
    args = parser.parse_args()
    # Do not export prompts or secrets to external tracing/logging services.
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    config = load_config(ROOT)
    if args.model:
        config = replace(config, model=replace(config.model, model_name=args.model))
    print("API key: " + ("set" if config.model.api_key else "missing"))
    print("Base URL: " + ("set" if config.model.base_url else "missing"))
    result = run_check(config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "records"}, ensure_ascii=False))
    raise SystemExit(0 if result["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
