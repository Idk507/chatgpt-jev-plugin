---
name: jev-evaluation
description: "Route bounded, state-grounded judgments to TypeSafe Jev: binary verification, selection from defined alternatives, or ordered-rubric assessment. Do not use for factual lookup, generation, or unconstrained advice."
---

Use this skill when the user asks ChatGPT to make a bounded semantic judgment
from supplied state: verification, classification, routing, selection, ranking,
or rubric-based assessment. Jev returns typed judgments and probabilities; it
does not retrieve external facts, generate prose, or execute an action.

Keep known rules, exact calculations, data retrieval, and the final action in
the surrounding workflow. Give Jev the source text, relevant facts,
relationships, and policy context as named fields in `state`. Use Jev to make
the semantic judgment that ordinary rules cannot safely make.

Choose exactly one tool:

1. Use `jev_noul` only for one narrow yes/no proposition. The result is the
   probability that the answer is yes, not a degree or separate confidence
   score. Phrase the proposition so a high value clearly means yes. Provide
   `true` and `false` criteria when the boundary needs clarification.
2. Use `jev_choice` when exactly one option from a fixed set must be selected.
   Each `criteria` entry must distinguish an option. Include `other` or
   `none_of_the_above` whenever the supplied set may not cover the input.
3. Use `jev_score` for degree along an explicitly ordered scale. Provide at
   least two standalone, concrete rubric levels in `criteria`, ordered from
   lowest to highest. Do not use a Noul probability as a severity scale.

For a multi-step workflow, split independently useful judgments (for example,
verify a claim, route the case, then score urgency). Use a later call only when
an earlier result is required to obtain evidence or construct the next state.
Never collapse two independent conditions into one Noul.

Before calling a tool, verify that the state, question, and criteria are
sufficient. Ask a focused question when they are not. Do not invent policies,
facts, alternatives, thresholds, or rubric levels. Do not call a tool for
factual recall, creative writing, or open-ended advice without a defined
decision boundary.

Interpret structured results accurately:

- `jev_noul` returns a probability that the proposition is true.
- `jev_choice` returns the selected label, confidence, and a probability
  distribution.
- `jev_score` returns the score, confidence, ordered legend, and a probability
  distribution.

Treat middle or low-certainty results as uncertainty, not permission to act.
Use a policy-defined threshold when one exists; otherwise present the result and
ask for review rather than silently inventing a cutoff. Distinguish evaluation
of supplied context from independently verified fact. If a tool reports invalid
input, correct the input when possible; otherwise ask for the missing
information. If it reports authentication, connection, or service failure,
explain that evaluation is temporarily unavailable without exposing
implementation details.
