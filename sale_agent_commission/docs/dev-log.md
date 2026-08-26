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

## Session 2.3

**Settlement model and state flow with buttons.**

Two new models: `sale.commission.settlement` (header) and
`sale.commission.settlement.line`. Sequence `sale.commission.settlement`
for the reference, four-state flow (draft/confirmed/paid/cancelled)
driven by action buttons with `_ensure_state` guarding transitions.
`sale.order` gets `settlement_line_ids` and a stored
`commission_settled` boolean.

No incidents during implementation. All manual test cases passed on
first install: sequence numbering, cross-agent line rejection, base
recompute on `commission_base` change, empty-settlement confirm
rejection, readonly lines and delete rejection once confirmed, live-
settlement duplicate rejection lifted after cancelling, date CHECK
constraint, `commission_settled` flipping back to `False` on
cancellation.

One thing to watch going into 2.4: the wizard will need to filter
candidate orders with `commission_settled = False`, not by absence of
`settlement_line_ids`, since a cancelled settlement leaves the line but
frees the order.

## Session 2.4

**Wizard (TransientModel) to generate settlements.**

New transient model `sale.commission.settlement.generate`, following the
Odoo 19 coding guideline of naming a wizard `<base_model>.<action>` and
avoiding the word "wizard" in `_name` (kept only as the directory name).
Filters candidate orders by agent, period, commission base and company,
always creates new settlements rather than merging into existing drafts.
`_candidate_domain` and `_candidate_orders` extracted as reusable
methods, with no business rule duplicated in the wizard: every
validation (agent consistency, currency, double settlement, period
bounds, state transitions) stays in the models from session 2.3. ADR-0003
documents this and three more decisions: `date_order` as the field that
decides an order's period, one settlement per agent per run with no
merging into existing drafts, and orders as a shortcut to prefill
filters rather than the literal set to settle.

Errors hit and fixed, in order:

- **Missing `<odoo>` root element in
  `sale_commission_settlement_security.xml`, and the file absent from
  the manifest's `data` list.** Left over from session 2.3: the record
  rules written back then had never actually been loaded, so the
  "own agent only" restriction was silently inactive since it was
  written. Not a session 2.4 bug, but found and fixed while wiring the
  wizard into the manifest.

- **Timezone mismatch between the wizard's period and `date_order`.**
  `date_order` is a Datetime stored in UTC; `date_from`/`date_to` are
  Dates read in the user's timezone. Comparing them directly shifts the
  period boundary by the user's UTC offset. Fixed with `_period_bounds`,
  which builds the interval in `self.env.user.tz` (via `zoneinfo`, not
  `pytz`) and converts to naive UTC before querying. The inverse
  conversion, `_local_date`, is needed later for `default_get` to
  propose a period from selected orders without the same off-by-one-day
  risk in reverse.

- **Wrong binding target, found by testing where the Action menu
  actually renders, not by reading docs.** First version bound the
  wizard's `ir.actions.act_window` to `sale.commission.settlement`
  (`binding_model_id`), reasoning that it was "the model this wizard is
  about." In practice, action-menu bindings in Odoo 19 only surface in
  the gear/Actions menu when records of the bound model are selected in
  a list — never in the top window-menu gear icon, which only offers
  import/export. That made the wizard reachable only by selecting
  settlements, which it then completely ignored, defeating the purpose
  of a selection-driven menu. Rebound to `sale.order`: selecting orders
  now prefills agents/company/period via `default_get` reading
  `active_ids`, without restricting the settled set to exactly what was
  selected (documented as Decision 4 in ADR-0003, precisely to avoid a
  silent partial settlement when a user selects 3 of an agent's 8
  pending orders).

