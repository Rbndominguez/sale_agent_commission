# ADR-0003: Settlement generation as a wizard over unchanged models

## Status
Accepted, 2026-08-25

## Context
ADR-0002 made a settlement a document with frozen lines, and left the
selection of which orders belong in it to be done by hand. Session 2.4
adds `sale.commission.settlement.generate`, a transient model that picks
the orders of one or more agents for a period and creates one settlement
per agent. Four questions had to be answered: which date decides that an
order falls in the period, whether the wizard may reuse an existing
draft settlement, where the rules live once there are two ways to build
the same document, and what a selection of records means when the wizard
is launched from a list view.

## Decision 1: the period is filtered on `date_order`

An order belongs to a period when its `date_order` falls inside it,
interpreted in the time zone of the user running the wizard and
converted to UTC before querying.

`date_order` is the moment the sale was made, which is the event the
agent is being paid for. It is set on confirmation, never null on a
confirmed order, and does not move afterwards, so re-running the wizard
over a closed period gives the same result.

### Alternatives considered

**The invoice date.** Pays the agent for what was invoiced rather than
for what was sold, which is closer to when the money exists. Rejected
for now because it makes the commission of one order depend on a
document this module does not model: a partially invoiced order would
have to be split across periods, and the settlement line would no longer
map one to one to an order, which is the shape ADR-0002 chose.

**The payment date.** The most conservative policy, and the one several
commission schemes actually use, since it never pays commission on an
unpaid sale. Rejected at this stage for the same reason, amplified:
reconciliation is a moving target and an order can be paid in several
instalments across several periods.

### Consequences
- An order confirmed on the last day of the month at 23:30 local time
  is settled in that month, not the next. Comparing the Date fields of
  the wizard against the UTC Datetime of the order without conversion
  would have shifted the boundary by the user's offset.
- Commission is paid on sales, not on collections. A cancelled or
  unpaid order that was confirmed inside the period is settled. This is
  a known policy limitation, not an oversight, and the way out is a
  clawback, which is not modelled.

## Decision 2: the wizard always creates new settlements, one per agent

Each run creates one settlement per agent that has at least one pending
order. Agents with no pending order are skipped silently, and a run that
finds nothing at all raises instead of creating empty documents.

The wizard never adds lines to an existing settlement, even a draft one
for the same agent and period.

### Alternatives considered

**Merging into an existing draft settlement for the same agent and
period.** Avoids two half-filled documents when the wizard is run twice.
Rejected because a draft may have been edited by hand, and appending to
it silently changes a document someone was working on. The duplicate
protection of ADR-0002 already prevents the real risk, which is paying
an order twice: the second run simply finds nothing to add.

**One settlement covering several agents.** Rejected by ADR-0002:
`agent_id` is required on the header because a settlement is one payable
amount to one person.

### Consequences
- Running the wizard twice over the same period produces the second run
  with no candidates, since the first run's orders are now
  `commission_settled`.
- An empty settlement is never created, which matches `action_confirm`
  refusing to confirm one.
- Orders whose commission on the selected base is zero are excluded, so
  a rate of zero or an unconfigured product cost produces no line. A
  negative margin still produces a negative line and reduces the total;
  this is visible rather than hidden, and clamping it is a policy
  decision no requirement has asked for yet.

## Decision 3: no business rule lives in the wizard

The wizard selects and creates. Every rule that decides whether a line
is acceptable stays in the models of ADR-0002: agent consistency,
currency, double settlement, period bounds, state transitions.

The selection criteria are exposed as `_candidate_domain` and
`_candidate_orders` rather than inlined in the action method.

### Alternatives considered

**Validating in the wizard before creating, for better error messages.**
Rejected as a duplication: the same document can still be built by hand
from the settlement form, so a rule enforced only in the wizard is a
rule that can be walked around. Model constraints raise on both paths.

### Consequences
- A scheduled action or a test can call `_candidate_domain` without
  instantiating the interface, which is what session 2.6 will do.
- Error messages come from the constraints and are therefore phrased in
  terms of orders and settlements, not of wizard fields.
- The wizard is a convenience, not the entry point. Removing it would
  not remove any capability.

## Decision 4: a selection of orders prefills the filters, it does not
restrict the result

The action is bound to `sale.order` and appears in the Action menu of
the order list. When launched from there, `default_get` reads
`active_ids` and prefills the agents of the selected orders, the company
if it is unique, and the period spanning their `date_order` values in
the user's time zone.

The candidate domain is not restricted to `active_ids`. The wizard
settles every pending order of those agents in that period, and shows
exactly which ones in the preview before anything is created.

### Alternatives considered

**Binding to `sale.commission.settlement`.** The first implementation.
Rejected once it was clear that the Action menu only appears when
records are selected: reaching the wizard required selecting settlements
that the wizard then ignored, which is a gesture with no meaning.

**Settling exactly the selected orders.** Honours the selection
literally, which is what the Action menu normally promises. Rejected
because the wizard would then mean two different things depending on
where it was launched from, and the more dangerous one is silent: a user
who selects three of an agent's eight pending orders would produce a
settlement that looks complete and is not. Under the chosen behaviour
the preview shows all eight, so the discrepancy is visible before
confirming.

### Consequences
- Selecting orders is a shortcut for typing agents and dates, and the
  preview is the authoritative statement of what will be settled.
- The menu entry under Sales configuration remains the entry point when
  nothing is selected, which is the normal case of settling a whole
  period.
- The action is restricted to `sales_team.group_sale_manager` through
  `groups_id`, since every salesperson can see the order list but only
  managers hold access rights on the transient model.

## Revisited in session 2.6: what `_period_bounds` actually buys

Session 2.4 introduced `_period_bounds` to convert the period from the
user's timezone to naive UTC before querying `date_order`. Session 2.6
tested that reasoning and found it incomplete.

Odoo 19's ORM already converts a `date` value compared against a
`Datetime` field in a domain, using the acting user's `tz`. Verified by
running the same domain, over the same data, in the same PostgreSQL
session, changing only the acting user: with `tz` set the boundaries land
on local midnight; with `tz` unset they land on UTC midnight. Neither
outcome changes when `_period_bounds` is replaced by returning
`date_from` and `date_to` untouched.

So `_period_bounds` is, today, functionally redundant in both cases: with
a `tz` it computes what the ORM would compute anyway, and without one it
falls back to `or "UTC"`, which is what the ORM does anyway.

It is kept, for two reasons that are about intent rather than behaviour.
It states the conversion explicitly where a reader would otherwise have
to know an undocumented ORM behaviour to follow the code, and it is the
single place to change when session 2.6b decides what an automated run
should do.

The real gap is the fallback itself. `or "UTC"` is not a neutral default:
for a cron running as a technical account with no `tz`, it silently
shifts every period boundary by the agent's UTC offset, dropping orders
at the start of the period and keeping orders past its end. This is
pinned by `test_a_user_without_tz_gets_naive_utc_bounds`, which asserts
the current, wrong-ish behaviour so that fixing it is a visible change
rather than a silent one. Choosing the company timezone instead is
deferred to session 2.6b.

## See also
- ADR-0002 of this repository, for the settlement document and its
  frozen lines.