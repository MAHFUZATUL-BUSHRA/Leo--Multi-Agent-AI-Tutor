"""Orchestration: Coordinator-driven sequential pipeline with a feedback loop.

Triage (Coordinator) -> Explain (Explainer) -> Quiz (Quiz Master, gets lesson as context)
  -> [student answers: human-in-the-loop] -> Evaluate (Evaluator, gets quiz + answers)
  -> weak concepts? -> Coordinator routes back to Explainer (re-teach) -> repeat (max rounds)
  -> Coordinator writes summary; memory updated.
"""
import json, os, time
from typing import Callable
from crewai import Crew, Process, Task
import prompts as P
from agents import build_agents
from models import Plan, Quiz, Evaluation

_UI = None


def _task_done(output):
    """Module-level callback (avoids CrewAI's checkpoint warning)."""
    if _UI is not None:
        _UI.agent_done(output.agent)


class LeoFatalError(Exception):
    """Errors retrying cannot fix (no credits, bad API key)."""


FATAL_MARKERS = ("insufficient_quota", "credit_balance", "no credits", "invalid_api_key",
                 "incorrect api key", "authenticationerror", "api key not valid", "permission_denied",
                 "no longer available", "not_found", "is not found", "model_not_found")

MAX_ROUNDS = 3
N_QUESTIONS = 4


