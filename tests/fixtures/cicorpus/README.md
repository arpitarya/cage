# `cicorpus` — the CI graphify corpus

A **new named corpus** (the frozen-corpus decision: never mutate an existing one), owned
by CI and nothing else.

- Purpose: give `graphify update/query` something real and tiny to build a graph over, so
  the `present` leg of `python-package.yml` exercises the interception path end to end.
- Deliberately **not** cage-lab's `tinyshop`, which stays lab-only.
- Deliberately trivial: CI asserts capture *mechanics*, never graph quality.
