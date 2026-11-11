# 🦁 Leo — Multi-Agent AI Tutor

Leo is a study assistant built with **CrewAI**. Four agents with separate roles, prompts and behaviours
collaborate to plan, teach, quiz and grade a student, with real handoffs between them.

Leo brings together four specialized AI agents that collaborate to create an interactive and personalized learning experience.
- 🎯 Coordinator Agent: Understands learning goals, plans the learning workflow, and coordinates tasks among the agents.
- 📚 Explainer Agent: Teaches concepts through simple explanations, practical examples, and relatable analogies.
- 📝 Quiz Master Agent: Generates topic-based quizzes to test students' understanding of learned concepts.
- 🧠 Evaluator Agent: Evaluates student answers, provides scores and constructive feedback, and identifies weak concepts for further improvement.

Together, these agents create an adaptive learning cycle that helps students learn, practice, evaluate their understanding, and improve.
## Agents
| Agent | Role | Output |
|---|---|---|
| **Coordinator** | Reads the request, handles vague input (asks one clarifying question), routes work, retries failed steps, triggers re-teaching, writes the summary | `Plan` (structured) |
| **Explainer** | Teaches the concept with analogies/examples; uses a different approach when re-teaching | Lesson text |
| **Quiz Master** | Writes questions from the Explainer's lesson | `Quiz` (Pydantic, structured) |
| **Evaluator** | Grades answers with partial credit, feedback, weak-concept detection; has a **calculator tool** | `Evaluation` (structured) |

Prompts: `prompts.py` (one role prompt + one task template per agent). Memory: `memory.py`.

## Architecture
```mermaid
flowchart TD
    S([Student]) -->|request| C1[Coordinator: triage]
    C1 -->|unclear| S
    C1 -->|Plan: topic, level| E[Explainer]
    E -->|lesson as task context| Q[Quiz Master]
    Q -->|Quiz JSON| S
    S -->|answers: human-in-the-loop| V[Evaluator]
    Q -->|Quiz JSON + reference answers| V
    V -->|Evaluation| C2{Coordinator: weak concepts?}
    C2 -->|yes + student agrees: FEEDBACK LOOP| E
    C2 -->|no / max rounds| M[(Student memory JSON)]
    C2 --> SUM[Coordinator: summary]
    M -.injected into every prompt.-> C1
```

## Orchestration pattern
**Coordinator-driven sequential pipeline with a feedback loop.**
CrewAI `Process.sequential` crews run each stage; Explainer→Quiz Master uses CrewAI task `context=` (true
handoff), and Quiz Master→Evaluator passes the structured `Quiz` JSON. The Coordinator owns control flow:
clarification, retries (`max_iter`, `max_execution_time`, retry with back-off), and routing weak answers back
to the Explainer (up to 3 rounds).

## Bonus features
- **Feedback loop:** Evaluator's `weak_concepts` → Coordinator → Explainer re-teaches → new quiz.
- **Human-in-the-loop:** student answers each question, can `/skip`, `/quit`, and approves re-teaching.

## Memory
Per-student JSON (`data/memory/`, git-ignored): past topics, scores, recurring weak concepts. Injected into
every agent's prompt via the `{memory}` placeholder.

## Run
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # add your API key (never commit .env)
python main.py
streamlit run app.py
```
** Any Lite LLM model works via `LEO_MODEL` (e.g. `LEO_MODEL=gemini/gemini-3.1-flash-lite`).




