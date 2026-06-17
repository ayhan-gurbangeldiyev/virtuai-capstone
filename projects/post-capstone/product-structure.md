# Product Structure — Cansu Operator Surfaces

Locked 2026-06-04. This document defines the three-layer operator-facing
product structure and the principles that bind it. Any implementation
decision that conflicts with what's written here requires an explicit
override from Berkay, not a silent design call.

---

## The Three Layers

| Layer | Name | Question answered | Build order |
|---|---|---|---|
| 1 | **Home** | What did Cansu decide today? | 1st (in progress) |
| 2 | **Choices** | How does Cansu decide in general? | 2nd |
| 3 | **Lifecycle** | How was this specific piece made? | 3rd |

### Layer 1 — Home (`/control`)

**Job:** the daily editorial front page. One decision pair, in Cansu's
voice, externally checkable.

**Mental model:** a newspaper's front page. Lead story, with the
reasoning that makes it the lead. System status is a footer, not the
headline.

**Trust mechanism:** the operator opens the two named items, reads
both, independently agrees with Cansu's distinction. Trust is earned,
not transferred.

### Layer 2 — Choices

**Job:** the editorial archive. Many decision pairs across the recent
window, each one accepted-vs-refused with the reasoning that separates
them.

**Mental model:** a newspaper's archive section. Proves the lead on
Home is consistent with the editorial pattern, not a cherry-pick.

**Trust mechanism:** the operator scans dozens of decision pairs and
forms an independent view of whether Cansu's judgment is coherent
across time. Verifies that the principle behind Home generalizes.

### Layer 3 — Lifecycle

**Job:** the per-piece microscope. For any single published item, show
its source, why it was deemed coverable, what was written, what visual
was used, what stopped or didn't stop its publication, and where it
landed.

**Mental model:** a footnote view. Reached by clicking on an item from
Home or Choices. Not a place anyone goes first.

**Trust mechanism:** does not start trust. Lets an operator who already
trusts Cansu's judgment satisfy curiosity about craft.

---

## Why this order

The build sequence is Home → Choices → Lifecycle, not Home → Lifecycle
→ Choices. The reasoning:

A skeptical operator who reads Home's hero —
*"Cansu covered NVIDIA but skipped Apple because…"* —
does not ask "how was the NVIDIA draft generated?" They ask "what else
did she reject?" That means the natural second click is **Choices**,
not Lifecycle.

Choices is the verification layer for Home. Lifecycle is an explanation
layer for execution. Verification must come before explanation, because
without verification the explanation has nothing to back up.

---

## Bound Principles

### Principle 1 — Home must never ask the operator to trust Cansu

Home shows evidence that allows the operator to reach the same
conclusion Cansu reached. It does not show Cansu's self-description and
ask the operator to believe it.

The test for any element on any of the three layers:

> *Can the operator verify this claim by looking at the world, not at
> the system's self-description?*

If yes, the element is **editorial** and belongs on the page.
If no, the element is **character** and does not belong on the page.

### Principle 2 — The Home hero is a decision pair, not a count

Canonical form:

> *"Cansu covered [published item] but skipped [refused item] because
> [externally checkable reason about the items themselves, not about
> Cansu]."*

Not the count of stories reviewed. Not the percentage accepted. Not a
list of refused categories. A specific pair with a specific reason.

### Principle 3 — Two levels of evidence

**Level 3 (the floor, achievable daily): the same-category comparison.**
One published item paired with one refused item from the same category
or domain, named together with the reasoning that separates them. This
is the daily trust mechanism. Externally checkable against the open
world.

**Level 4 (the ceiling, occasional): the self-override with external
referents.** A statement that today's decision departs from her typical
pattern, *only allowed when the override clause itself contains an
externally checkable fact*. "She made an exception today" is not
allowed. "She made an exception today because Anthropic's funding
changes the competitive frontier with OpenAI" is allowed, because the
operator can independently evaluate the strategic implication.

When no qualifying Level 4 moment exists, the screen shows Level 3 and
does not invent a Level 4. Better to be quieter than to manufacture
narrative.

### Principle 4 — Personality is brand, not trust

Sentences that describe Cansu's character ("she'd rather stay quiet
than publish something that doesn't sound like her") are persuasive
but they are not evidence. They are brand work. Brand work is allowed
in marketing surfaces; it is not allowed on Home, Choices, or
Lifecycle.

A skeptical journalist is not convinced by Cansu's voice. They are
convinced by Cansu's choices. The three layers are designed for the
journalist.

### Principle 5 — Quiet days require evidence, not reassurance

A quiet day (zero published items) is the most operationally important
case for the trust mechanism, because it is the case most likely to be
misread as failure. On a quiet day, Home surfaces:

- the named item Cansu *most considered* and ultimately refused
- the externally checkable reason she refused it

The sentence form is identical to the productive-day hero except that
the published slot becomes "she didn't write today; the closest call
was [item]." The operator's verification path is the same: open the
item, read it, decide whether her reasoning holds.

