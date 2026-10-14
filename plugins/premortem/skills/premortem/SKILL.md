---
name: premortem
description: >
  Use before committing to anything costly or hard to reverse — shipping, merging,
  launching, releasing, migrating, hiring, signing, investing, or finalizing a plan,
  design, strategy, or decision in any domain — to surface the failure modes that optimism
  and consensus are hiding. Also use when the user says "premortem" / "pre-mortem", or asks
  "what could go wrong", "why might this fail", "stress-test" / "pressure-test this",
  "poke holes", "red team this", "find the failure modes", or "is this actually ready".
  Symptoms that mean it's needed: high confidence, "tested well", "should be fine", "just
  a formality", "quick sanity check", everyone agrees. NOT a postmortem of a real past
  incident, and NOT a substitute for code, security, legal or financial review — it
  complements them. For harm caused by the plan *succeeding*, use dystopia;
  for building a capability that could be turned to destruction, use oppenheimer.
user-invocable: true
argument-hint: "[plan, change, decision or launch to premortem]"
---

# Premortem

It already failed. Work backward from the failure to find the causes while there's still time to fix them.

Why it works: imagining an outcome as certain (prospective hindsight) makes people generate more reasons for it, about 30% more in Mitchell, Russo & Pennington (1989). Premortems cut overconfidence about twice as much as pro/con lists (Veinott, Klein & Wiggins 2010) and found more and better risks than brainstorming, including black swans (Gallop & Bischoff 2016). The evidence is about *more and more candid* causes, not about predicting which one will happen. Generate in the frame; judge outside it.

## First: size it

Decide the depth before anything else.

- **Quick pass** — small, reversible, local (a rename, a config tweak, a minor copy change). A TL;DR line with the verdict, then at most five causes, one line each, still past tense, the most specific first, each with its fix or check. Under 150 words.
- **Full pass** — costly, one-way, many people, money, data, reputation. Everything below.

Unsure? Quick pass, and say what would make it worth the full one.

## Hold the frame

- **It failed. Past tense, certain.** "Users churned," "we rolled it back," "the data was corrupted" — never "this might fail" or "there's a risk that." The shift from *could* to *did* is the mechanism.
- **No hedging while you generate.** Banned until you rank: *might, could, would, may, probably, likely, possibly, in theory, hopefully, should be fine, to be safe.*
- **Stay in character.** Don't narrate the exercise or the method, and don't reassure ("of course this probably won't happen"). Write the failure.
- **Say the quiet part.** Failure is assumed, so naming a weakness — in the plan, the premise, the team, the person asking — isn't disloyalty. It's the job.
- **Honest at the boundary.** Report the results as real risks and concrete fixes. Never imply an incident happened, never soften a finding to be reassuring.

## The pass

1. **Name it.** One line: what's being committed to, and what success had to look like — the thing under the knife and the bar it had to clear.
2. **Jump to the failure.** A concrete moment ("three weeks after launch", "at the first quarterly review") and the failure as fact, specific and measurable: *"signups fell 40% the first week and never recovered; we reverted on day 19."* Decide what "failed" means here — and include the quiet failure: it shipped, nothing broke, and nobody used it.
3. **Work backward from every vantage.** First read what exists — the plan, the diff, the doc, the numbers — so causes come from this thing, not from a generic list. Then walk the lenses below, each as a *separate* observer, and write why it failed. Aim for 8–12, unfiltered. Include causes that implicate the premise (we were wrong about what people wanted) and the people (the one person who understood it left). If the user can see the plan but hasn't spoken yet, ask for their own two or three worries *before* showing yours — once they read your list, it anchors them.
4. **Make each cause real.** For every cause:
   - **Mechanism** — how it actually played out, step by step.
   - **False assumption** — what we believed going in that turned out untrue.
   - **Earliest signal** — the first observable thing as it started going wrong.
   - **Grounded or assumed** — point to the line, section or fact it comes from, or mark it as an assumption.

   Specificity test: at least half the causes would not make sense for a different plan. A cause that fits any project ("communication broke down", "scope crept") needs its specific mechanism here or it goes.
5. **Now rank — out of the frame.** You just imagined every cause vividly, and imagining an outcome inflates how likely it feels (Koehler 1991). So score likelihood from evidence, not vividness: has this happened before, here or to comparable efforts (the outside view)? Score each — likelihood (H/M/L, with the precedent) · impact (H/M/L) · detection (would we see the earliest signal in time? yes/late/no). Pull the few that are likely, damaging, or invisible until too late. Mark any *elephant* — the cause everyone already suspected and nobody said.
6. **Change the plan now.** For each top cause, one of: remove it (redesign, cut scope), catch it (a test, check, or monitor on the earliest signal), contain it (flag, staged rollout, backup, reversible step), or accept it explicitly. Turn the earliest signals into **tripwires**: the signal, the threshold, and the action already agreed — "if refunds pass 3% in week one, we pause the rollout" — decided now, while no one is invested in continuing. Offer to write the tripwires down where they outlive the conversation — the plan itself, an issue, a checklist in the repo — with when to check them; a tripwire nobody checks is decoration.
7. **Premortem the fix.** Confidence rebounds once fixes exist (Veinott et al. saw it rise most in the premortem group after solutions). Run one short round on the revised plan: *it failed anyway — why?* Then give the verdict: **go**, **go with these changes**, or **not yet** (and what would change that).

