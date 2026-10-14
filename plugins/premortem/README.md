# premortem

A [Claude Code](https://claude.com/claude-code) **plugin** with three ways to meet the future before you commit to it, each told as if it already happened:

- **premortem**: it failed. Why?
- **dystopia**: it worked exactly as intended, at scale, for years, and for someone the world it made is a nightmare. Who, and how?
- **oppenheimer**: it worked perfectly, then it was used. Who holds the capability now, and what did you owe that future?

All three run while there is still time to change the plan. Part of the [atelier](../../README.md) marketplace.

```bash
# In Claude Code:
/plugin marketplace add insanetic/atelier
/plugin install premortem@atelier
```

Then run `/premortem the billing migration`, `/premortem:dystopia the referral program` or `/premortem:oppenheimer releasing the model weights`, or just ask "what could go wrong with this?", "how could this be abused?" or "should we even build this?".

---

## When to use it

- Before anything costly or hard to reverse: a release, a merge, a migration, a launch, an architecture or refactor plan.
- When confidence is high and nobody has pushed back: "tested well", "should be fine", "just a sanity check".
- For any domain: software, product and UX, a launch or campaign, operations and events, a hire, a personal decision. The lenses are universal, with packs per domain.
- **Dystopia** before anything that will reach many people or run for years: a feature, an algorithm, a policy, a pricing or incentive scheme.
- **Oppenheimer** before building, releasing or open-sourcing a dual-use capability: a model, a tool, a dataset, a technique, a research result. Above all when the work is technically exciting and racing a competitor.
- Not for a postmortem of an incident that really happened, and not a replacement for code or security review. It runs next to them.

The premortem also fires on its own when you say "premortem", "what could go wrong", "poke holes", "red team this", "is this actually ready" and the like; dystopia on "black mirror this", "unintended consequences", "how could this be abused", "what if this works too well"; oppenheimer on "dual-use", "should we even build this", "what if this falls into the wrong hands", "if we don't, someone else will".

---

## How a pass runs

### Premortem

1. **Name it:** what is being committed to, and what success had to look like.
2. **Jump to the failure:** a concrete moment ("three weeks after launch") and the failure stated as fact, including the quiet one (it shipped and nobody used it).
3. **Work backward:** 8 to 12 causes, each from a separate lens (the premise, the people, the dependencies, time, incentives, the assumption nobody checked, then a domain pack), with no filtering for likelihood.
4. **Make each cause real:** the mechanism, the false assumption behind it, the earliest signal.
5. **Rank, out of the frame:** likelihood from precedent rather than from how vivid the story was, impact, and whether the earliest signal would be seen in time.
6. **Change the plan:** remove, catch, contain or accept each top cause, and turn the earliest signals into tripwires with a threshold and an action agreed now.
7. **Premortem the fix**, then a verdict: go, go with these changes, or not yet.

### Dystopia

1. **Name the win** in numbers.
2. **Fast-forward** two to five years to the success at scale, with a short scene of one ordinary person's day in it.
3. **Ripple outward:** first-, second- and third-order consequences from each lens (the bad actor, the non-user, the vulnerable user, the metric that got gamed, incentives, scale, dependence, power, trust, fairness, attention, the environment, the norm).
4. **Make each real:** the chain from success to harm, who it lands on, the earliest signal.
5. **Judge, out of the frame:** likelihood from precedent, severity, breadth, reversibility.
6. **Triage:** act (change the design now), influence (partners, policy), monitor (signal, threshold, owner).
7. **Run it again on the changed design**, then a verdict: build as planned, build with these changes, or rethink.

### Oppenheimer

1. **Name the capability, not the product:** what can now be done, by whom, at what cost, with the intended use stripped away.
2. **It got out:** released, copied, leaked, sold, acquired, requisitioned, stated as fact.
3. **The day it was used:** 6 to 10 uses from each lens (the worst holder, your own side under pressure, the insider, the successor, the leak, automation, the arms race, the target).
4. **The builder's account:** the sentence you'd have told yourself ("it's just a tool", "the race", "not my department").
5. **Judge, out of the frame:** uplift over what already exists, magnitude, reversibility, who holds it, precedent.
6. **Decide the lines now:** red lines, a narrower or gated capability, who else must review it and by when, and what you'd do if your own side crossed the line.
7. **Verdict:** build, build differently, build with controls, or don't build.

It names the builder's blind spots: "technically sweet" (Oppenheimer, 1954 hearing), "not my department" (Tom Lehrer's "Wernher von Braun", 1965), the race argument, the Collingridge dilemma (1980: easy to shape while young, hard once entrenched) and the Franck Report (June 1945), the dissent that existed and reached nobody with the power to act. The von Braun "wrong planet" line is quoted as attributed, since no primary source for it has been found. The skill reasons about purpose and consequence only and never gives operational detail for a harm.

