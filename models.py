"""Structured outputs passed between agents (typed handoffs)."""
from typing import List, Literal
from pydantic import BaseModel, Field


class Plan(BaseModel):
    intent: Literal["learn", "unclear"]
    topic: str = Field(description="Clean topic name, empty if unclear")
    level: Literal["beginner", "intermediate", "advanced"] = "beginner"
    clarification_question: str = Field(default="", description="Question to ask the student if intent is unclear")


class Question(BaseModel):
    id: int
    type: Literal["mcq", "short"]
    question: str
    options: List[str] = []
    answer: str = Field(description="Reference correct answer")
    concept: str = Field(description="The sub-concept this question tests")


class Quiz(BaseModel):
    questions: List[Question]


class Grade(BaseModel):
    question_id: int
    correct: bool
    score: float = Field(ge=0, le=1)
    concept: str
    feedback: str


class Evaluation(BaseModel):
    grades: List[Grade]
    overall_feedback: str
    weak_concepts: List[str]
    needs_reteach: bool
