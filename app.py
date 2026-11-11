"""Leo — Streamlit UI. Run: streamlit run app.py
Drives the same Leo orchestrator as the CLI, one stage per rerun (state machine in session_state)."""
import os
os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")   # no trace-sharing prompt
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
st.set_page_config(page_title="Leo — Multi-Agent Tutor", page_icon="🦁", layout="wide")

ICON = {"Leo Coordinator": "🧭", "Leo Explainer": "📘", "Leo Quiz Master": "❓", "Leo Evaluator": "📝"}
MAX_ROUNDS = 3


class StUI:
    """Adapter so the orchestrator can report agent activity to Streamlit."""
    box = None

    def _emit(self, text):
        st.session_state.activity.append(text)
        if self.box is not None:
            self.box.write(text)

    def agent_start(self, role, msg): self._emit(f"▶ {ICON.get(role, '🤖')} **{role}** — {msg}")
    def agent_done(self, role): self._emit(f"✔ {ICON.get(role, '🤖')} **{role}** finished")
    def say(self, text): self._emit(text)


S = st.session_state
for k, v in dict(stage="start", activity=[], leo=None, plan=None, topic="", level="beginner",
                 weak="", round=1, lesson="", quiz=None, ev=None, summary="", clarify_tries=0,
                 clarify_q="").items():
    S.setdefault(k, v)
ui = StUI()


def reset():
    for k in list(S.keys()):
        del S[k]


def run_step(label, fn, *args):
    """Run an agent step inside a live status box showing which agent is doing what."""
    from orchestrator import LeoFatalError
    try:
        with st.status(label, expanded=True) as box:
            ui.box = box
            out = fn(*args)
            box.update(label=label + " — done", state="complete")
            ui.box = None
        return out
    except LeoFatalError as e:
        ui.box = None
        st.error(str(e))
        st.stop()


# ---------------- sidebar: team + activity log ----------------
with st.sidebar:
    st.header("🦁 Leo's team")
    for role, icon in ICON.items():
        st.markdown(f"{icon} {role}")
    st.divider()
    st.subheader("Activity log (handoffs)")
    for line in S.activity[-40:]:
        st.markdown(line)
    st.divider()
    if st.button("🔄 New session"):
        reset(); st.rerun()

st.title("🦁 Leo — Multi-Agent AI Tutor")

if not any(os.getenv(k) for k in ("OPENAI_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY", "ANTHROPIC_API_KEY")):
    st.error("No API key found. Copy `.env.example` to `.env` and add your key, then restart.")
    st.stop()


def start_planning(request):
    from orchestrator import Leo
    plan = run_step("🧭 Coordinator: reading your request", S.leo.triage, request)
    if plan and plan.intent == "learn" and plan.topic:
        S.topic, S.level, S.stage = plan.topic, plan.level, "teach"
    else:
        S.clarify_tries += 1
        if S.clarify_tries > 2:
            S.stage = "failed"
        else:
            S.clarify_q = (plan.clarification_question if plan and plan.clarification_question
                           else "What topic would you like to learn today?")
            S.stage = "clarify"
    st.rerun()


# ---------------- stages ----------------
if S.stage == "start":
    with st.form("start"):
        name = st.text_input("Your name")
        request = st.text_input("What would you like to learn?", placeholder="e.g. Explain photosynthesis")
        go = st.form_submit_button("Start")
    if go and name and request:
        from memory import StudentMemory
        from orchestrator import Leo
        mem = StudentMemory(name)
        S.leo = Leo(mem, ui)
        st.caption(f"Memory: {mem.context()}")
        start_planning(request)

elif S.stage == "clarify":
    st.info(f"🧭 **Coordinator:** {S.clarify_q}")
    with st.form("clarify"):
        ans = st.text_input("Your answer")
        go = st.form_submit_button("Send")
    if go and ans:
        start_planning(ans)

elif S.stage == "failed":
    st.warning("🧭 I couldn't pin down a topic. Try something like 'Explain photosynthesis'.")

elif S.stage == "teach":
    st.subheader(f"Round {S.round}/{MAX_ROUNDS} — {S.topic}")
    lesson, quiz = run_step("📘 Explainer → ❓ Quiz Master", S.leo.teach_and_quiz, S.topic, S.level, S.weak)
    if lesson and quiz:
        S.lesson, S.quiz, S.stage = lesson, quiz, "quiz"
        st.rerun()
    else:
        st.error("The team couldn't produce a lesson/quiz.")
        if st.button("Retry"):
            st.rerun()

elif S.stage == "quiz":
    st.subheader(f"Round {S.round}/{MAX_ROUNDS} — {S.topic}")
    with st.container(border=True):
        st.markdown("#### 📘 Explainer's lesson")
        st.markdown(S.lesson)
    st.markdown("#### ❓ Quiz Master's questions")
    with st.form(f"quiz_{S.round}"):
        answers = {}
        for q in S.quiz.questions:
            st.markdown(f"**Q{q.id}.** {q.question}  \n*tests: {q.concept}*")
            if q.type == "mcq" and q.options:
                answers[q.id] = st.radio("Choose", q.options, index=None, key=f"q{S.round}_{q.id}",
                                         label_visibility="collapsed")
            else:
                answers[q.id] = st.text_input("Answer", key=f"q{S.round}_{q.id}",
                                              label_visibility="collapsed")
        submit = st.form_submit_button("Submit answers to Evaluator")
    if submit:
        answers = {k: (v or "") for k, v in answers.items()}
        ev = run_step("📝 Evaluator: grading", S.leo.evaluate, S.quiz, answers, S.topic, S.level)
        if ev:
            S.ev, S.stage = ev, "feedback"
            S.leo.log.append({"round": S.round, "weak": ev.weak_concepts})
            st.rerun()
        else:
            st.error("Evaluator is unavailable. Please submit again.")

elif S.stage == "feedback":
    ev = S.ev
    st.subheader("📝 Evaluator feedback")
    for g in ev.grades:
        st.markdown(f"{'✅' if g.correct else '❌'} **Q{g.question_id}** ({g.score:.0%}, {g.concept}) — {g.feedback}")
    st.success(ev.overall_feedback)
    can_loop = ev.needs_reteach and ev.weak_concepts and S.round < MAX_ROUNDS
    if can_loop:
        st.warning(f"🧭 Weak concepts: {', '.join(ev.weak_concepts)}. Re-teach them?")
        c1, c2 = st.columns(2)
        if c1.button("🔁 Yes, re-teach (feedback loop)"):
            S.weak = ", ".join(ev.weak_concepts)
            S.round += 1
            S.stage = "teach"
            S.activity.append("🔁 Evaluator → Coordinator → Explainer: re-teaching weak concepts")
            st.rerun()
        if c2.button("Finish session"):
            S.stage = "finish"; st.rerun()
    elif st.button("Finish session"):
        S.stage = "finish"; st.rerun()

elif S.stage == "finish":
    S.summary = run_step("🧭 Coordinator: wrapping up", S.leo.finish, S.topic, S.ev)
    S.stage = "done"
    st.rerun()

elif S.stage == "done":
    st.balloons()
    st.subheader("🎉 Session summary")
    st.success(S.summary)
    st.caption("Saved to student memory. Start a new session from the sidebar.")
