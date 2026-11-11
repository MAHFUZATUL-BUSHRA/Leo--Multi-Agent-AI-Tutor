"""Leo — CLI. Shows which agent is working and every handoff."""
import os
os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")   # no trace-sharing prompt
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

import sys
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt, Confirm

load_dotenv()
STYLE = {"Leo Coordinator": "cyan", "Leo Explainer": "green",
         "Leo Quiz Master": "yellow", "Leo Evaluator": "magenta"}


class CLI:
    def __init__(self): self.c = Console()
    def agent_start(self, role, msg):
        self.c.print(f"[bold {STYLE.get(role,'white')}]▶ {role}[/]: {msg}")
    def agent_done(self, role):
        self.c.print(f"[bold {STYLE.get(role,'white')}]✔ {role} finished[/]")
    def say(self, text): self.c.print(text)
    def ask(self, prompt): return Prompt.ask(f"[bold]{prompt}[/]")
    def confirm(self, prompt): return Confirm.ask(prompt)
    def show_lesson(self, text):
        self.c.print(Panel(Markdown(text), title="📘 Explainer's lesson", border_style="green"))
    def show_question(self, q):
        body = q.question + ("\n" + "\n".join(f"  {chr(65+i)}. {o}" for i, o in enumerate(q.options)) if q.options else "")
        self.c.print(Panel(body, title=f"❓ Q{q.id} ({q.type}) — tests: {q.concept}", border_style="yellow"))
    def show_evaluation(self, ev):
        for g in ev.grades:
            icon = "✅" if g.correct else "❌"
            self.c.print(f"{icon} Q{g.question_id} [{g.score:.0%}] {g.feedback}")
        self.c.print(Panel(ev.overall_feedback, title="📝 Evaluator feedback", border_style="magenta"))


def main():
    if not (os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("GROQ_API_KEY")
            or os.getenv("ANTHROPIC_API_KEY")):
        sys.exit("Set an API key in .env (see .env.example).")
    from memory import StudentMemory
    from orchestrator import Leo, LeoFatalError
    ui = CLI()
    ui.say("[bold]🦁 Leo — Multi-Agent AI Tutor[/]")
    name = ui.ask("What's your name?")
    mem = StudentMemory(name)
    ui.say(f"[dim]Memory: {mem.context()}[/]")
    try:
        Leo(mem, ui).session(ui.ask("What would you like to learn?"))
    except LeoFatalError as e:
        ui.say(f"[bold red]✖ {e}[/]")


if __name__ == "__main__":
    main()