class Leo:
    def __init__(self, memory, ui):
        """ui: object with .agent_start(role, msg), .agent_done(role), .say(text),
        .show_quiz_question(q), .ask(prompt) -> str, .confirm(prompt) -> bool"""
        global _UI
        _UI = ui
        self.memory, self.ui = memory, ui
        self.agents = build_agents()
        self.log = []

    # ---- helpers -----------------------------------------------------------
    def _run(self, tasks, inputs, retries=2):
        """Run a sequential crew; Coordinator-level retry if an agent errors/stalls."""
        crew = Crew(agents=list({t.agent.role: t.agent for t in tasks}.values()), tasks=tasks,
                    process=Process.sequential, verbose=bool(os.getenv("LEO_DEBUG")),
                    task_callback=_task_done)
        for attempt in range(retries + 1):
            try:
                return crew.kickoff(inputs=inputs)
            except Exception as e:  # stall, timeout, bad JSON, rate limit...
                if any(m in str(e).lower() for m in FATAL_MARKERS):
                    raise LeoFatalError(
                        "The LLM provider rejected the request (no credits, invalid key, or the model in LEO_MODEL "
                        "no longer exists). Check .env: GEMINI_API_KEY and LEO_MODEL "
                        "(e.g. gemini/gemini-3.8-flash).") from e
                self.ui.say(f"[Coordinator] Step failed ({type(e).__name__}). "
                            f"{'Retrying...' if attempt < retries else 'Giving up on this step.'}")
                time.sleep(1.5 * (attempt + 1))
        return None

    def _base(self, topic="", level="beginner", weak=""):
        return dict(student_name=self.memory.name, memory=self.memory.context(),
                    topic=topic, level=level, weak_concepts=weak or "none",
                    n_questions=N_QUESTIONS)

    # ---- steps -------------------------------------------------------------
    def triage(self, request: str):
        a = self.agents["coordinator"]
        t = Task(description=P.TRIAGE, expected_output="A Plan object", agent=a, output_pydantic=Plan)
        self.ui.agent_start(a.role, "Reading your request and planning...")
        r = self._run([t], {**self._base(), "request": request})
        return r.pydantic if r and r.pydantic else None

    def teach_and_quiz(self, topic, level, weak):
        ex, qm = self.agents["explainer"], self.agents["quiz_master"]
        t1 = Task(description=P.EXPLAIN, expected_output="A short lesson with recap", agent=ex)
        t2 = Task(description=P.QUIZ, expected_output="A Quiz object", agent=qm,
                  context=[t1],              # <-- real handoff: lesson -> Quiz Master
                  output_pydantic=Quiz)
        self.ui.agent_start(ex.role, f"Teaching '{topic}'" + (f" (re-teaching: {weak})" if weak else ""))
        self.ui.agent_start(qm.role, "Will write questions from the lesson (handoff Explainer -> Quiz Master)")
        r = self._run([t1, t2], self._base(topic, level, weak))
        if not r or not r.pydantic:
            return None, None
        return r.tasks_output[0].raw, r.pydantic

    def evaluate(self, quiz: Quiz, answers: dict, topic, level):
        ev = self.agents["evaluator"]
        t = Task(description=P.EVALUATE, expected_output="An Evaluation object", agent=ev,
                 output_pydantic=Evaluation)
        self.ui.agent_start(ev.role, "Grading answers (handoff Quiz Master -> Evaluator)")
        r = self._run([t], {**self._base(topic, level),
                            "quiz_json": quiz.model_dump_json(),
                            "answers_json": json.dumps(answers)})
        return r.pydantic if r and r.pydantic else None

    def summarize(self, topic):
        a = self.agents["coordinator"]
        t = Task(description=P.SUMMARY, expected_output="3 sentences", agent=a)
        self.ui.agent_start(a.role, "Wrapping up the session...")
        r = self._run([t], {**self._base(topic), "session_log": json.dumps(self.log)})
        return r.raw if r else "Great work today!"

    # ---- main loop ---------------------------------------------------------
    def session(self, request: str):
        plan = self.triage(request)
        tries = 0
        while (plan is None or plan.intent == "unclear" or not plan.topic) and tries < 2:
            q = plan.clarification_question if plan and plan.clarification_question \
                else "What topic would you like to learn today?"
            self.ui.say(f"[Coordinator] {q}")
            plan = self.triage(self.ui.ask("You"))
            tries += 1
        if plan is None or not plan.topic:
            self.ui.say("[Coordinator] I couldn't pin down a topic. Try e.g. 'Explain photosynthesis'.")
            return
        topic, level, weak = plan.topic, plan.level, ""
        last_ev = None

        for rnd in range(1, MAX_ROUNDS + 1):
            self.ui.say(f"\n=== Round {rnd}/{MAX_ROUNDS} — topic: {topic} ===")
            lesson, quiz = self.teach_and_quiz(topic, level, weak)
            if not lesson or not quiz:
                self.ui.say("[Coordinator] The team couldn't produce a lesson/quiz. Please try again.")
                return
            self.ui.show_lesson(lesson)

            # human-in-the-loop: student answers (and can intervene)
            answers = {}
            for q in quiz.questions:
                self.ui.show_question(q)
                ans = self.ui.ask("Your answer (or /skip, /quit)")
                if ans.strip() == "/quit":
                    self.ui.say("[Coordinator] Session ended early. Progress saved.")
                    break
                answers[q.id] = "" if ans.strip() == "/skip" else ans
            else:
                ev = self.evaluate(quiz, answers, topic, level)
                if not ev:
                    self.ui.say("[Coordinator] Evaluator is unavailable; ending the session safely.")
                    return
                last_ev = ev
                self.ui.show_evaluation(ev)
                self.log.append({"round": rnd, "weak": ev.weak_concepts})
                # FEEDBACK LOOP: weak answers go back to the Explainer via the Coordinator
                if ev.needs_reteach and ev.weak_concepts and rnd < MAX_ROUNDS:
                    if self.ui.confirm("[Coordinator] Some concepts are shaky. Re-teach them? (y/n)"):
                        weak = ", ".join(ev.weak_concepts)
                        continue
                break
            break

        if last_ev:
            self.ui.say("\n" + self.finish(topic, last_ev))

    def finish(self, topic, ev):
        """Update memory and have the Coordinator write the summary (used by CLI and Streamlit)."""
        score = sum(g.score for g in ev.grades) / max(1, len(ev.grades))
        mastered = [g.concept for g in ev.grades if g.score >= 0.8]
        self.memory.record(topic, score, ev.weak_concepts, mastered)
        return self.summarize(topic)
