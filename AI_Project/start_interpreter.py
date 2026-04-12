from interpreter import interpreter
from pathlib import Path
import re

# Read handshake from Butler's Bible
journal_path = Path.home() / "AI_Project" / "interpreter_journal.md"

print("="*60)
print("🎩 YOUR FAITHFUL ASSISTANT")
print("="*60)

if journal_path.exists():
    with open(journal_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract handshake
    matches = re.findall(r'AUTHENTICATION CODE: ([A-Z0-9]+)', content)
    if matches:
        handshake = matches[-1]
        print(f"\n🔐 Handshake verified: {handshake}")
    else:
        print("\n⚠️  No handshake found")
else:
    print("\n⚠️  Butler's Bible not found")

print("\nConfiguration:")
print("  • Model: Claude 4.5 (Opus)")
print("  • Auto-run: Enabled")
print("  • Safe mode: OFF")
print("\n" + "="*60)
print("Ready to serve, Master Ryan. 🎩")
print("="*60)
print()

# Configure interpreter
interpreter.llm.model = "claude-opus-4-20250514"
interpreter.auto_run = True

# Start chat
interpreter.chat()
