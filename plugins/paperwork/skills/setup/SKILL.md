---
name: setup
description: >-
  Use when the user wants to start an invoice / document archive, set up
  paperwork, point it at a folder (OneDrive, Dropbox, a NAS), or add or change
  a legal entity, VAT ID, address or category - "set up my invoice archive",
  "add my new GmbH", "we moved offices", "where do my Belege go". Creates the
  archive layout and writes the entities the engine assigns every document to.
user-invocable: true
license: MIT
metadata:
  author: Stanislav Schmidt
  version: 0.3.0
---

# Setup

The engine needs Docker; nothing else is installed on the machine. The first run builds the tools
image once (`paperwork doctor` shows the tool versions).

## Workflow

1. **Where.** Ask for the archive folder (default `~/OneDrive/Belege` or the OneDrive folder the user
   names; on macOS it is under `~/Library/CloudStorage/OneDrive-*`). `paperwork init <folder>` creates
   `_inbox/ _review/ _duplicates/ _paperwork/ exports/` and registers the archive, so `paperwork` and
   the guard hook find it from anywhere. An existing folder full of documents can be the root: the
   `catalog` skill brings them in afterwards.
2. **Entities.** Ask in one batch (AskUserQuestion) for every company and the private person who
   receives or issues documents: legal name and the name variants that appear on invoices, VAT ID
   (USt-IdNr.), tax number, every address used now or before. Write them to
   `_paperwork/config.json` (it is the one archive file you edit directly):

   ```json
   {"slug": "acme", "name": "Acme GmbH", "names": ["ACME GmbH", "Acme Digital GmbH"],
    "vat_ids": ["DE123456789"], "tax_numbers": ["14097/16501"],
    "addresses": ["Musterweg 1", "Am Hafen 7"], "kind": "business"}
   ```

   `kind: private` for a person: documents billed to that name and to no company go there. The slug
   is the top folder name: lowercase, short, stable.
3. **Categories and start year.** Keep the default categories unless the user has their own chart of
   accounts; `start_year` is the oldest document they will keep.
4. **Classes and rules (optional).** The built-in classes (`inv cn rcpt rem notice oc quote contract
   other`) cover most archives. Ask whether the user files anything else (a contract with a term,
   a payslip). Add it under `classes` in `config.json`; the README's "Classes and rules" section has
   an example. Fields are `{"name": {"type": ...}}` with type `text`, `date`, `money`, `number`,
   `bool` or `choice` (`choice` needs a non-empty `choices` list). `required` lists proposal keys,
   party keys such as `seller.name`, or `fields.<name>`. Class keys match `[a-z][a-z0-9-]{0,15}`,
   field names `[a-z][a-z0-9_]{0,31}` and are not `id`, `entity`, `counterparty`, `issue_date`,
   `status`, `confirmed` or `path`. The folder template must start with `{entity}`.
   `paperwork schema` shows the result. A first `_paperwork/rules.json` can wait until the same
   correction has come up twice (see the `review` skill).
5. `paperwork doctor` must show no problems. Then tell the user to drop files into `_inbox/` and run
   the `inbox` skill.

## Changing later

Edit `config.json`, then `paperwork export`: every record is re-checked against the new config, and
`paperwork plan` shows the renames a changed entity would cause. Run `paperwork plan` after every
change to a `name` or `folder` template too, and show the user the renames before applying. Never
rename entity folders by hand.

## Notes worth telling the user

- OneDrive "Files On-Demand": files that only exist in the cloud are downloaded when read; files that
  cannot be read are reported, never skipped silently. Run the engine on one machine at a time; a
  lock file stops a second one.
- Documents are read inside a container with no network. Only documents that need Claude's reading
  are seen by Claude.