- **`ParseError` on `<field name="groups_id" eval="[(4, ref(...))]"/>`
  inside the `ir.actions.act_window` record.** Odoo 19 renamed
  `groups_id` to `group_ids` on `ir.actions.act_window`,
  `ir.actions.server`, `ir.actions.report`, `ir.ui.view` and
  `ir.ui.menu` — one of several large breaking renames in this version
  (also `res.groups.category_id` → `privilege_id.category_id`,
  `res.groups.users` → `user_ids`). Most search results and older
  tutorials still show `groups_id` for these models, which made this
  one non-obvious to catch without hitting the ParseError directly.
  Fixed field name, and also switched the eval tuple from `(4, ref(...))`
  to `Command.link(ref(...))` for consistency with the Python side
  (`Command` is available inside an `eval` in a data file, same as
  `ref`). Note the `<menuitem groups="...">` and `<field groups="...">`
  *attribute* usage elsewhere is unaffected — the parser translates that
  attribute to the right underlying field regardless of version, so
  only explicit `<field name="groups_id">` records needed changing.

- **Restricting `group_ids` on the action surfaced a real gap**: without
  it, every salesperson would see "Generate Commission Settlements" in
  the order list's Action menu (since everyone can see orders), and it
  would fail for them at the ACL level on the transient model
  (`sales_team.group_sale_manager`-only in `ir.model.access.csv`). Easy
  to miss when testing only as admin — worth testing this kind of
  binding as a non-admin user before considering it done.

Mid-session decision: moved the wizard's `ir.actions.act_window` record
out of `views/sale_commission_settlement_views.xml` (where it had been
pasted alongside the settlement's own views, a copy-paste-adjacent
mistake similar in spirit to 2.2's misplaced `model` field) into
`wizard/sale_commission_settlement_generate_views.xml`, keeping the
transient and everything about it — model, views, action, menu — in one
file per the wizard/ directory convention.

One thing to watch going into 2.6: the scheduled action will call
`_candidate_domain` and `_candidate_orders` directly, without a
`self.env.user.tz` to lean on for `_period_bounds` — a cron runs as a
specific user, but the period boundaries for an automated run may need
to be defined in the company's timezone instead, not whichever user's
`tz` happens to be set on the technical account executing the cron.

## Session 2.5

**QWeb PDF report for settlements.**

New `report/` folder with two files: `..._templates.xml` (QWeb) and
`..._reports.xml` (the `ir.actions.report`). Two templates, wrapper plus
document, so the body can be inherited on its own and each settlement
renders in its agent's language via `t-lang`.

The report is reachable from the Print menu through `binding_model_id`,
with no button in the form header and no group restriction: the record
rule from 2.3 already limits an agent to their own settlements.

Mid-session decision, documented as ADR-0004: printable in every state
with a warning banner in draft and cancelled, and stored as an
attachment only in state `paid` (`attachment` expression returning a
falsy value elsewhere, plus `attachment_use`). Freezing at `confirmed`
was rejected because `attachment_use` returns the stored bytes forever,
so the archived copy would keep saying "Confirmed" after payment.

Verified by hand: exactly one `ir_attachment` row appears, and only on
the first print after the settlement is paid. Changing the company
document layout afterwards changes a draft printout but not the paid
one, which is the whole point of the decision.

Notes for next time:

- Without wkhtmltopdf on the PATH, Odoo falls back to HTML instead of
  failing. Silent symptom, easy to misread as a broken template.

- `attachment` and `attachment_use` are edited on the `ir.actions.report`
  form, not on the generic `ir.actions.actions` list under Technical >
  Actions, which only shows name and type. Reaching the right form took
  longer than it should have.

- `_render_qweb_pdf` in Odoo 19 is called on the `ir.actions.report`
  model, not on the action record, and takes the report reference as
  first argument: `env["ir.actions.report"]._render_qweb_pdf(report_name,
  res_ids)`. It returns a `(bytes, "pdf")` tuple. Most examples online
  still use the pre-16 form. The low-level
  `_render_qweb_pdf_prepare_streams` is two calls further down the chain.

- `t-lang` only switches the rendering language; it does not translate
  our own literals, because the module has no `i18n/` catalogue yet.
  Testing it properly needs the target language installed under
  Translations > Languages first. Left for 2.7.

- A value changed from the interface on a record the module owns (here
  `attachment_use`) is reverted by `-u`, since the field is not under
  `noupdate`.