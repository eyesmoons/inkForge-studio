# Comet subagent progress — inkforge-collaborative-writing

Plan: docs/superpowers/plans/2026-08-31-inkforge-collaborative-writing.md
review_mode: standard | tdd_mode: tdd | build_mode: subagent-driven-development | isolation: current (no-git)

## Key interface facts (verified)

- `user_db.DB_PATH` — module-level path; `_connect()` reads it directly. ✅
- `user_db._db_instance` — module-level singleton (`Optional[UserDB]`, ~line 1900). ✅
- `user_db.get_db()` — PLAIN function returning the singleton (NOT a context manager). `UserDB` itself supports `with` (`__enter__`/`__exit__`).
- ⚠️ DB ACCESS PATTERN (Ruling): every `with get_db() as db:` block MUST call `db._connect()` inside it before use. `UserDB.__exit__` closes conn (sets it None); `_connect()` re-reads module-level `DB_PATH`, so this honors tests' monkeypatched temp DB. The plan's bare `with get_db() as db:` pattern is MISSING this — all later DB-module tasks (ai_labeler, article_history) must include the `_connect()` call. Cost if wrong: tests silently hit real users.db / AttributeError on None conn.

## Rulings

- Ruling (T3): plan's `with get_db() as db:` pattern → use `with get_db() as db: db._connect()` — `UserDB.__exit__` closes conn, `_connect()` re-reads monkeypatched DB_PATH. Cost if wrong: tests hit real DB, isolation broken.

## Completed

### Task 1 — 4 张数据表 — COMPLETE
- Model: sonnet | DONE_WITH_CONCERNS (premailer env) | Risk: schema → reviewed, Spec ✅ Quality ✅
- TDD: 4 failed → 4 passed. Checkoff: OpenSpec 1.1, 1.2. Deferred minor: premailer not in requirements.txt.

### Task 2 — pytest 基础设施 — COMPLETE
- Model: sonnet | DONE | No risk signals → no per-task review.
- TDD: no config → 4 passed (configfile: pytest.ini).

### Task 3 — version_manager — COMPLETE
- Model: fable | DONE | No risk signals → no per-task review.
- TDD: ImportError → 6 passed. Files: modules/version_manager.py, tests/test_version_manager.py
- Checkoff: OpenSpec 1.3.

### Task 13 — history article frontend — COMPLETE
- Model: fable | DONE_WITH_CONCERNS (resolved) | non-risk → no per-task review, straight to checkoff.
- TDD: 5 failed → 5 passed. Added 4 history routes + workbench.html saveToHistory() wiring + collaborative.js module + common.css.
- GAP CLOSED: brief assumed `POST /api/collaborative/<id>/save-article` existed (Task 11) — it did NOT (workbench only flipped a phase flag, nothing persisted). save→history chain was dead. Ruled it into T13 scope (broken handoff, not new scope): added the missing route (line ~3822) + rewired saveToHistory() to call it. Verified end-to-end: article persisted w/ mandatory AI label, appears in history list. 401/400/404 negatives correct.
- Checkoff: OpenSpec 10.1, 10.2, 10.3, 10.4. Full suite 49/49 green.

Ruling (T13): the missing `save-article` route is a Task 11 broken handoff (plan line 930 lists it as required; T15 e2e assumes it) — ruled INTO T13 closure, not new scope. Cost if wrong: history feature stays dead, T15 e2e fails.

### Task 14 — platform-specific feature removal — COMPLETE
- Model: fable | DONE_WITH_CONCERNS (resolved) | RISK task (deletions + cross-module) → per-task review APPROVED below.
- Phase 1: deleted 4 platform modules + cover_maker frontend + all imports/routes/push-logic. Cleaned ~25 branding instances + 8 ai_writer.py prompts (coordinator-fixed). Deleted dead account-mgmt system + 6 user_db account fns + dropped wechat_media_id/wechat_draft_id columns. 52/52 green.
- Phase 2 (scope expansion): deleted 10 platform pages (topics/write/dashboard/rewrite/import/skill/schedule/config/profile/viral) + routes + old index.html; cleaned branding from generic tools (hotrank/history/today_in_history/material_library/common.js); removed all platform nav links; fixed / redirect → /collaborative.
- **Result: 0 platform markers (微信/公众号/weixin/api.weixin) in active source** (831 remain, all in dist/ build artifacts). 52/52 tests green.
- Checkoff: OpenSpec 11.1, 11.2, 11.3, 11.4, 11.5, 11.6. Deviation: domains_config.json RESTORED (generic topic-research data, not platform-specific) — honors user's real intent; test renamed to test_domains_config_preserved.
- Review: task-14-review.md (per-task review APPROVED — see below).
- Carry (non-blocking): dead account/publish code blocks remain in common.js + history.html (call deleted /api/accounts, /api/publish); generic code, not platform branding — outside constraint. common.js is high-risk shared; flag for later, not Task 14.

Ruling (T14 scope expansion): leftover platform pages + nav links violate the explicit repeated constraint — ruled INTO T14 scope (same mandate, agent stopped early). Verified irreversible claims: index.html was orphan (deleted ok); / redirect fixed to /collaborative (not deleted dashboard).

### Task 15 — end-to-end integration tests — COMPLETE
- Model: fable | DONE | RISK task (cross-module) → per-task review APPROVED below.
- TDD: 6 new e2e tests, all pass. Full suite 58/58 green (was 52, +6). No regressions.
- Tests: full workflow (12.1), version lifecycle (12.2), AI label compliance block+admin (12.3), history mgmt (12.5), platform removal (12.5). Genuine assertions (status codes, label presence, version ordering, diff content, rollback restores content, 400/404 negatives).
- Checkoff: OpenSpec 12.1, 12.2, 12.3, 12.4, 12.5.

## All 15 build tasks COMPLETE

OpenSpec tasks.md fully checked. 58/58 tests green. 0 platform markers in active source.

Next: final lightweight code review (review_mode: standard) → build exit conditions → comet guard build --apply.
