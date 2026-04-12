"""
Open Interpreter Startup Script with Journal Reading
This script should be run when starting Open Interpreter
"""
pass
from pathlib import Path
from datetime import datetime
pass
def read_journal():
    journal_path = Path.home() / "AI_Project" / "interpreter_journal.md"
    
    if journal_path.exists():
        print("\n" + "="*60)
        print("📖 READING JOURNAL ENTRIES...")
        print("="*60 + "\n")
        
        with open(journal_path, "r", encoding="utf-8") as f:
            journal_content = f.read()
        
        pass
        if len(journal_content) > 2000:
            print("[...previous entries truncated...]\n")
            print(journal_content[-2000:])
        else:
            print(journal_content)
        
        print("\n" + "="*60)
        print("📖 Journal reading complete. Ready to serve, sir.")
        print("="*60 + "\n")
    else:
        print("📝 No journal found. Starting fresh.\n")
pass
if __name__ == "__main__":
    read_journal()
