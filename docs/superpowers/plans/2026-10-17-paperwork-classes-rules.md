# paperwork: classes, rules and confirmation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the inbox → classify → name → file loop configurable: document classes in `config.json` (fields, required fields, checks, name and folder templates), user rules in `rules.json`, and a third outcome, *unconfirmed*, for what Claude decided alone.

**Architecture:** Everything stays in the single-file engine `plugins/paperwork/lib/paperwork.py`, following its existing sections. The class registry replaces `DOC_TYPES`/`MONEY_TYPES`; `doc_type` stays the record field that names the class, so existing records need no migration. Rules are applied when a record's fields are set (extract, record, set) and persisted with a log, like every other accepted field; `rules test` previews and `rules apply` re-applies them explicitly. Files and JSON records stay the only truth; no database.

**Tech Stack:** Python 3 stdlib, runs in the plugin's Docker image; tests are `unittest` in `plugins/paperwork/tests/test_paperwork.py`.

**Spec:** `research/studies/dms-inbox-classification/study.md` (sections *Ours against theirs* → Actions 1–3, *Recommendation*) and the step list agreed in conversation (steps 1–4: classes, layered classification with rules, three outcomes, naming and sorting from templates).

## Global Constraints

- No code path deletes or overwrites a document; only `apply` moves files, via the existing plan/journal/undo.
- An archive created by 0.1.0 must re-plan with **zero moves** after the upgrade, with no config change.
- `doc_type` remains the record and proposal field name for the class; built-in class keys are exactly `inv cn rcpt rem notice oc quote contract other`.
- Rule matching is exact or regex only; no "any word" matching.
- Claude may only use existing classes and entities; a new counterparty from a Claude proposal is *proposed*, not silently trusted.
- Never derive anything from file or folder names.
- File names stay ASCII; total path ≤ `MAX_PATH` (250).
- Tests: `plugins/paperwork/bin/paperwork __test` (Docker must be running); single test: `plugins/paperwork/bin/paperwork __test -k <name>`.
- Version becomes `0.2.0` everywhere `0.1.0` appears for paperwork (engine `VERSION`, `plugin.json`, `marketplace.json`, skill frontmatter).

## Review Focus

1. **Upgraded archive:** documents filed by 0.1.0 stay where they are — test `test_upgrade_replans_zero_moves` (Task 2).
2. **Template renders an unsafe or empty folder** (empty custom field, `..`, `/` in a value, leading `_`): the document goes to review with check `path:folder`, never outside its entity tree — test `test_unsafe_folder_goes_to_review` (Task 2).
3. **Two equally specific rules disagree:** review with `rule:conflict`, never a silent pick — test `test_rule_conflict_goes_to_review` (Task 3).
4. **Broken rules file** (bad regex, unknown class): every command fails fast with the rule id in the message, before touching records — test `test_bad_rules_fail_fast` (Task 3).
5. **A class removed from config while records still use it:** those records go to review with check `class`, the engine does not crash — test `test_removed_class_goes_to_review` (Task 1).

---

### Task 1: Class registry in config

**Files:**
- Modify: `plugins/paperwork/lib/paperwork.py` — constants at L41-42, `normalize_proposal` L659, `SCHEMA` L748, `Archive` L852, `config_problems` L988, `check` L1080, `export_rows` L1991, every `normalize_proposal(` call site (`extract`, `cmd_record`, `cmd_set`, `template_test`)
- Test: `plugins/paperwork/tests/test_paperwork.py`

