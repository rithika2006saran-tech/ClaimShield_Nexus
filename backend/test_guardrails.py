import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import logging
logging.basicConfig(level=logging.DEBUG)

from app.ai.guardrails import init_guardrails, protect_privacy

try:
    print("Testing initialization...")
    init_guardrails()
    print("Testing protect_privacy...")
    text = "My name is John Doe and my phone number is 212-555-1234."
    result = protect_privacy(text)
    print("Input:", text)
    print("Output:", result)
except Exception as e:
    print(f"Error: {e}")