### Principle 6 — System health supports the story; it does not become the story

Liveness checks (reconciler last run, cron last fire, Postiz reachable)
appear on Home as a small footer strip. They defend against false-GREEN
failure modes; they are not the page. If liveness fails, the hero gets
a small visual marker and the footer turns yellow or red. The hero
text itself does not change tone.

### Principle 7 — Internal system names never appear on operator surfaces

These words do not appear on Home, Choices, or Lifecycle:

- Persona Gate
- TrendScout
- Content Strategist
- Visual Director
- Compliance / LLM Judge
- Postiz
- Wiro / HeyGen / Nano Banana

The operator-facing vocabulary is **stories**, **decisions**, **choices**,
**published**, **skipped**, **considered**, **drafts**, **platforms**.
Internal stage names live in an engineer-mode debug toggle that the
operator never sees by default.

The rename of "Persona Gate Review" → "Choices" is the canonical
example of this principle. The product teaches the operator about
Cansu, not about the architecture.

### Principle 8 — Infrastructure fades; editorial dominates

Any element that pulls operator attention away from Cansu's editorial
decision back to the pipeline — throughput counts, queue depth, stage
names, processing rate, "the system evaluated N things today" — does
not belong on Home, regardless of whether the underlying data is
interesting.

The editorial story must be the strongest signal on the page at all
times. When any element competes with the hero for attention, that
element is doing infrastructure work and needs to be removed,
collapsed into the footer, or transformed into editorial framing.

Canonical example: the count `"Cansu bugün 520 hikâye değerlendirdi"`
was removed from Home v1 (2026-06-04) because it reads as system
throughput and competes with the hero. The locked spec calls for a
similar-looking line as a click-through to Choices, but only when
Choices exists — without a destination, the line has no editorial job
and only does pipeline work, so it does not ship.

Test for any future element: *would a non-technical operator describe
this as something Cansu did, or as something the system did?* If the
latter, it fails the principle.

---

## Home v1 — what ships

### Rules in

- The decision-pair hero (Level 3 floor; Level 4 ceiling when available)
- A single clickable release URL for the most recent published piece
- A one-line liveness strip in the footer
- A neutral-styled kill switch with current pause state
- A single clickable line: "Cansu also considered N other stories today →"
  that links to Choices when Choices exists; until then, it links nowhere
  and is rendered as muted text

### Rules out

- Cost burn charts
- Engagement counters per platform
- 7-day hero history strip
- Multi-account or multi-persona selectors
- Status gauges, queue depth visualizations, throughput charts
- Any element styled like a card, tile, KPI box, or dashboard panel
- Personality sentences not anchored in an external fact
- Self-override claims without an externally checkable referent inside
  the override clause

---

## Choices v1 — what it has to do when built

Not in active build. Scope-locked for the eventual second phase:

- Render the recent decision archive as a sequence of decision pairs
  using the same "covered / skipped / reason" structure as the Home
  hero
- Each pair externally verifiable (operator can open both items)
- The selection algorithm for what pairs to surface must be a rule
  the operator can understand and audit ("most operationally important
  contrast of the day," not a black box ranking)
- Top of Choices: the same hero currently on Home, with a visible
  "← back to today" link to Home

Choices is not a log view. It is a curated editorial archive.

---

## Lifecycle v1 — what it has to do when built

Not in active build. Scope-locked for the eventual third phase:

For any specific published item, six operator-facing sections, each
externally verifiable:

| Section | Operator question | Evidence |
|---|---|---|
| Source | Where did the story come from? | Link to the original trend signal |
| Why this story | Why did Cansu decide it was worth covering? | Plain-language gate rationale |
| What she said | What did the piece actually say? | The published text/content |
| Voice check | Does this sound like Cansu? | Reference to her typical voice patterns |
| Visual fit | Does the image actually show the story? | The image + brief reasoning |
| Where it landed | Did it publish and where? | The release URL + status |

Internal stage names (Content Strategist, Visual Director, Compliance)
do not appear on Lifecycle. They live in an engineer-mode debug toggle.

---

## The single shipping test for Home v1

A skeptical journalist opens Home, reads it for 15 seconds, opens the
two items named in the hero in new tabs, reads both, and concludes the
distinction is reasonable. They have not trusted Cansu — they have
agreed with her.

If the hero does not enable that exact sequence, it is not yet
finished. No other test, metric, or stakeholder review overrides this
one.

---

## Two kinds of trust the product is now explicitly separating

| Kind of trust | Surface that delivers it |
|---|---|
| Trust that the system is **operating** | Home (status footer + liveness) |
| Trust that the system's **judgment is sound** | Choices (decision archive) |
| Curiosity about **how a specific piece was made** | Lifecycle (drill-down) |

Before this lock, the product was conflating the first two. The
separation is the most important structural decision in the operator
product. Home does the operating-trust job and previews the
judgment-trust through one decision pair. Choices does the full
judgment-trust job. Lifecycle is downstream of both.
