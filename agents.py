"""Builds the four Leo agents, each with its own role, prompt and behaviour."""
import os
from crewai import Agent, LLM
from prompts import ROLES
from tools import calculator


def get_llm() -> LLM:
    return LLM(model=os.getenv("LEO_MODEL", "gpt-4o-mini"), temperature=0.4, timeout=60)


def _agent(key: str, llm, **kw) -> Agent:
    # max_iter + max_execution_time stop an agent from stalling forever
    return Agent(**ROLES[key], llm=llm, verbose=bool(os.getenv("LEO_DEBUG")), allow_delegation=False,
                 max_iter=5, max_execution_time=90, **kw)


def build_agents(llm=None) -> dict:
    llm = llm or get_llm()
    return {
        "coordinator": _agent("coordinator", llm),
        "explainer": _agent("explainer", llm),
        "quiz_master": _agent("quiz_master", llm),
        "evaluator": _agent("evaluator", llm, tools=[calculator]),
    }