**Interfaces:**
- Produces:
  - `BUILTIN_CLASSES: dict[str, dict]` — keys `inv cn rcpt rem notice oc quote contract other`; each class dict has `label: str`, `money: bool`, `sign: "positive" | "negative" | None`, `required: list[str]` (dotted keys, `fields.<name>` allowed), `checks: list[str]` (only `"ustg14"` known), `name: str`, `folder: str`, `fields: dict[str, dict]`.
  - `FIELD_TYPES = {"text", "date", "money", "number", "bool", "choice"}`; a field spec is `{"type": ..., "label"?: str, "choices"?: list[str]}`.
  - `NAME_TEMPLATE = "{issue_date}_{class}_{counterparty}_{number}_{amount}_{id}"`, `FOLDER_TEMPLATE = "{entity}/{year}/{direction}"` (used by Task 2; defined here as every built-in's `name`/`folder`).
  - `merge_classes(cfg: dict) -> dict[str, dict]` — built-ins, then each `cfg["classes"][key]` shallow-merged over the built-in of the same key or added as new (new classes default to `money: False, sign: None, checks: [], required: ["issue_date"], fields: {}` and the default templates).
  - `Archive.classes` — property returning `merge_classes(self.config)`.
  - `normalize_proposal(p: dict, classes: dict = BUILTIN_CLASSES) -> dict` — `doc_type` must be a key of `classes`; new optional proposal key `fields` normalized by the class's field specs into `d["fields"]` (always present, `{}` when none).
  - `config_problems(cfg)` additionally validates `cfg.get("classes", {})`.

Built-in values (copy exactly; they reproduce today's `check()`):

| key | money | sign | required (beyond `issue_date`, `seller.name`) | checks |
|---|---|---|---|---|
| inv | true | positive | buyer.name, invoice_number, currency, gross | ustg14 |
| cn | true | negative | buyer.name, invoice_number, currency, gross | — |
| rcpt | true | positive | currency, gross | — |
| rem, notice, oc, quote, contract, other | false | None | — | — |

Labels: from today's `SCHEMA["doc_type"]` text (`inv` "invoice", `cn` "credit note, Storno, Rechnungskorrektur", …).

- [ ] **Step 1: Write the failing tests**

```python
    def write_config(self, **changes):
        path = os.path.join(self.root, "_paperwork", "config.json")
        cfg = json.loads(read(path))
        cfg.update(changes)
        write_json(path, cfg)

    def test_config_adds_a_class_with_required_fields(self):
        self.write_config(classes={"policy": {"label": "insurance policy",
                                              "fields": {"policy_number": {"type": "text"},
                                                         "start": {"type": "date"}},
                                              "required": ["issue_date", "seller.name", "fields.policy_number"]}})
        self.drop("a.pdf", text_pdf([hoster_invoice(extra=["Versicherungsschein Nr. VS-77"])]))
        self.pw("ingest")
        doc = self.only_pending()[0]["id"]
        p = hoster_proposal()
        p["doc_type"] = "policy"
        code, view, _ = self.propose(doc, p)
        self.assertEqual(code, 3)
        self.assertIn("required:fields.policy_number", [c["id"] for c in view["problems"]])
        p["fields"] = {"policy_number": "VS-77", "start": "2026-01-01"}
        path = os.path.join(self.root, "_paperwork", "proposals", doc + ".json")
        write_json(path, p)
        code, view, err = self.pw("record", doc, path, "--force")
        self.assertEqual(code, 0, (view, err))

    def test_bad_class_config_fails(self):
        self.write_config(classes={"Bad Key": {}})
        code, _, err = self.pw("status")
        self.assertNotEqual(code, 0)
        self.assertIn("classes", err)
        self.write_config(classes={"policy": {"fields": {"x": {"type": "colour"}}}})
        code, _, err = self.pw("status")
        self.assertIn("policy", err)

    def test_removed_class_goes_to_review(self):
        self.write_config(classes={"policy": {}})
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        doc = self.only_pending()[0]["id"]
        p = hoster_proposal()
        p["doc_type"] = "policy"
        self.assertEqual(self.propose(doc, p)[0], 0)
        self.write_config(classes={})
        self.pw("ingest")  # any recompute
        view = self.pw("show", doc[:8])[1]
        self.assertEqual(view["status"], "review")
        self.assertIn("class", [c["id"] for c in view["problems"]])
```

Also add to `Units`: `test_builtin_classes` asserting `set(pw.BUILTIN_CLASSES) == {"inv","cn","rcpt","rem","notice","oc","quote","contract","other"}` and `pw.normalize_proposal({"doc_type": "x"})` raises `pw.Fail`.

- [ ] **Step 2: Run them, expect failures**

Run: `plugins/paperwork/bin/paperwork __test -k class`
Expected: FAIL (`unknown proposal fields: fields`, `classes` not validated, `BUILTIN_CLASSES` missing).

- [ ] **Step 3: Implement the registry**

- Replace `DOC_TYPES`/`MONEY_TYPES` with `BUILTIN_CLASSES`; derive any remaining list need from it.
- `config_problems`: class keys match `^[a-z][a-z0-9-]{0,15}$`; field names match `^[a-z][a-z0-9_]{0,31}$`; field `type` in `FIELD_TYPES`; `choice` needs a non-empty `choices` list; `required` entries are proposal keys, dotted party keys or `fields.<declared name>`; messages start with `classes.<key>:`. Template validation is added in Task 2.
- `normalize_proposal`: add `"fields"` to `PROPOSAL_KEYS`; normalize per type — `date` via `iso_date`, `money` via `money(dec(...))`, `number` via `plain(dec(...))`, `bool` must be bool, `choice` must be in `choices`, `text` stripped; undeclared field name → `Fail("unknown field ... for class ...")`.
- `check()`: look up `cls = archive.classes.get(d["doc_type"])`; if missing add error `class` "class X is not in config.json" and skip class-specific checks. Required list = `cls["required"]` (built-ins: the table above, which equals today's logic). Replace `MONEY_TYPES` tests with `cls["money"]`, the `cn` sign tests with `cls["sign"]`, the `cn` evidence abs-compare with `cls["sign"] == "negative"`, the §14 block's `doc_type == "inv"` with `"ustg14" in cls["checks"]`.
- `export_rows`: replace `MONEY_TYPES` with the class's `money`.
- `cmd_schema`: emit `SCHEMA` with `doc_type` replaced by `{key: label}` of `archive.classes`, plus `"fields": {class: field specs}` for classes that declare fields (needs an `Archive`; keep working without one by falling back to built-ins).
- Pass `archive.classes` at every `normalize_proposal` call site.

- [ ] **Step 4: Run the whole suite**

Run: `plugins/paperwork/bin/paperwork __test`
Expected: all tests PASS, including every pre-existing test unchanged.

- [ ] **Step 5: Commit**

```bash
git add plugins/paperwork/lib/paperwork.py plugins/paperwork/tests/test_paperwork.py
git commit -m "feat(paperwork): document classes in config with typed fields"
```

---

### Task 2: Names and folders from class templates

**Files:**
- Modify: `plugins/paperwork/lib/paperwork.py` — `canonical_name` L1308, `target_path` L1316, `config_problems`
- Test: `plugins/paperwork/tests/test_paperwork.py`

**Interfaces:**
- Consumes: `Archive.classes`, `NAME_TEMPLATE`, `FOLDER_TEMPLATE` (Task 1).
- Produces:
  - `PLACEHOLDERS = {"issue_date", "due_date", "service_date", "year", "class", "counterparty", "number", "amount", "id", "entity", "direction", "category"}`, plus `fields.<name>` for the class's declared fields.
  - `template_problems(template: str, cls: dict) -> list[str]` — unknown placeholders, unbalanced braces; folder templates additionally must contain `{entity}` as their first segment.
  - `placeholder_values(record: dict, cls: dict) -> dict[str, str]` — every value already filesystem-safe; empty → `"-"`; `issue_date` empty → `"0000-00-00"`, `year` → `"0000"`, `counterparty` → `"unknown"`, `number` → `safe_number(invoice_number)`, `amount` → `"{gross}{currency}"` as today, `id` → first 8 hex; dates ISO; other fields `safe_number(str(v))`.
  - `render(template: str, values: dict[str, str]) -> str`.
  - `canonical_name(record, cls) -> tuple[str, str]` — `(name_without_ext, ext)`.
  - `target_path(record, archive) -> str` — unchanged signature and review/duplicate behaviour; the filed branch renders `cls["folder"]` and `cls["name"]`.

Path-length trimming keeps today's order, generalised: shorten `number`, then `counterparty`, then each `fields.*` placeholder in the order it appears in the name template, re-rendering after each, until the full path ≤ `MAX_PATH`.

Folder safety: after rendering, split on `/`; any segment that is empty, `-`, `.`, `..` or starts with `_`, or a first segment that is not the record's entity → the record gets error check `path:folder` (added in `compute`, so it shows in `problems`) and `target_path` returns the review path.

- [ ] **Step 1: Write the failing tests**

```python
    def test_upgrade_replans_zero_moves(self):
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        self.propose(self.only_pending()[0]["id"], hoster_proposal())
        self.file_all()
        self.write_config(classes={})  # explicit empty: built-ins only
        self.assertEqual(self.pw("plan")[1]["moves"], 0)

    def test_folder_and_name_templates(self):
        self.write_config(classes={"inv": {"folder": "{entity}/{year}"},
                                   "contract": {"fields": {"start": {"type": "date"}},
                                                "folder": "{entity}/contracts/{counterparty}",
                                                "name": "{fields.start}_{class}_{counterparty}_{id}"}})
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.drop("b.pdf", text_pdf([hoster_invoice(number="V-1", extra=["Vertrag ab 01.01.2026"])]))
        self.pw("ingest")
        a, b = [p["id"] for p in self.only_pending()]
        self.propose(a, hoster_proposal())
        p = hoster_proposal(number="V-1")
        p.update(doc_type="contract", fields={"start": "2026-01-01"})
        self.propose(b, p)
        targets = sorted(m["to"] for m in self.pw("plan")[1]["by_destination"]["to archive"])
        self.assertIn(f"nordlicht/contracts/muster-hosting/2026-01-01_contract_muster-hosting_{b[:8]}.pdf", targets)
        self.assertTrue(any(t.startswith("nordlicht/2026/2026-03-14_inv_") for t in targets))

    def test_unsafe_folder_goes_to_review(self):
        self.write_config(classes={"contract": {"fields": {"area": {"type": "text"}},
                                                "folder": "{entity}/{fields.area}"}})
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        doc = self.only_pending()[0]["id"]
        p = hoster_proposal()
        p.update(doc_type="contract", fields={"area": ".."})
        code, view, _ = self.propose(doc, p)
        self.assertEqual(code, 3)
        self.assertIn("path:folder", [c["id"] for c in view["problems"]])
        self.assertTrue(view["target"].startswith("_review/"))

    def test_bad_template_fails(self):
        self.write_config(classes={"inv": {"name": "{issue_date}_{colour}"}})
        code, _, err = self.pw("status")
        self.assertNotEqual(code, 0)
        self.assertIn("colour", err)
```

Add to `Units`: `render("{a}_{b}", {"a": "x", "b": "y"}) == "x_y"`.

- [ ] **Step 2: Run them, expect failures**

Run: `plugins/paperwork/bin/paperwork __test -k "template or folder or upgrade"`
Expected: FAIL (templates ignored; paths still hardcoded).

- [ ] **Step 3: Implement** `PLACEHOLDERS`, `template_problems` (wire into `config_problems` for `name` and `folder` of every merged class), `placeholder_values`, `render`, the new `canonical_name`, the template branch of `target_path` with the trimming and folder-safety rules above. `{class}` renders the class key.

- [ ] **Step 4: Run the whole suite**

Run: `plugins/paperwork/bin/paperwork __test`
Expected: all PASS; `test_inbox_to_archive_round_trip` still expects `nordlicht/2026/in/2026-03-14_inv_muster-hosting_RE-2026-0042_119.00EUR_<id>.pdf`.

- [ ] **Step 5: Commit**

```bash
git add plugins/paperwork/lib/paperwork.py plugins/paperwork/tests/test_paperwork.py
git commit -m "feat(paperwork): file names and folders rendered from class templates"
```

---

### Task 3: Rules engine, applied when fields are set

**Files:**
- Modify: `plugins/paperwork/lib/paperwork.py` — new section "Rules" after "Entities and checks"; `Archive.__init__`; `extract` L1519; `cmd_record` L1623; `cmd_set` L1666; `compute` L1273
- Test: `plugins/paperwork/tests/test_paperwork.py`

**Interfaces:**
- Consumes: `Archive.classes` (Task 1).
- Produces:
  - Rule file format, archive layer `_paperwork/rules.json`, user layer `_paperwork/rules/<user>.json` with `<user>` = env `PAPERWORK_USER` (slug; layer skipped when unset or file absent):
    ```json
    {"rules": [{"id": "hetzner-hosting",
                "when": {"counterparty": "hetzner-online", "text": ["Cloud Server"], "regex": "Rechnung\\s+Nr", "vat_id": "DE...", "doc_type": "inv", "entity": "acme"},
                "set":  {"doc_type": "inv", "entity": "acme", "direction": "in", "category": "hosting", "tags": ["server"], "fields.<name>": "..."}}]}
    ```
    `when` needs ≥ 1 key; `text` = all phrases appear (compared with `squash`); `regex` = `re.search(..., re.I | re.M)` on the derived text.
  - `RULE_WHEN = {"counterparty", "vat_id", "text", "regex", "doc_type", "entity"}`, `RULE_SET = {"doc_type", "entity", "direction", "category", "tags"}` plus `fields.<name>`.
  - `load_rules(archive) -> list[dict]` — each rule gets `"layer": "archive" | "user"`; raises `Fail` on any problem.
  - `rules_problems(doc: object, classes: dict, cfg: dict, layer: str) -> list[str]` — unknown keys, duplicate ids, empty `when`, invalid regex, unknown class / entity / category / field; every message starts with `rules[<layer>].<id>:`.
  - `match_rules(rules: list, record: dict, text: str) -> list[dict]`.
  - `decide(matches: list) -> tuple[dict[str, tuple[object, str]], list[str]]` — field → (value, rule id), plus conflict messages. Per field, archive-layer rules decide first: the most specific match (most `when` keys) wins; a tie with different values is a conflict. User-layer rules only fill fields the archive layer did not set. `tags` are unioned.
  - `apply_rules(archive, record) -> None` — on `record["data"]`: set each decided field; when it replaces a different non-empty value, add `{"field", "from", "to", "rule"}` to `record["rule_log"]`; record conflicts in `record["rule_conflicts"]`; set `record["rules"] = sorted(applied ids)`. Skips fields listed in `record["edits"]` (a person's edit beats a rule). Counterparty for `when.counterparty` comes from `archive.resolve_counterparty(party, create=False)`.
  - `compute` adds error check `rule:conflict` per conflict, warning `rule:override` per `rule_log` entry, and error `rule:entity` when a rule-set entity differs from the entity the billed/issuing party resolves to (`resolve_entity` without the explicit entity).

Call `apply_rules` right after `record["data"]` is assigned in `extract` (XML and template routes), `cmd_record` and `cmd_set`. `Archive.__init__` loads rules once (`self.rules = load_rules(self)`), so a broken file fails every command.

- [ ] **Step 1: Write the failing tests**

```python
    def write_rules(self, rules, user=None):
        name = "rules.json" if not user else os.path.join("rules", user + ".json")
        path = os.path.join(self.root, "_paperwork", name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        write_json(path, {"rules": rules})

    def test_rule_sets_class_and_category(self):
        self.write_rules([{"id": "hoster", "when": {"text": ["Cloud Server"]},
                           "set": {"category": "hosting", "tags": ["server"]}}])
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        doc = self.only_pending()[0]["id"]
        code, view, err = self.propose(doc, hoster_proposal())
        self.assertEqual(code, 0, (view, err))
        rec = json.loads(read(os.path.join(self.root, "_paperwork", "docs", view["id"] + ".json")))
        self.assertEqual(rec["data"]["category"], "hosting")
        self.assertEqual(rec["data"]["tags"], ["server"])
        self.assertEqual(rec["rules"], ["hoster"])

    def test_rule_overrides_proposal_with_a_warning(self):
        self.write_rules([{"id": "is-receipt", "when": {"counterparty": "muster-hosting"}, "set": {"doc_type": "rcpt"}}])
        # first document creates the counterparty, second is ruled
        for n in ("A-1", "A-2"):
            self.drop(n + ".pdf", text_pdf([hoster_invoice(number=n)]))
        self.pw("ingest")
        a, b = [p["id"] for p in self.only_pending()]
        self.propose(a, hoster_proposal(number="A-1"))
        code, view, _ = self.propose(b, hoster_proposal(number="A-2"))
        self.assertIn("rule:override", [c["id"] for c in view["warnings"]])

    def test_rule_conflict_goes_to_review(self):
        self.write_rules([{"id": "a", "when": {"text": ["Cloud Server"]}, "set": {"category": "hosting"}},
                          {"id": "b", "when": {"text": ["Gesamtbetrag"]}, "set": {"category": "software"}}])
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        code, view, _ = self.propose(self.only_pending()[0]["id"], hoster_proposal())
        self.assertEqual(code, 3)
        self.assertIn("rule:conflict", [c["id"] for c in view["problems"]])

    def test_user_rules_only_fill_gaps(self):
        self.write_rules([{"id": "arch", "when": {"text": ["Cloud Server"]}, "set": {"category": "hosting"}}])
        self.write_rules([{"id": "mine", "when": {"text": ["Cloud Server"]},
                           "set": {"category": "software", "tags": ["mine"]}}], user="erika")
        os.environ["PAPERWORK_USER"] = "erika"
        self.addCleanup(os.environ.pop, "PAPERWORK_USER", None)
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        code, view, _ = self.propose(self.only_pending()[0]["id"], hoster_proposal())
        rec = json.loads(read(os.path.join(self.root, "_paperwork", "docs", view["id"] + ".json")))
        self.assertEqual((rec["data"]["category"], rec["data"]["tags"]), ("hosting", ["mine"]))

    def test_bad_rules_fail_fast(self):
        self.write_rules([{"id": "broken", "when": {"regex": "("}, "set": {"category": "hosting"}}])
        code, _, err = self.pw("status")
        self.assertNotEqual(code, 0)
        self.assertIn("broken", err)
        self.write_rules([{"id": "noclass", "when": {"text": ["x"]}, "set": {"doc_type": "invoice"}}])
        self.assertIn("noclass", self.pw("status")[2])
```

(`run()` calls `pw.main` in-process, so `os.environ["PAPERWORK_USER"]` reaches the engine.)

- [ ] **Step 2: Run them, expect failures**

Run: `plugins/paperwork/bin/paperwork __test -k rule`
Expected: FAIL (no rules support).

- [ ] **Step 3: Implement** the Rules section with the signatures above, wire `apply_rules` into the three call sites, and the three checks into `compute`.

- [ ] **Step 4: Run the whole suite**

Run: `plugins/paperwork/bin/paperwork __test`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/paperwork/lib/paperwork.py plugins/paperwork/tests/test_paperwork.py
git commit -m "feat(paperwork): user rules that set class, entity, category and tags"
```

---

### Task 4: `rules test`, `rules apply`, hints for Claude, guard and launcher

**Files:**
- Modify: `plugins/paperwork/lib/paperwork.py` — `parser` L2169, `cmd_pending` L1588, new `cmd_rules`
- Modify: `plugins/paperwork/hooks/guard.py:18-19`
- Modify: `plugins/paperwork/bin/paperwork` (the final `run` line: add `-e PAPERWORK_USER`)
- Test: `plugins/paperwork/tests/test_paperwork.py`

**Interfaces:**
- Consumes: `load_rules`, `match_rules`, `decide`, `apply_rules` (Task 3).
- Produces:
  - `paperwork rules test [--file <path>]` — validates (the given file replaces the archive layer for this run), then for every record with fields emits `{"id", "rules": [ids], "changes": [{"field", "from", "to", "rule"}], "conflicts": [...]}` for records whose result would differ; writes nothing. Exit 0, or 1 when the file is invalid.
  - `paperwork rules apply` — under the lock, re-runs `apply_rules` on every record whose `source` is not `"user"` (fields in `edits` stay untouched by Task 3's rule), recomputes, saves, emits the same change list.
  - `pending` items gain `"rule_hints": {field: value}` from rules whose `when` uses only `text`/`regex` (the only conditions known before reading).
  - Guard: `WRITABLE` adds `"_paperwork/rules/"`, `WRITABLE_FILES` adds `"_paperwork/rules.json"`.

- [ ] **Step 1: Write the failing tests**

```python
    def test_rules_test_previews_without_writing(self):
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        doc = self.only_pending()[0]["id"]
        self.propose(doc, hoster_proposal())
        docs = os.path.join(self.root, "_paperwork", "docs")
        before = {n: read(os.path.join(docs, n)) for n in os.listdir(docs)}
        self.write_rules([{"id": "hoster", "when": {"text": ["Cloud Server"]}, "set": {"category": "hosting"}}])
        code, out, err = self.pw("rules", "test")
        self.assertEqual(code, 0, err)
        self.assertEqual(out["changes"][0]["changes"][0]["to"], "hosting")
        self.assertEqual(before, {n: read(os.path.join(docs, n)) for n in os.listdir(docs)})
        code, out, _ = self.pw("rules", "apply")
        self.assertEqual(json.loads(read(os.path.join(docs, doc_file(docs, doc))))["data"]["category"], "hosting")

    def test_pending_carries_text_rule_hints(self):
        self.write_rules([{"id": "hoster", "when": {"text": ["Cloud Server"]}, "set": {"doc_type": "inv"}}])
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        self.assertEqual(self.only_pending()[0]["rule_hints"], {"doc_type": "inv"})
```

(`doc_file(docs, prefix)` — small helper returning the record file name starting with `prefix`.)
Guard, in `test_edits`: `assertIsNone(verdict("Write", {"file_path": "/data/Belege/_paperwork/rules.json"}))` and the same for `/data/Belege/_paperwork/rules/erika.json`.

- [ ] **Step 2: Run them, expect failures**

Run: `plugins/paperwork/bin/paperwork __test -k "rules_test or rule_hints or edits"`
Expected: FAIL.

- [ ] **Step 3: Implement** `cmd_rules` with subcommands `test` and `apply` (argparse `action` choice plus `--file`), the `rule_hints` in `cmd_pending`, the guard allowlist and the launcher env pass-through.

- [ ] **Step 4: Run the whole suite**

Run: `plugins/paperwork/bin/paperwork __test`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/paperwork/lib/paperwork.py plugins/paperwork/hooks/guard.py plugins/paperwork/bin/paperwork plugins/paperwork/tests/test_paperwork.py
git commit -m "feat(paperwork): rules test and apply, rule hints in pending"
```

---

### Task 5: Unconfirmed outcome, alternatives and `confirm`

**Files:**
- Modify: `plugins/paperwork/lib/paperwork.py` — `PROPOSAL_KEYS`/`normalize_proposal`, `SCHEMA`, `Archive.resolve_counterparty`, `compute`, `status_of` L1290, `record_view` L1613, `export_rows` (status filter at L1991 and a `confirmed` column), `parser`, new `cmd_confirm`
- Test: `plugins/paperwork/tests/test_paperwork.py`

**Interfaces:**
- Consumes: `record["rules"]`, `record["rule_log"]` (Task 3).
- Produces:
  - Proposal key `alternatives`: `{"doc_type": [class keys], "entity": [entity slugs], "counterparty": [names]}`, each optional, ranked best-first, max 3 per key; unknown class or entity → `Fail`. Stored as `d["alternatives"]` (`{}` when none).
  - `needs_confirmation(record: dict) -> bool` — true when `record["source"] == "claude"`, no `record.get("confirmed")`, and either no applied rule set `doc_type` or the counterparty is a proposed vendor.
  - `resolve_counterparty(party, create=True, proposed=False)` — a vendor created with `proposed=True` gets `"proposed": True`; `compute` passes `proposed=(record.get("source") == "claude")` and adds warning `counterparty:new` when the record's vendor is proposed.
  - `status_of`: where it would return `"ok"` or `"filed"` and `needs_confirmation(record)` → `"unconfirmed"`. `target_path` is unchanged: unconfirmed documents are filed like the others.
  - `record_view` adds `"confirmed": bool` and `"alternatives"`.
  - `paperwork confirm <id> [<id> ...]` — under the lock sets `record["confirmed"] = {"at": now()}` and clears `proposed` on the record's vendor; refuses a record in `review`. `cmd_set` also sets `confirmed` (a person edited it).
  - Exports include `unconfirmed` documents (same filter as `ok`/`filed`) and a `confirmed` column (`true`/`false`) in `documents.csv`.

- [ ] **Step 1: Write the failing tests**

```python
    def test_claude_alone_is_unconfirmed_until_confirmed(self):
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        doc = self.only_pending()[0]["id"]
        p = hoster_proposal()
        p["alternatives"] = {"doc_type": ["rcpt"]}
        code, view, err = self.propose(doc, p)
        self.assertEqual(code, 0, (view, err))
        self.assertEqual(view["status"], "unconfirmed")
        self.assertIn("counterparty:new", [c["id"] for c in view["warnings"]])
        self.assertEqual(view["alternatives"], {"doc_type": ["rcpt"]})
        self.file_all()
        self.assertEqual(self.pw("show", doc[:8])[1]["status"], "unconfirmed")
        self.assertEqual(len(self.pw("list", "--status", "unconfirmed")[1]["documents"]), 1)
        code, _, err = self.pw("confirm", doc[:8])
        self.assertEqual(code, 0, err)
        self.assertEqual(self.pw("show", doc[:8])[1]["status"], "filed")
        self.assertFalse(self.pw("vendors")[1]["vendors"][0].get("proposed"))

    def test_xml_and_ruled_documents_need_no_confirmation(self):
        self.write_rules([{"id": "hoster", "when": {"text": ["Cloud Server"]}, "set": {"doc_type": "inv"}}])
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        doc = self.only_pending()[0]["id"]
        self.propose(doc, hoster_proposal())
        self.pw("confirm", doc[:8])  # confirms the new vendor once
        self.drop("b.pdf", text_pdf([hoster_invoice(number="RE-2")]))
        self.pw("ingest")
        code, view, _ = self.propose(self.only_pending()[0]["id"], hoster_proposal(number="RE-2"))
        self.assertEqual(view["status"], "ok")

    def test_alternatives_must_be_known(self):
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        p = hoster_proposal()
        p["alternatives"] = {"doc_type": ["invoice"]}
        code, _, err = self.propose(self.only_pending()[0]["id"], p)
        self.assertEqual(code, 2)
        self.assertIn("alternatives", err)
```

Check the existing assertions that expect `"ok"`/`"filed"` after a Claude proposal (`test_inbox_to_archive_round_trip` and others): they now see `"unconfirmed"`. Update each to confirm first (`self.pw("confirm", doc[:8])`) or to expect `"unconfirmed"`, keeping what the test is about; do not weaken any other assertion.

- [ ] **Step 2: Run them, expect failures**

Run: `plugins/paperwork/bin/paperwork __test -k "unconfirmed or confirmation or alternatives"`
Expected: FAIL.

- [ ] **Step 3: Implement** the interfaces above.

- [ ] **Step 4: Run the whole suite**

Run: `plugins/paperwork/bin/paperwork __test`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/paperwork/lib/paperwork.py plugins/paperwork/tests/test_paperwork.py
git commit -m "feat(paperwork): unconfirmed outcome with alternatives and confirm"
```

---

### Task 6: Class fields in the exports

**Files:**
- Modify: `plugins/paperwork/lib/paperwork.py` — `export_rows` L1953, `cmd_export` L2026
- Test: `plugins/paperwork/tests/test_paperwork.py`

**Interfaces:**
- Consumes: `Archive.classes` with `fields` (Task 1).
- Produces: for every class that declares fields and has at least one exportable document, `exports/<scope>/class-<key>.csv` (and `-de` variant like the others) with columns `id, entity, counterparty, issue_date, status, confirmed, path`, then the class's fields in declaration order. Byte-identical on re-export, like the existing files.

- [ ] **Step 1: Write the failing test**

```python
    def test_class_fields_are_exported(self):
        self.write_config(classes={"contract": {"fields": {"start": {"type": "date"}, "notice": {"type": "text"}}}})
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        doc = self.only_pending()[0]["id"]
        p = hoster_proposal()
        p.update(doc_type="contract", fields={"start": "2026-01-01", "notice": "3 Monate"})
        self.propose(doc, p)
        self.pw("export")
        rows = self.csv_rows("all", "class-contract.csv")
        self.assertEqual((rows[0]["start"], rows[0]["notice"]), ("2026-01-01", "3 Monate"))
        self.assertTrue(self.pw("export")[1]["unchanged"])
```

- [ ] **Step 2: Run it, expect failure**

Run: `plugins/paperwork/bin/paperwork __test -k class_fields`
Expected: FAIL (file missing).

- [ ] **Step 3: Implement** the per-class tables inside `export_rows` and write them in `cmd_export` through the existing `table_text`.

- [ ] **Step 4: Run the whole suite**

Run: `plugins/paperwork/bin/paperwork __test`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/paperwork/lib/paperwork.py plugins/paperwork/tests/test_paperwork.py
git commit -m "feat(paperwork): export class fields per class"
```

---

### Task 7: Skills, docs and version

**Files:**
- Modify: `plugins/paperwork/skills/inbox/SKILL.md`, `skills/review/SKILL.md`, `skills/setup/SKILL.md`, `skills/ask/SKILL.md` (mention `class-*.csv`)
- Modify: `plugins/paperwork/README.md`, `plugins/paperwork/DESIGN.md`
- Modify: `plugins/paperwork/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `lib/paperwork.py` (`VERSION`), every skill's `metadata.version`

Content to add (decisions, not prose to invent):

- **inbox skill:** Workflow step 2 — read `rule_hints` and follow them unless the document clearly contradicts them (then say so in `notes`). Step 3 — `doc_type` must be one of the classes `paperwork schema` lists; fill `fields` the class declares; add `alternatives` when unsure between classes, entities or counterparties (ranked, max 3). Rules section — "Only existing classes and entities; a new counterparty is fine but will be *unconfirmed*." Report — list unconfirmed documents with their alternatives and offer `paperwork confirm <id>...`; when the same correction recurs, offer a rule in `_paperwork/rules.json` and run `paperwork rules test` before saving it.
- **review skill:** a second queue: `paperwork list --status unconfirmed`; for each, show the choice and alternatives, then `confirm` or `set`.
- **setup skill:** optional step — classes beyond the built-ins (`classes` in `config.json`: label, fields, required, name, folder) and a first `rules.json`; always run `paperwork plan` after a template change and show the renames.
- **README:** the archive layout gains `_paperwork/rules.json` and `rules/<user>.json`; new commands `rules test|apply`, `confirm`; status `unconfirmed`; a short config example with one custom class and one rule; the file-name section notes names and folders come from the class templates (defaults unchanged).
- **DESIGN.md:** replace the "naming" mention in the config line with "classes (fields, required, checks, name and folder templates)"; add a "Classes and rules" section stating: class = the one place that decides fields, checks, name and folder; rule layers and precedence (archive before user, most specific wins, tie → review, a person's edit beats a rule); rules applied when fields are set, re-applied only by `rules apply`; the three outcomes.
- Version `0.2.0`.

- [ ] **Step 1: Make the edits above.**
- [ ] **Step 2: Check every version string**

Run: `grep -rn "0\.1\.0" plugins/paperwork .claude-plugin/marketplace.json`
Expected: no paperwork hits left.

- [ ] **Step 3: Run the whole suite once more**

Run: `plugins/paperwork/bin/paperwork __test`
Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add plugins/paperwork .claude-plugin/marketplace.json
git commit -m "feat(paperwork): classes, rules and confirmation in skills and docs (0.2.0)"
```
