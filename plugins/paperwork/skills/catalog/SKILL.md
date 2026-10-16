---
name: catalog
description: >-
  Use when the user has existing folders of invoices, receipts or business
  documents (OneDrive, Dropbox, Downloads, years of PDFs) and wants them
  catalogued, deduplicated, indexed or reorganised into the paperwork archive -
  "catalog my old invoices", "index this folder", "clean up my Belege folder",
  "find duplicates in my invoices", "bring my archive into the new structure".
  Registers documents where they are or reorganises them, always as a plan the
  user approves first.
user-invocable: true
license: MIT
metadata:
  author: Stanislav Schmidt
  version: 0.1.0
---

# Catalog

Bring documents that already exist into the archive. Two ways; ask which one (recommended:
reorganise, because the folder structure then answers questions by itself):

- **Index in place.** The documents stay where they are, get records, show up in the CSVs and
  duplicates are found. Nothing moves: apply no plan, or only the duplicates part of it.
- **Reorganise.** The same, then `paperwork plan` / `apply` moves every confirmed document into
  `<entity>/<year>/<in|out>/` with the naming convention. Everything is journaled; `paperwork undo`
  reverses a batch.

## Workflow

1. The folder has to be inside the archive root (the engine only sees the archive; a container mount).
   Either make the existing folder the root (`paperwork init <folder>`, then the `setup` skill), or
   copy (`cp -Rn`) the documents into `_inbox/`. Never move the user's originals out of their place
   yourself.
2. `paperwork ingest --adopt` registers every file in the archive that has no record yet, wherever it
   is, including manually moved files it already knows (relinked by hash).
3. Read what is pending exactly as the `inbox` skill says: content only, never file or folder names
   (a folder called `2023` or `Telekom` may hold anything).
4. Show the duplicates (`paperwork list --status duplicate`) and the plan, grouped by destination,
   with counts per entity and year. Apply only what the user approved.
5. `paperwork export`, `paperwork verify`, and offer templates for vendors with many documents.

Large folders: work in batches of about 20 documents per `record` round and report progress.
