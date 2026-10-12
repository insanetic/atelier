# Starting a catalog

A repository without `.claude/rules/` gets these files. Product name `acme`, product prefix `AC`.

```
.claude/rules/
  arch.md          the contract and cross-cutting entries; no paths, loads in every session
  <area>.md        core entries per area, scoped by paths (go.md, angular.md, sql.md, ...)
  authoring.md     this repo's ID prefixes and file names; paths: .claude/rules/**
  acme-arch.md     product prefix and product-wide entries; no paths
  acme-<area>.md   product additions per area, same paths as <area>.md
```

## The contract

The top of the always-loaded core file, before any entry:

```markdown
# Conventions

Each entry is one rule with a stable ID: `### <ID> [MUST|SHOULD] <rule>`, then what it means, examples, how it is
checked and why.

- **MUST** holds everywhere. The only exception is the waiver an entry names, written where the exception is, with its
  reason; a new waiver needs the maintainer's approval.
- **SHOULD** needs judgment, and the entry says what can outweigh it. When you deviate, name the entry and the reason
  in your reply.
- **Checked by** names the lint rule, test or hook that enforces the entry; its failure message starts with the ID
  and says the fix. `review` means no machine checks it yet: you are the check.
- **Core and product.** Unprefixed files are shared by every product and identical in each repository; files
  prefixed with the product's name hold its additions. If a product entry seems to contradict the core, the core wins.
- **Your instructions come first.** An explicit instruction from the maintainer in the session takes precedence over
  any entry. The change records it: the entry's waiver marker, or a line in the reply or commit naming the entry.
- **Cite, never restate.** Skills, docs and messages refer to a convention by its ID.
- **Entries win.** Where code contradicts an entry, the entry wins and the contradiction is reported as a catalog gap,
  never copied.
```

Then run `rulebook check`: it must pass before the first entry is cited anywhere.

## A scoped core file

```markdown
---
paths:
  - 'src/**/*.ts'
  - 'src/**/*.html'
---

# Angular

### NG-001 [MUST] Components use OnPush change detection

Every `@Component` sets `changeDetection: ChangeDetectionStrategy.OnPush`; the template reads signals, inputs or the
`async` pipe.

- Bad: no `changeDetection` key, so the component falls back to Default.
- Checked by: eslint @angular-eslint/prefer-on-push-component-change-detection

### NG-002 [MUST] HTTP is called only from services

Components, directives and pipes call a method on an injectable service that owns the endpoint and its types.

- Bad: `inject(HttpClient)` in a `*.component.ts`.
- Checked by: eslint no-restricted-imports (HttpClient in components, directives, pipes)

### NG-003 [SHOULD] Local state is a signal

State owned by one component or service is a `signal()`, derived state a `computed()`. Outweighed when a public API
already exposes an Observable other code consumes.

- Bad: a private `BehaviorSubject` read only by its own template.
- Checked by: review
```

## Product additions with pointers

A product file may end with the places a core entry is applied:

```markdown
## Examples of core entries here

- NG-002: PlanService (src/app/plans/plan.service.ts)
```
