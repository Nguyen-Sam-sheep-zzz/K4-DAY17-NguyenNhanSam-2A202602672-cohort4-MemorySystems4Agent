"""A reproducible offline demo using synthetic facts and temporary state."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_advanced import AdvancedAgent
from agent_baseline import BaselineAgent
from config import LabConfig
from model_provider import ProviderConfig


def run_demo(root: Path) -> dict:
    model = ProviderConfig("openai", "offline-demo", 0)
    config = LabConfig(root, ROOT / "data", root / "state", 1200, 4, model, model)
    agents = {"Baseline": BaselineAgent(config, True), "Advanced": AdvancedAgent(config, True)}
    cases = []

    def ask(label: str, thread: str, question: str, user: str = "demo_sam") -> None:
        cases.append({
            "step": label, "user_id": user, "thread_id": thread, "question": question,
            "answers": {name: agent.reply(user, thread, question)["response"]
                        for name, agent in agents.items()},
        })

    for agent in agents.values():
        agent.reply("demo_sam", "chat-1", "Mình tên là Sâm. Mình ở Đà Nẵng. Mình đang làm backend engineer.")
    ask("1. Nhớ trong cùng chat", "chat-1", "Mình tên gì và đang ở đâu?")
    ask("2. Mở chat mới", "chat-2", "Mình tên gì và đang ở đâu?")

    for agent in agents.values():
        agent.reply("demo_sam", "chat-2", "Mình chuyển vào Huế. Mình không còn làm backend engineer nữa, giờ chuyển sang MLOps engineer.")
        agent.reply("demo_sam", "chat-2", "Hôm nay mình ở Hà Nội để họp hai ngày.")
    ask("3. Correction và chuyến đi tạm", "chat-2", "Mình đang ở đâu và làm nghề gì?")

    agents = {"Baseline": BaselineAgent(config, True), "Advanced": AdvancedAgent(config, True)}
    ask("4. Tạo lại cả hai agent", "chat-3", "Nhắc lại tên, nơi ở và nghề nghiệp của mình.")
    ask("5. Người dùng khác", "chat-hai", "Mình tên gì?", user="demo_hai")
    return {"mode": "offline", "state": "temporary", "facts": "synthetic-demo", "cases": cases}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print machine-readable demo evidence")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="day17-demo-") as directory:
        result = run_demo(Path(directory))
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("Demo offline — dữ liệu giả lập, state tạm, không gọi API.\n")
            for case in result["cases"]:
                print(case["step"])
                print("Câu hỏi: " + case["question"])
                for name, response in case["answers"].items():
                    print(name + ":\n" + response)
                print()


if __name__ == "__main__":
    main()
