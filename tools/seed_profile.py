"""
seed_profile.py — One-time (idempotent) profile seeder for Guppy's memory DB.
Run any time to add/update Ryan's profile facts.  All calls use remember()
which does an UPSERT, so it is safe to re-run.

Usage:
    python seed_profile.py
    .venv\\Scripts\\python.exe seed_profile.py
"""
from src.guppy.memory.memory import remember, save_contact

# ── Helper ─────────────────────────────────────────────────────────────────────
results = []

def seed(key: str, value: str, category: str):
    msg = remember(key, value, category)
    results.append(msg)
    print(f"  {msg}")


print("=" * 60)
print("  GUPPY PROFILE SEEDER")
print("=" * 60)

# ── Personal identity ──────────────────────────────────────────────────────────
print("\n[1/5] Personal identity...")
seed("full_name",           "Ryan Severus Sparks",                           "personal")
seed("preferred_name",      "Ryan",                                           "personal")
seed("location",            "White Bear Lake, MN",                            "personal")
seed("phone",               "612-417-2133",                                   "personal")
seed("guppy_address",       "Master Ryan  (how Guppy addresses Ryan)",        "personal")
seed("merlin_address",      "Apprentice  (how Merlin addresses Ryan)",         "personal")

# ── Work ───────────────────────────────────────────────────────────────────────
print("\n[2/5] Work & company...")
seed("role",                "SDR / AE  (Sales Development Representative / Account Executive)", "work")
seed("company",             "Northern Spark Sales Agency",                    "work")
seed("company_also",        "Arcane Artisans Retail Distribution Network (co-venture, 2021-present)", "work")
seed("work_focus",          "B2B sales — prospecting, outreach, account management, call reports, order notes", "work")
seed("work_background",     "10+ years sales experience. $2M+ revenue generated for clients. Platforms: Upwork, GlenCoco. Sectors: SaaS, B2B/B2C, home remodeling/building.", "work")
seed("primary_email",       "ryanseverussparkssales@gmail.com  (alias: main)", "work")
seed("personal_email",      "ryanseverussparks@gmail.com  (alias: personal)", "work")
seed("retiring_email",      "trsparkssales@gmail.com  (alias: sales — being phased out)", "work")

# ── AI suite ───────────────────────────────────────────────────────────────────
print("\n[3/5] AI assistant suite...")
seed("ai_suite_name",       "Guppy — Ryan's personal AI assistant suite",     "projects")
seed("ai_guppy",            "Guppy: cyberpunk chief-of-staff persona. Primary: Claude Sonnet. Local route: Ollama model 'guppy'.", "projects")
seed("ai_merlin",           "Merlin: fantasy wizard mentor persona. Runs locally via Ollama model 'merlin'.", "projects")
seed("ai_omnissiah",        "Omnissiah: Warhammer 40K / gothic hub controller. System-tray launcher for all agents.", "projects")
seed("ai_council",          "Historical Council specialist surface is quarantined; the unified launcher and configured instances are the active desktop path.", "projects")
seed("ai_stack",            "PySide6 GUI, Anthropic Claude API, Ollama, SQLite memory (guppy_memory.db), Gmail API, Spotify API, edge_tts + Whisper voice", "projects")

# ── Preferences & style ────────────────────────────────────────────────────────
print("\n[4/5] Preferences...")
seed("response_style",      "Direct, concise, no fluff. Guppy stays in cyberpunk/butler character. Merlin stays in fantasy character.", "preferences")
seed("memory_behaviour",    "Guppy proactively remembers facts Ryan shares. Uses recall before answering questions that may have context.", "preferences")
seed("gmail_cleanup",       "Prefers aggressive inbox cleanup. Smart cleanup runs 6 passes: unsubscribe, noreply, newsletter, old promo, old mail, mark-old-unread-as-read.", "preferences")
seed("gmail_consolidation", "Keeping main + personal Gmail. Retiring trsparkssales@gmail.com.", "preferences")
seed("spotify_use",         "Uses Spotify for background music while working. Guppy can control playback.", "preferences")
seed("interests",           "Gaming (98+ titles: RimWorld, Total War, Cyberpunk 2077, Disco Elysium). Content creation (Filmora). Design (GIMP, Krita). Writing (Scrivener). Reads Dresden Files.", "personal")

# ── Contacts — seed Ryan himself so Guppy knows the owner ─────────────────────
print("\n[5/5] Contacts...")
result = save_contact(
    name="Ryan Sparks",
    company="Northern Spark Sales Agency",
    email="ryanseverussparkssales@gmail.com",
    phone="612-417-2133",
    notes="Owner / operator of this Guppy instance. SDR/AE. White Bear Lake MN. Prefers direct communication.",
)
print(f"  {result}")

# ── Summary ────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print(f"  Done. {len(results)} facts seeded, 1 contact upserted.")
print("  Guppy will pick these up on next startup via get_startup_context().")
print("=" * 60)
