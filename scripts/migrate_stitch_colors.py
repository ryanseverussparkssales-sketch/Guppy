#!/usr/bin/env python3
"""Migrate all accent colors to Stitch design system."""
import re
from pathlib import Path

# Get all view files
views_dir = Path("ui/launcher/views")
components_dir = Path("ui/launcher/components")

files = list(views_dir.glob("*.py")) + list(components_dir.glob("*.py"))
print(f"Processing {len(files)} files...")

replaced_total = 0
for file_path in files:
    try:
        content = file_path.read_text()
        original = content
        
        # Replace accent colors with word boundaries
        content = re.sub(r'\bT\.PRIMARY\b', 'T.ACCENT_ORANGE', content)
        content = re.sub(r'\bT\.SECONDARY\b', 'T.ACCENT_TEAL', content)
        content = re.sub(r'\bT\.TERTIARY\b', 'T.ACCENT_TEAL', content)
        
        # Write back if changed
        if content != original:
            file_path.write_text(content)
            changes = content.count('ACCENT_ORANGE') + content.count('ACCENT_TEAL')
            print(f"✅ {file_path.name}: updated")
            replaced_total += changes
    except Exception as e:
        print(f"❌ {file_path.name}: {e}")

print(f"\n✅ Migration complete! Updated {replaced_total} color references")
