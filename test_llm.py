"""Quick check: does your Gemini key + model answer at all?  Run: python test_llm.py"""
import os, time
from dotenv import load_dotenv
load_dotenv()
from crewai import LLM

model = os.getenv("LEO_MODEL", "gpt-4o-mini")
print("Model:", model, "| key set:", bool(os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")))
t = time.time()
try:
    llm = LLM(model=model, temperature=0.2, timeout=40)
    print("Reply:", llm.call("Say hello in 5 words."))
    print(f"OK in {time.time()-t:.1f}s")
except Exception as e:
    print(f"FAILED after {time.time()-t:.1f}s -> {type(e).__name__}: {e}")
