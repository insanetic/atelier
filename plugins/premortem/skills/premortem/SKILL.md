---
name: premortem
description: >
  Use before committing to anything costly or hard to reverse — shipping, merging,
  launching, releasing, deploying, or finalizing a plan, design, architecture, or
  refactor — to surface the failure modes that optimism and consensus are hiding. Also
  use when the user says "premortem" / "pre-mortem", or asks "what could go wrong",
  "why might this fail", "stress-test" / "pressure-test this", "poke holes", "red team
  this", "find the failure modes", or "is this actually ready". Primarily for coding and
  web design / UX (production incidents, rollbacks, data loss, edge cases, accessibility,
  confused users, abandonment), and adaptable to marketing, design, or any plan. The
  symptoms that mean it's needed: high confidence, "tested well", "should be fine",
  "just a formality", "quick sanity check", everyone agrees. NOT a postmortem of a real
  past incident, and NOT a substitute for normal bug / security review — it complements them.
user-invocable: true
argument-hint: "[plan, change, PR or launch to premortem]"
---

# Premortem

It already failed. Work backward from the failure to find the causes while there's still time to fix them — because "what *went* wrong?" surfaces far more than "what *could* go wrong?"

## Hold the frame

The technique only works if you treat the failure as something that has already happened. The instant you slip back into "could / might / probably," you're forecasting again — optimism returns, the candor evaporates, and you lose most of what this is for. Protect the frame:

- **It failed. Past tense, certain.** Write "users churned," "we rolled it back," "the data was corrupted" — never "this might fail" or "there's a risk that." The shift from *could* to *did* is the entire mechanism.
- **No hedging while you generate.** Banned until you rank: *might, could, would, may, if, probably, likely, possibly, most plausible, in theory, hopefully, should be fine, to be safe.* Each one smuggles optimism back in.
- **Stay in character.** Don't narrate it as an exercise or a simulation, don't narrate the method either ("let me hold the frame…"), and don't reassure ("of course this probably won't happen"). Just write the failure. Breaking character breaks the effect.
- **Say the quiet part.** Failure is assumed, so naming a weakness isn't disloyalty or being negative — it's the job. Write the doubt you'd normally keep polite about.
- **Honest at the boundary.** This surfaces *real* risks, not fiction. Report them as genuine risks and concrete fixes. Never imply an incident actually happened, and never soften a finding to be reassuring.

## The pass

1. **Name it.** One line: what's shipping, and what success looked like — the thing under the knife and the bar it had to clear.
2. **Jump to the failure.** Pick a concrete moment ("three weeks after launch") and state the failure as a fact, vividly and specifically. Not "it had problems" — *"signups fell 40% the first week and never recovered; the team reverted on day 19."* Decide what "failed" concretely means here.
3. **Work backward from every vantage.** Walk the vantage points below, each as a *separate* observer, and for each write down why it failed. Get everything out — aim for 8–12 — without filtering for likelihood. Include the ones that implicate the premise itself (we were wrong about what users wanted; the one person who understood it left).
4. **Make each cause real.** For every cause capture three things:
   - **Mechanism** — how it actually played out, concretely.
   - **False assumption** — what we believed going in that turned out untrue.
   - **Earliest signal** — the first thing we'd have observed as it started to go wrong.
5. **Now rank.** Only here does likelihood return. Compact table — cause · likelihood (H/M/L) · impact (H/M/L). Pull the few that are both likely and damaging.
6. **Change the plan now.** For each top cause, the specific change to make before proceeding: the guardrail, test, flag, or redesign that removes it or catches it at the earliest signal.

## Vantage points

Pick the packs that fit. Generate from each as a distinct observer — that independence is what stops you anchoring on your first idea.

- **Any domain:** the assumption nobody checked · what we didn't build or scope · a dependency that failed us · the empty / edge / degenerate case · whoever inherits this in six months · worked-in-dev, broke-in-reality · the silent failure (wrong result, no error).
- **Code / systems:** load and scale · concurrency and races · the rollback and the migration · an integration contract that drifted · security and abuse · the observability gap (it broke and nothing alerted) · the 3am on-call · data loss or corruption · backward compatibility.
- **Web / UX:** the confused first-timer · the power user · accessibility (keyboard, screen reader, contrast) · small screen and slow network · the empty / loading / error states · trust and abandonment (the form, the checkout) · content overflow and i18n · the user who does it "wrong."
- **Other domains (marketing, design, ops…):** name the people or forces whose disappointment *is* the failure, and make each one a vantage.

## Red flags — you've left the frame

- You wrote "could," "might," or "would." → State it as already done.
- You ordered causes "by likelihood" while generating. → Stop ranking; finish surfacing.
- A cause is vague ("quality issues," "performance problems"). → Name the exact mechanism.
- You stopped at three or four. → Keep going; the useful ones surface late.
- You skipped one because "that won't happen." → That's the one. Write it.
- You softened it or added reassurance. → Delete the hedge.

## Rationalizations

| Excuse | Reality |
|--------|---------|
| "I'll just list the risks." | A risk list is conditional and polite. Past-tense certainty is what buys the ~30% more real failures found. Hold the frame. |
| "Ranking as I go is efficient." | Ranking while generating filters out the uncomfortable causes before they're written. Generate first, rank last. |
| "It's a quick check / a box to tick." | "Quick check" confidence is exactly when failures hide. Scale the depth down, never the frame — still past tense, still concrete. |
| "I shouldn't alarm them / I'll stay balanced." | Balance is for the decision, not the premortem. Here your only job is the failure case, fully. |
| "I should hedge to stay honest." | Honesty is reporting real risks plainly — not diluting them with "probably won't happen." Commit while generating; be honest at the boundary. |
| "The change isn't even written / I can't see it." | Premortem the plan, not the diff. Ground it where you can, name assumptions where you can't, flag the gap — then proceed. |

## Scale to the stakes

A small or reversible change earns a 30-second pass: a few causes, fix the top one, move on. A costly or one-way change earns the full pass. When they ask for it tight, compress the *presentation* — lead with the ranked few that matter, one line each for the rest — never the frame or the generation. For the highest-stakes calls, go wide — dispatch parallel agents, each holding one vantage, so causes are generated independently with no anchoring (use superpowers:dispatching-parallel-agents when it's installed). Hold the frame at every size.

$ARGUMENTS
