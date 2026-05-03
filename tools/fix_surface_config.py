"""One-time fix: reset companion surface_config to llamacpp-hermes4."""
import sqlite3
import sys
sys.path.insert(0, r"C:\Users\Ryan\Guppy")

from src.guppy.paths import MAIN_DB_PATH

conn = sqlite3.connect(str(MAIN_DB_PATH))
conn.execute("UPDATE surface_config SET model='llamacpp-hermes4' WHERE surface='companion'")
conn.commit()
rows = conn.execute("SELECT surface, model FROM surface_config").fetchall()
print("surface_config after fix:")
for r in rows:
    print(f"  {r[0]} -> {r[1]}")
conn.close()
