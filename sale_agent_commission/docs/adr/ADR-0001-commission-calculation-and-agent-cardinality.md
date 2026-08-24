# ADR-0001: Commission calculation base and single agent per order

## Status
Accepted, 2026-08-24

## Context
Session 2.2 added `agent_id`, `commission_rate` and `commission_amount` to
`sale.order`. Two decisions were made while writing that code and need to
be explicit before session 2.3 builds a settlement model on top of them,
because changing either one later means migrating data, not just editing
a compute method.

## Decision 1: commission is calculated on both `amount_untaxed` and margin

The commission is calculated on two independent bases, stored as two
separate fields on `sale.order`:

- `commission_amount`, `commission_rate` percent of `amount_untaxed`
  (the order subtotal before taxes).
- `commission_amount_margin`, the same `commission_rate` percent of
  `margin`, the field added by the `sale_margin` module (sale price
  minus cost).

Both fields are kept, not one replacing the other, so a deployment can
report or settle on whichever base fits its policy, and the two can be
compared side by side.

### Alternatives considered

**Margin only.** Pays the agent for actual profitability instead of
volume, which is the economically sound incentive: under a
subtotal-only scheme, an agent who negotiates a 40% discount earns the
same commission as one who sells at list price, as long as the final
subtotal is identical. Rejected as the sole basis because dropping
`amount_untaxed` entirely would remove a simpler, tax-independent
figure that some commission policies still want to reference, and
because it was already in place and used by session 2.1's structure
before this ADR.

**`amount_total` (subtotal plus taxes).** Simpler to justify to a
non-technical stakeholder, but taxes vary by customer country and
fiscal position, so two identical sales to different countries would
pay different commissions for identical work. Rejected: the agent's
earnings would depend on something they do not control and did not
sell.

**Both bases side by side (chosen).** Requires depending on
`sale_margin`, which pulls in cost data (`standard_price`) that must be
correctly configured per product to be meaningful. The known weakness
of the subtotal-only figure stays visible rather than hidden: both
numbers are stored, so the discount-manipulation gap in
`commission_amount` is there to see, not silently accepted.

### Consequences
- The manifest now depends on `sale_margin`, not only `sale`.
- Session 2.3's settlement model can read either
  `commission_amount` or `commission_amount_margin`, or both, when
  building a settlement line. Which one becomes the default settlement
  base is a decision still open for 2.3.
- Margin figures are only meaningful if product cost
  (`standard_price`) is set correctly. On a database with poorly
  costed demo products, `commission_amount_margin` will show
  misleadingly low or zero values; this is a data quality issue in the
  source data, not a bug in this module.

## Decision 2: one agent per order, not several

`agent_id` is a single `Many2one`, not a `Many2many` or a one2many to a
split table.

### Alternatives considered

**Many2many with a split ratio per agent.** Handles the real-world
case of two agents co-selling one deal. Rejected for this stage
because it requires a split ratio (and possibly a role: closer versus
referrer) per agent, which turns `agent_id` from a field into a small
model of its own — essentially building session 2.3's settlement lines
a session early, without a concrete requirement driving the design of
how the split should work.

**Single agent (chosen).** Matches the common case of one salesperson
per order, keeps `commission_rate` and both commission amount fields
as simple scalars, and keeps the compute logic a one-line
`@api.depends`. The limitation is real: a genuinely split-commission
deal cannot be represented, and forcing it into a single `agent_id`
would mean picking one agent arbitrarily or entering two separate
orders for one deal, which breaks the correspondence between order and
sale.

This was deliberately not generalized ahead of need. No concrete
split-commission case has been specified yet (equal split? weighted?
role-based?), and building the wrong shape of generality is more
expensive to unwind later than building none. The migration cost of
extending later, described below, is known and bounded, which is what
makes deferring it an acceptable trade rather than a shortcut.

### Consequences
- Session 2.3's settlement wizard groups by a single `agent_id`, one
  settlement per agent per period, with no split logic to build.
- Extending to multiple agents later is a breaking change to the data
  model, not an additive one: `agent_id` would need to become a
  one2many to a new `sale.order.commission.line` model, and existing
  orders would need a migration script converting the single value
  into a one-line recordset.
- This is the higher-risk deferred decision of the two: Decision 1 was
  extended alongside the existing field without touching stored data;
  Decision 2 cannot be extended the same way.

## See also
- This is the first ADR in the `sale_agent_commission` repository;
  numbering here is independent from the `odoo-lab` learning
  repository's own ADR sequence.
- `odoo-lab`, `docs/reference/learning-path.md`, session 2.2, for the
  context this module was built under.