## Lenses

Use the universal lenses on everything, then the pack that fits the domain. Each is a distinct observer — that independence is what stops you anchoring on the first idea.

- **Universal:** the premise (wrong problem, wrong customer, wrong bet) · the people who had to do, use, approve or pay for it · the process and handoffs · the tools and dependencies · the outside world (competitors, regulation, the market, the weather) · time (it took twice as long; the window closed) · money and incentives (someone was rewarded for the wrong thing) · the assumption nobody checked · what we didn't scope · worked-in-the-test, broke-in-reality · the edge / empty / degenerate case · the silent failure (wrong result, no alarm) · whoever inherits it in six months.
- **Software / systems:** load and scale · concurrency and races · the rollback and the migration · a contract or API that drifted · security and abuse · the observability gap · the 3am on-call · data loss or corruption · backward compatibility.
- **Product / UX:** the confused first-timer · the power user · accessibility (keyboard, screen reader, contrast, cognition) · small screen and slow network · empty, loading and error states · trust and abandonment · overflow and i18n · the user who does it "wrong."
- **Business / launch / marketing:** the buyer vs. the user · pricing and the unit economics · the channel that didn't deliver · the message that landed differently · the competitor's response · legal, compliance, contracts.
- **Operations / events / projects:** the critical path · the single point of failure (a person, a supplier, a venue) · capacity and lead times · the handover · the backup plan nobody rehearsed.
- **Personal or one-off decisions (a move, a hire, a job):** the reason you really want it · who else it lands on · the cost you discounted · what you can't undo · what you'd tell a friend in your place.
- **Anything else:** name the people or forces whose disappointment *is* the failure, and make each a lens.

## Red flags — you've left the frame

- You wrote "could," "might," or "would" while generating. → State it as done.
- You ordered causes by likelihood while generating. → Finish surfacing first.
- A cause is vague ("quality issues", "bad timing"). → Name the mechanism.
- You stopped at three or four. → Keep going; the useful ones surface late.
- You skipped one because "that won't happen." → That's the one. Write it.
- You ranked a cause high because the story was vivid. → Find the precedent or rank it lower.
- Every fix is "be careful" or "monitor closely." → Name the test, the threshold, the owner.
- The causes would fit any project. → Go back to the plan and find where this one breaks.

## Rationalizations

| Excuse | Reality |
|--------|---------|
| "I'll just list the risks." | A risk list is conditional and polite. The certain past tense is what makes people name the uncomfortable causes. Hold the frame. |
| "Ranking as I go is efficient." | Ranking while generating filters out the uncomfortable causes before they're written. Generate first, rank last. |
| "It's a quick check." | "Quick check" confidence is when failures hide. Scale the depth down, never the frame. |
| "I shouldn't alarm them." | Balance belongs to the decision, not the premortem. Here the job is the failure case, fully — then an honest verdict. |
| "The fixes cover it now." | That is the confidence rebound. Premortem the fix. |
| "I can't see the change / the plan isn't written." | Premortem the plan you were told. Name the assumptions you had to make and flag the gap. |

## Running it with people

When the user will run this with a team, give them Klein's script: brief the plan · announce "it's a year from now, it failed — badly" · **two to three minutes of silent, individual writing** (independent lists are the point; discussion first lets the first speaker and the most senior person anchor everyone) · round robin, one cause each, leader last so rank doesn't chill dissent, until every list is empty · merge, rank, change the plan · revisit the list at each milestone. Have people write before they see any AI-generated list.

## Scale to the stakes

The depth is set by *First: size it* above. Brevity is in the *presentation* (see Output) — never in the frame or the generation. For the highest stakes, go wide: dispatch parallel agents, one lens each, so causes are generated with no anchoring (use superpowers:dispatching-parallel-agents when it's installed), then merge, deduplicate and rank yourself.

## Output

Generate fully, show tight: the pass happens in your head and in the full cause list, but the reader gets only what changes the decision. No preamble, no restating the plan, no narrating the method, no closing summary. Every line names a specific thing from this plan — a step, a number, a person, a file — never a category. Numbers where the plan has numbers.

```
**TL;DR:** <verdict> — <the one or two causes that matter, a clause each>; <the change that matters most>.

**It failed:** <one sentence: the moment and the failure, as fact>.

**Top causes**
1. <cause, past tense, specific> — because <false assumption>. First sign: <signal>. <L/I/D, e.g. H·H·late — precedent>.
   → <remove / catch / contain / accept: the concrete change>
2. …  (3–5 in all, ranked)

**Also surfaced:** <the rest, a few words each, one line>
**Tripwires:** <signal> > <threshold> → <pre-agreed action>   (one line each)
**Verdict:** go / go with these changes / not yet — <residual risk, one sentence>
```

Full pass: under 450 words. Quick pass: the TL;DR line, then at most five one-line causes with their check — under 150 words, nothing else.

Hard limits: each top item is at most two sentences plus its → line. "Also surfaced" is one line, comma-separated, not bullets. The verdict is one sentence plus the residual risk — don't re-list the plan. No line before the TL;DR (don't announce the depth you chose), and at most one short closing line, only to offer writing the tripwires down.

$ARGUMENTS
