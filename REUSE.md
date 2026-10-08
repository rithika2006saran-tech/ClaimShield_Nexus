# Reuse statement

**Reference concepts only. No source code, schemas, models, notebooks, datasets or dependencies were copied or adapted from any pre-existing repository.**

The project brief supplied a GitHub integration blueprint listing public repositories as *inspiration*. They were used solely as conceptual references (e.g. "a provider-month panel", "hybrid BM25 + vector retrieval fused with RRF", "evidence-grounded copilot"). Everything in this repository - data generator, rules, feature engineering, scoring pipeline, graph and temporal logic, case/priority policy, Second Brain, Brief/Copilot, API and UI - was written from scratch for this project.

Third-party *libraries* used as dependencies (not copied into the tree) are listed in `THIRD_PARTY_NOTICES.md`. The shadcn/ui-style primitives in `frontend/src/components/ui` are small hand-written components following the public shadcn/ui pattern (Radix + class-variance-authority + tailwind-merge); no files were pasted from the shadcn registry.

If any copied code is discovered later it should be removed and reported.
