---
name: dystopia
description: >
  Use before building, launching or scaling something that will reach many people or last
  a long time — a product, feature, algorithm, AI system, policy, pricing or incentive
  scheme, platform rule, org change — to find the harm it does by *succeeding*: second-
  and third-order consequences, misuse, people outside the room, metrics that got gamed,
  what it does at scale and over years. Also use when the user says "dystopia",
  "black mirror this", "consequence scanning", "harms modeling", "unintended
  consequences", "how could this be abused", "what if this works too well", "second-order
  effects", or "who gets hurt". Complements premortem, which asks why the plan failed;
  this asks what went wrong because it didn't. For a
  capability that can't be un-invented once it exists, use oppenheimer. NOT a security threat model, legal review
  or ethics sign-off — it feeds them.
user-invocable: true
argument-hint: "[product, feature, policy or system to imagine at full success]"
---

# Dystopia

It worked exactly as intended. It was adopted, it hit every target, it ran for years at scale. For someone, the world it made is a nightmare. Who, and how? Find out while the design can still change.

That is the literary sense of the word: a dystopia is usually someone's utopia, working as designed, seen from the side it lands on. So the question is never only "is it bad?" but *who wins, who pays, and by whose values is it worse.*

A premortem finds why the plan missed its goal. This finds the cost of the goal being met. Teams are blind here for a structural reason: success is what everyone is rewarded for, so nobody inside the room imagines it as the cause. The method combines prospective hindsight (state the future as fact, then explain it — the frame that makes people generate more and more candid reasons) with established foresight and harm tools: the futures wheel's orders of consequence (Glenn 1972), Doteveryone's consequence scanning, harms modeling across non-users (Microsoft, adapted by C2PA), and the Ethical OS risk zones (IFTF and Omidyar Network 2018).

## Hold the frame

- **It succeeded. Past tense, certain.** Not "this could be misused" — "by year two, the feature was how stalkers found people." Success isn't in question; its consequences are.
- **Winners and losers, both named.** For each consequence say who it served as well as who it hurt. A harm with no beneficiary is usually one nobody will fix, and a harm someone profits from is one that will grow.
- **No hedging while you generate.** The same banned words as a premortem: *might, could, would, may, probably, possibly, hopefully, in theory.*
- **Concrete people, concrete days.** Name who it happened to and what their Tuesday looked like. "Society was harmed" is not a consequence.
- **Not doom, not a sermon.** No moralizing, no verdicts on the people building it. The job is to see the mechanism clearly so it can be designed out.
- **Honest at the boundary.** Report real, plausible consequences and concrete changes. Never present the scenario as a prediction or as something that happened.

## The pass

1. **Name it and the win.** One line: what it is, and what success meant in numbers — users, usage, revenue, adoption, the metric the team will be judged on.
2. **Fast-forward.** Pick a horizon long enough for behaviour to adapt — usually two to five years — and state the success as fact at scale: *"Forty million people used it daily; it became the default way to …"* Then a scene of two or three sentences: one ordinary person, one moment, in the world where it won. The scene surfaces what lists don't; keep it short enough that it does only that.
3. **Ripple outward.** Read whatever describes the thing — the spec, the code, the pitch — and anchor consequences in what it actually does. From the success, trace consequences in orders: first (what it directly does), second (what people and systems do in response), third (what that changes — norms, markets, institutions, the environment). Do this from every lens below. Aim for 8–12, unfiltered, and keep at least half of them second-order or later; first-order effects are the ones the team already saw.
4. **Make each consequence real.** For every one:
   - **Chain** — success → the mechanism → the harm, each link stated.
   - **Who** — the people it lands on, especially those who never chose the product.
   - **Earliest signal** — the first measurable thing that would show it starting.
5. **Now judge — out of the frame.** A vivid scene makes its harms feel likelier than they are (imagining an outcome inflates its perceived probability, Koehler 1991). Ground likelihood in precedent: has something comparable done this — a similar product, policy, or incentive? Score each — likelihood (with the precedent) · severity · breadth (how many people) · reversibility (can the harmed recover, can we undo it). Severe and irreversible outranks frequent and mild.
6. **Triage — act, influence, monitor** (from consequence scanning). **Act:** in our control — change the design, default, incentive or access. **Influence:** partly ours — partners, policy, the ecosystem, documentation. **Monitor:** not addressable now — name the signal and the threshold that would trigger action, and who watches it.
7. **Run it again on the changed design**, briefly: it succeeded with these changes in — what went wrong now? Then the verdict: **build as planned**, **build with these changes**, or **rethink** (and the question that must be answered first).

