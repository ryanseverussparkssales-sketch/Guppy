# Guppy — Library Surface

**Last updated:** 2026-04-30 (Tranche H complete)

The Library surface (BookDrop) provides book/media acquisition, cataloging, and OPDS access.

---

## Architecture

```
WorkspaceView (via LibraryView at /library or Workspace tab)
    ↓
LibraryView.tsx — search, intake form, shelf browser
    ↓
GET /api/library/search
POST /api/library/add
GET /api/library/shelf
GET /api/library/opds         ← OPDS 1.2 catalog feed
GET /api/library/opds/{id}    ← entry detail
    ↓
src/guppy/api/routes_library.py   — JSON catalog CRUD
src/guppy/library/enricher.py     — OpenLibrary metadata fetch + cache
```

---

## Storage

- **Catalog:** `config/library.json` — plain JSON, git-trackable. Each entry: `{id, title, author, isbn, format, path, added_at, metadata?}`
- **Metadata cache:** `guppy_main.db.library_metadata` — OpenLibrary API responses, TTL 30 days

---

## Intake Flow

1. User submits title/ISBN via LibraryView intake form
2. `POST /api/library/add` validates entry, appends to `config/library.json`
3. Enricher fetches OpenLibrary metadata (async, cached)
4. Entry appears in shelf browser with cover art and metadata

---

## OPDS Feed

`GET /api/library/opds` returns a valid OPDS 1.2 Atom feed.  
Compatible with: KOReader, Calibre, Moon+ Reader, most e-reader apps.

Feed URL: `http://localhost:8080/api/library/opds`

---

## Acquisition Policy

- Local intake only — user adds files/ISBNs directly
- No automated scraping or acquisition
- OPDS serves existing catalog entries only

---

## Enrichment

`src/guppy/library/enricher.py` calls OpenLibrary Search API:

```
https://openlibrary.org/search.json?isbn={isbn}
https://openlibrary.org/search.json?title={title}&author={author}
```

Results cached in `guppy_main.db.library_metadata` with 30-day TTL.
Cache key: `isbn:{isbn}` or `title:{title}:{author}` (normalized).