### What you get back

Every answer opens with a **TL;DR**: the verdict, the cause or harm that matters most, and the change to make. Below it come only the 3 to 5 top items, each with its fix, then one line for everything else that surfaced, the tripwires and the verdict. The full generation still happens; the reader gets what changes the decision. The skills ask for under 450 words on a full pass (dystopia 500) and under 150 on a quick pass. In the evals, full passes came out at 560 to 750 words, about plain Claude's length, and quick passes at 180 to 230.

### Why it is built this way

All three generate in the past tense with no hedging, then judge outside that frame. Each step is there for a finding:

- **Generate as fact.** Imagining an outcome as certain makes people give more reasons for it, about 30% more in Mitchell, Russo & Pennington (1989). Premortems cut overconfidence about twice as much as pro/con lists (Veinott, Klein & Wiggins 2010), and found more and better risks than brainstorming, black swans included (Gallop & Bischoff 2016). The 30% counts reasons; it says nothing about accuracy, so the skill never claims it does.
- **Rank on evidence.** Imagining or explaining an outcome makes it feel likelier (Koehler 1991), so the ranking asks for a precedent instead of trusting the vivid story.
- **Premortem the fix.** In Veinott et al., confidence rose most in the premortem group once people had come up with solutions, so the skills run one more round on the changed plan.
- **Write alone first.** People write their lists alone before anyone shares, as in Klein's original procedure (HBR, 2007), because the first speaker or the most senior person otherwise anchors the room. The same goes for an AI's list, which is why the premortem asks for the user's worries before showing its own.
- **Borrowed tools.** Dystopia's lenses and triage come from foresight and responsible-tech practice: the futures wheel (Glenn 1972), Doteveryone's consequence scanning (act, influence, monitor), harms modeling across non-users (Microsoft, adapted by C2PA) and the Ethical OS risk zones (IFTF and Omidyar Network 2018).

The evidence base is real but thin: a handful of studies, small or student samples, one scenario each. The skills lean on the parts that replicate across this literature (independent generation, a concrete frame, judging after generating) rather than on any single number.

Depth follows the stakes. A small, reversible change gets a 30-second pass; a one-way decision gets the full one. For the highest stakes a skill sends parallel agents, one per lens, so no cause anchors the others (through [superpowers](https://github.com/obra/superpowers)' `dispatching-parallel-agents` skill when it is installed).

---

## Install

```bash
/plugin marketplace add insanetic/atelier     # from GitHub
/plugin install premortem@atelier
# or, from a local clone:
/plugin marketplace add ./path/to/atelier
```

For a whole project, run `claude plugin marketplace add insanetic/atelier --scope project` and `claude plugin install premortem@atelier --scope project` in its root, then commit `.claude/settings.json`.

Update later with `/plugin marketplace update atelier`.

**Other agents:** each skill is a plain `SKILL.md` with no tools, hooks or agents, so any agent that reads Agent Skills can use `skills/premortem/`, `skills/dystopia/` and `skills/oppenheimer/` as is.

---

## What's inside

| Component | Name | On invoke¹ | What it does |
|---|---|---|---|
| Skill | `/premortem` (`/premortem:premortem`) | ~2.5k | Holds the failure frame, walks the lenses, ranks on precedent, sets tripwires, gives a verdict |
| Skill | `/premortem:dystopia` | ~2.2k | Holds the success frame, traces consequences by order and lens, names who pays and who gains, triages act / influence / monitor |
| Skill | `/premortem:oppenheimer` | ~2.3k | Strips the capability of its intended use, assumes it got out, weighs uplift and reversibility, sets red lines |

¹ Estimated from word count; confirm with `claude plugin details premortem@atelier`. The always-on cost is about 250 tokens per skill description.

---

## Repository layout

```text
plugins/premortem/
├── .claude-plugin/plugin.json    # plugin manifest
├── skills/premortem/SKILL.md     # it failed: why
├── skills/dystopia/SKILL.md      # it succeeded: who paid
├── skills/oppenheimer/SKILL.md   # it exists: who holds it
└── evals/                        # one case per scenario, graded with and without the plugin
```

---

## Develop

```bash
claude plugin validate --strict .
claude --plugin-dir .                 # try it live
claude plugin eval . --runs 2 --judge-model sonnet   # the eval suite, with and without the plugin
```