## Lenses

Seven core lenses — each a separate observer. Go deep on the ones that bite, not shallow on all.

- **The bad actor:** a stalker, scammer, harasser, troll farm, cheating competitor or abusive partner uses it exactly as designed. What did they get?
- **The non-user:** the people affected who never signed up — neighbours, bystanders, the person in the photo, the worker displaced, the community the data describes.
- **The vulnerable user:** a child, someone in crisis, someone with a disability, low literacy, no money, or no choice but to use it.
- **The metric and the incentive:** the target became the goal (Goodhart's law), and someone got paid or promoted for the harm. What did people and the system do to hit the number instead of the purpose?
- **Scale and dependence:** what was harmless for a thousand users and wasn't for a hundred million? What became a monoculture, a gatekeeper, a single point of failure — and what happened when it changed its terms or shut down?
- **Power and trust:** who gained control over whom, and what can now be watched, scored, denied, or faked?
- **Fairness:** who got systematically less — worse results, higher prices, more scrutiny — and did they have any way to know or appeal?

When the domain calls for it, add: **attention and wellbeing** (sleep, focus, relationships, the habit loop) · **the environment and the commons** (energy, materials, shared resources) · **the norm** (what everyone came to expect once it was normal). A pricing scheme leans on metric, fairness, dependence; a social feature on bad actor, non-user, attention; an internal tool on metric, power, dependence.

## Red flags — you've left the frame

- You wrote "could be misused." → Name who misused it, how, and what they got.
- Everything is first-order. → Ask "and then what did people do?" twice more.
- The harm has no named person. → Put someone in the scene.
- You're arguing it won't happen. → That's the judging step. Finish generating.
- You moralized. → Delete the sermon; keep the mechanism.
- The only mitigation is "add a policy" or "educate users." → Change a default, a limit, an incentive, an access rule — something the system does.

## Rationalizations

| Excuse | Reality |
|--------|---------|
| "We're too small for this to matter." | The consequences of success arrive at the scale of success. Design it while it's small enough to change. |
| "Users can choose not to use it." | Non-users and the people with no choice carry most of the harm. Write their scene. |
| "That's misuse, not our product." | If the design made the misuse easy, it's the design. |
| "This is speculative." | All of it is, until it isn't. Generate freely, then rank by precedent. |
| "Ethics is someone else's review." | This finds the cases for that review. A review can only weigh what someone named. |

## With a team

Same discipline as a premortem: everyone writes silently first, then a round robin, so the first idea and the senior voice don't anchor the room. Run it once scope is defined — earlier yields only generic harms — and again before scaling. Keep the monitor list alive: it's only useful if someone checks the signals.

## Scale to the stakes

A small internal change, or something few people will touch, gets a quick pass: the three lenses that fit, a TL;DR line with the verdict, one line per consequence, under 150 words. Anything that touches many people, sensitive data, money, children, or decisions about people gets the full pass. For the highest stakes, dispatch parallel agents, one lens each (superpowers:dispatching-parallel-agents when installed), then merge and judge yourself.

## Output

Generate fully, show tight: the pass happens in your head and in the full cause list, but the reader gets only what changes the decision. No preamble, no restating the plan, no narrating the method, no closing summary. Every line names a specific thing from this plan — a step, a number, a person, a file — never a category. Numbers where the plan has numbers.

```
**TL;DR:** <verdict> — <who pays most, and how, in one clause>; <the design change that matters most>.

**Where it won:** <horizon and the success, as fact, one sentence>. <The scene: one person, one moment, two or three sentences.>

**Top consequences**
1. <success → mechanism → harm, one chain> — pays: <who>; gains: <who>. First sign: <signal>. <likelihood (precedent) · severity · breadth · reversibility>.
   → <act / influence / monitor: the concrete change>
2. …  (3–5 in all, ranked, at least two second-order or later)

**Also surfaced:** <the rest, a few words each, one line>
**Monitor:** <signal> > <threshold> → <action>, owner   (one line each)
**Verdict:** build as planned / build with these changes / rethink — <residual risk, one sentence>
```

Full pass: under 500 words. Quick pass: the TL;DR line, then at most five one-line consequences with their change — under 150 words.

Hard limits: each top item is at most two sentences plus its → line. "Also surfaced" is one line, comma-separated, not bullets. The verdict is one sentence plus the residual risk — don't re-list the plan. No line before the TL;DR (don't announce the depth you chose), and at most one short closing line, only to offer writing the monitor list down.

$ARGUMENTS
