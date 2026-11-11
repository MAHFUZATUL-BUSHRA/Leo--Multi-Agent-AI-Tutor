"""Persistent student memory (JSON per student). Injected into every agent's prompt."""
import json, re
from pathlib import Path

DIR = Path(__file__).parent / "data" / "memory"


class StudentMemory:
    def __init__(self, name: str):
        DIR.mkdir(parents=True, exist_ok=True)
        self.name = name
        self.path = DIR / f"{re.sub(r'[^a-z0-9]+', '_', name.lower())}.json"
        self.data = {"name": name, "sessions": [], "weak_concepts": {}, "last_topic": ""}
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text())
            except json.JSONDecodeError:
                pass  # corrupted file -> start fresh

    def context(self) -> str:
        d = self.data
        if not d["sessions"]:
            return "New student, no history."
        recent = "; ".join(f"{s['topic']} ({s['score']:.0%})" for s in d["sessions"][-5:])
        weak = ", ".join(d["weak_concepts"]) or "none"
        return f"Returning student. Recent topics: {recent}. Known weak concepts: {weak}."

    def record(self, topic: str, score: float, weak: list, mastered: list):
        self.data["sessions"].append({"topic": topic, "score": score})
        self.data["last_topic"] = topic
        for w in weak:
            self.data["weak_concepts"][w] = self.data["weak_concepts"].get(w, 0) + 1
        for m in mastered:
            self.data["weak_concepts"].pop(m, None)
        self.path.write_text(json.dumps(self.data, indent=2))
