# Dev log

Purpose of this file: capture concrete mistakes, fixes, and mid-session
decisions per session, so a new chat can pick up context that
`learning-path.md` (status) and the ADRs (accepted decisions) don't
carry on their own. Update at the end of each session.

## Session 2.1
Repository structure, AGPL-3 licence, README, empty installable module.
No incidents.

## Session 2.2

**Extend sale.order and res.users with commission logic.**

Fields added: `agent_id`, `commission_rate`, `commission_amount`,
`commission_amount_margin` on `sale.order`; `commission_agent`,
`commission_rate` on `res.users`. `commission_rate` on the order is
compute + store + readonly=False: proposed from the agent's default,
then frozen on the order (not a `related` field, so changing an
agent's rate later does not retroactively change past orders).

Errors hit and fixed, in order:

- **Root `__init__.py` empty.** `sale_agent_commission/__init__.py` had
  no `from . import models`, so the models package was never loaded.
  The `models/__init__.py` itself was correct
  (`from . import res_users` / `sale_order`), which made the symptom
  confusing: Odoo reported the field didn't exist on the model, which
  looked like a typo in the field name rather than a missing import at
  the package root.

- **`inherit_id` pointing to the wrong model's view.** A `record` for
  `sale.order`'s form view was pasted with `model` still set to
  `res.users` (copy-paste from the wrong block). Error message was
  misleading: "the field `inherit_id` does not exist on `res.users`",
  which is really a symptom of `model` being wrong, not of `inherit_id`.

- **List view external id.** Not guessed from memory; Odoo 19 list
  views use `<list>`, not `<tree>`, and ids can differ from older
  versions. Found via debug mode → Edit View: List on the actual
  Sales > Orders list, rather than assumed.

- **`write()` returning `True` on an invalid value (150 on a 0–100
  constraint).** The `models.Constraint` CHECK existed in the DB
  (confirmed with `\d sale_order` in psql) and the module had been
  updated with `-u`, but the write still silently "succeeded" in
  `oshell`. Cause: the ORM batches writes in cache and only flushes to
  PostgreSQL on certain triggers (search, commit, etc.); nothing had
  triggered a flush yet. Fix: call `env.flush_all()` explicitly to
  force the UPDATE and surface the `CheckViolation` /
  `IntegrityError`.

Mid-session decision: extended the commission base beyond the original
plan mid-session, after discussing ADR-0001 (this repo's own numbering,
independent of `odoo-lab`'s ADR-0001/0002). Commission is now computed
on both `amount_untaxed` (`commission_amount`) and on margin via the
`sale_margin` dependency (`commission_amount_margin`), same
`commission_rate` applied to both bases, kept side by side rather than
one replacing the other. Decided against generalizing `agent_id` to
multiple agents now (YAGNI — no concrete split-commission requirement
yet); documented as a known, higher-risk-to-change-later limitation in
the same ADR.

Numbering note: this repo (`sale_agent_commission`) has its own ADR
sequence, starting at ADR-0001, independent from the `odoo-lab`
repository's ADR-0001 (development environment) and ADR-0002 (licence
and repository layout).
