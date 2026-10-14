---
name: oppenheimer
description: >
  Use before building, releasing or open-sourcing a *capability* that could be turned to
  serious harm once it exists — a model, a tool, a dataset, an exploit technique, a
  surveillance, targeting, persuasion, automation or scraping system, a research result,
  anything dual-use — and above all when the work is technically exciting and moving fast.
  Also use when the user says "oppenheimer", "von braun", "dual-use", "should we even
  build this", "what if this falls into the wrong hands", "can this be weaponized", "we
  can't un-invent it", "if we don't, someone else will", or "not my department". Unlike
  dystopia (harm from a product's adoption), this is about the capability itself, who ends
  up holding it, and the builder's own responsibility. NOT a substitute for legal,
  export-control, biosafety or security review, and never a guide to causing the harm.
user-invocable: true
argument-hint: "[capability, model, tool or research to reckon with before it exists]"
---

# Oppenheimer

It worked perfectly. Then it was used.

Two lines carry the feeling. Oppenheimer, recalling the first test: *"We knew the world would not be the same… Now I am become Death, the destroyer of worlds"* (NBC, 1965). And the line attributed — doubtfully — to von Braun when the first V-2 hit London: *"The rocket worked perfectly, except for landing on the wrong planet."* Both are the moment after: a technical triumph, and the creator realising the triumph was never the point. This skill moves that moment to *before*, while the choice is still open.

It differs from its siblings. A premortem asks why the plan failed. Dystopia asks what its adoption did to people. This asks what the *capability* does once it exists — in anyone's hands, for any purpose, forever — and what the person building it owes that future.

## Why builders miss it

The blind spots are documented, and they're the lenses below:

- **"Technically sweet."** Oppenheimer in 1954: when you see something technically sweet, you go ahead and do it, and argue about what to do with it only after the technical success. Momentum and fascination outrun judgement.
- **"Not my department."** Tom Lehrer's von Braun (1965): *"Once the rockets are up, who cares where they come down?"* Responsibility gets split until nobody holds it.
- **"If we don't, someone else will."** The race argument. Sometimes true — and then the question becomes how much *this* work adds, which the race argument never asks.
- **"We'll govern it later."** The Collingridge dilemma (1980): while a technology is young, it's easy to shape but its effects are unknown; once its effects are known, it's entrenched and hard to change. Later is when control is gone.
- **Nobody outside the room.** The Franck Report (June 1945) — scientists urging a warning or a demonstration on an uninhabited site before any use on a city — was written, but the scientific panel advised direct use and the report likely never reached the president. The dissent existed; it came too late and through too few hands.

## First: screen it

Most capabilities are ordinary. Before the full pass, answer two questions in a line each:

1. **Uplift** — does this give a hostile holder meaningfully more than they can already get for free?
2. **Ceiling** — is the worst credible misuse severe, large-scale, or impossible to recall?

Both clearly no (a file converter, a UI library, a CRUD app): give the TL;DR — **build** — with the reason in a clause, name the one ordinary risk worth a fix if there is one, and stop. Under 100 words, no tables, no lists. Either yes, or genuinely unsure: run the full pass.

## Hold the frame

- **It exists and it was used. Past tense, certain.** Not "this could be weaponized" — "eighteen months after release, it was running in …" Its existence isn't in question; what it was used for is.
- **Name the holder.** Every use has a hand on it: a state, a company, a criminal group, an insider, a lone actor, *your own side under pressure*. The bomb was used by the people who meant well.
- **Stay at the level of purpose, never recipe.** Describe what was done and to whom, not how to do it. This skill reasons about consequences; it never produces operational detail for the harm, and it stops if the conversation turns that way.
- **No hedging while you generate; honest at the boundary.** The scenarios are a method, not predictions. Report them as risks and decisions, plainly.

## The pass

1. **Name the capability, not the product.** Strip the intended use. What can now be done that couldn't before — by whom, at what cost, at what scale? *"Anyone with a laptop can now X in minutes."* The demo is the intended use; the capability is everything else.
2. **It got out.** State, as fact, how it left your control: released, open-sourced, copied, leaked, sold, acquired, the company changed hands, the government asked. Assume whatever *can* be copied, was.
3. **The day it was used.** From each lens below, write who used it, for what, and against whom — at full capability, at the worst plausible moment. Include your own side, under pressure, with the best intentions. Aim for 6–10.
4. **The builder's account.** For each, write the sentence you'd have told yourself while building it — "it's just a tool," "the race," "that's for policy to decide." Those sentences are the failure; name them so they can't do their work quietly.
5. **Now judge — out of the frame.** Imagined catastrophes feel likelier than they are (Koehler 1991), and dismissed ones feel safer. Judge on:
   - **Uplift** — how much does this add over what is already available? A capability that already exists in the wild changes little; a step-change for the worst holder changes much. This counterfactual is the honest version of "someone else will."
   - **Magnitude** — worst credible harm, and to how many.
   - **Reversibility** — can it be recalled, patched, revoked? Weights, papers and techniques can't.
   - **Who holds it** — how many, and how well-intentioned, how accountable.
   - **Precedent** — what happened to comparable capabilities once they existed?
6. **Decide the lines now**, while you are still free to:
   - **Red lines** — the uses, buyers or conditions under which you stop, refuse, or pull it — written down before the money, the deadline and the excitement are in the room.
   - **Shape the capability** — build less of it: narrower, slower, auditable, gated, staged, watermarked, with a kill switch, or only the defensive half.
   - **Who else must be in the room** — the people it lands on, an independent reviewer, the relevant safety or ethics body. Send the Franck Report *before* the decision, to someone with the power to act on it.
   - **Your own position** — what you'd do if your red line were crossed by your employer, client or government. Decide it now.
7. **Verdict:** **build**, **build differently** (and how), **build with these controls**, or **don't build** — with the uplift and reversibility that decided it. Then one more round: *it was built your way, and it was still used — how?*

## Lenses

- **The worst holder** — a hostile state, a criminal group, a terrorist, a stalker: what is the most it gives them?
- **Your own side under pressure** — a war, a crisis, a quarter that has to be saved. What did the well-meaning use it for?
- **The insider** — an employee, a contractor, an admin with access. What could one person do alone?
- **The successor** — the acquirer, the next leadership, the next government. Who inherits it, and what do they want?
- **The leak** — once copied, it's everyone's. Who is the least accountable holder of a copy?
- **The automation** — the same act, now done a million times, faster than anyone can review.
- **The arms race** — what does building it make others build, and what's the equilibrium?
- **The target** — the person or group it is ultimately pointed at. Write from their side.

## Red flags — you've left the frame

- "It's just a tool." → Tools have holders. Name them.
- "Someone else would build it anyway." → Then measure the uplift; don't assume it's zero.
- "Policy will handle it." → Name who, with what power, by when.
- You described the intended use. → That's the demo. Describe the capability.
- You're writing how the harm would be done. → Stop. Purpose and consequence only.
- The only control is a terms-of-service clause. → What does the system itself make impossible?

## Rationalizations

| Excuse | Reality |
|--------|---------|
| "It's technically sweet — let's see if it works first." | Oppenheimer's own diagnosis of what went wrong. Decide the lines before the success, when you still can. |
| "We're the good guys." | The holder changes. And the good guys used it too. |
| "It's open science; knowledge should be free." | Often right — and still a choice about *this* result, *now*, at *this* level of detail. Weigh the uplift. |
| "I'm just the engineer." | "Not my department" is the line this skill is named against. |
| "It's too early to know." | Collingridge: early is the only time you can still shape it. |

## Scale to the stakes

The screen above settles the ordinary cases; a screen that finds low uplift and recoverable harm is a good result, not a skipped one. Anything with high uplift for a hostile holder, mass scale, or no way to recall it gets the full pass and a human decision-maker beyond the builder. Where a domain has a formal process — biosafety and dual-use research of concern review, export control, a responsible-disclosure policy, an AI release policy — name it and route to it; this skill prepares the case, it doesn't replace the review.

## Output

Generate fully, show tight: the pass happens in your head and in the full cause list, but the reader gets only what changes the decision. No preamble, no restating the plan, no narrating the method, no closing summary. Every line names a specific thing from this plan — a step, a number, a person, a file — never a category. Numbers where the plan has numbers.

```
**TL;DR:** <verdict> — <uplift and reversibility in one clause>; <the line or control that matters most>.

**The capability:** <what anyone can now do, without the intended use, one sentence>. **It got out:** <how, one sentence>.

**Top uses**
1. <holder> used it to <purpose> against <whom>. Builder's sentence: "<…>". <uplift · magnitude · reversibility — precedent>.
2. …  (3–5 in all, ranked)

**Also surfaced:** <the rest, a few words each, one line>
**Red lines:** <condition> → <what we do>   (one line each)
**Shape:** <how the capability is narrowed, gated or staged, one or two lines>
**In the room:** <who reviews it, before when>
**Verdict:** build / build differently / build with controls / don't build — <why, one sentence>
```

Full pass: under 450 words. Screened out as ordinary: the TL;DR line and at most two sentences — under 100 words.

Hard limits: each top item is at most two sentences plus its → line. "Also surfaced" is one line, comma-separated, not bullets. The verdict is one sentence plus the residual risk — don't re-list the plan. No line before the TL;DR (don't announce the depth you chose), and at most one short closing line, only to offer writing the red lines down.

$ARGUMENTS
