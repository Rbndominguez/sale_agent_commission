# ADR-0002: Settlement as a document with frozen lines

## Status
Accepted, 2026-08-25

## Context
Session 2.3 introduces the model that pays agents. ADR-0001 stored two
commission figures on `sale.order` (`commission_amount` on
`amount_untaxed` and `commission_amount_margin` on `margin`) and left
open which one a settlement uses. That question has to be answered
before a settlement can compute anything, and the shape of the
settlement itself (a document, or a flag on the order) determines
whether a paid settlement can change value after the fact.

## Decision 1: the settlement chooses its own commission base

`sale.commission.settlement` carries a required `commission_base`
selection, `untaxed` or `margin`, defaulting to `untaxed`. Each
settlement line copies the corresponding figure from the order.

The base is a property of how an agent is paid, not of how a sale was
made, so it belongs to the payment document. Keeping it per settlement
also makes the two bases of ADR-0001 usable at the same time in one
database, which is the reason both were kept.

### Alternatives considered

**A company-wide setting.** One base per company, configured once in
`res.config.settings`. More consistent, since the same period could
never be settled twice on different bases, but it makes the common case
of two agents on different contracts inexpressible, and it introduces
settings machinery not otherwise needed at this stage.

**Settling both bases in the same document.** Rejected: a settlement is
a payable amount, and two totals in one document is not a payable
amount.

### Consequences
- Two settlements for the same agent and period, on different bases,
  would pay twice. This is prevented by Decision 3 below, which is
  base-independent by design.
- The wizard in session 2.4 must ask for the base before it can
  propose any figure.

## Decision 2: a settlement is a document with frozen lines

Two models: `sale.commission.settlement` (header) and
`sale.commission.settlement.line` (one line per settled order). Each
line stores `base_amount`, `commission_rate` and `amount` as computed,
stored, non-readonly fields depending on `order_id` and
`settlement_id.commission_base` only, never on the order amounts
themselves.

Selecting an order proposes the figures; later changes to the order do
not alter them. This is the same pattern as `commission_rate` on
`sale.order` in ADR-0001: what is frozen is decided by what is left out
of `@api.depends`, not by the field type.

### Alternatives considered

**A `settlement_id` many2one on `sale.order`, with an inverse
one2many.** No new line model, less code. Rejected because the settled
amount would remain a live computed field of the order: reopening and
editing a confirmed order would silently change the total of an already
paid settlement. It also leaves no place for manual adjustments, which
occur in practice.

### Consequences
- Line amounts can be edited by hand while the settlement is in draft.
  This is intended; the audit trail is the chatter on the header.
- `base_amount` and `commission_rate` on the line are informational,
  showing how `amount` was reached. They are not recomputed from each
  other, so an edited `base_amount` does not change `amount`.
- Settlement lines only accept orders in the settlement currency, which
  is the company currency. Multi-currency settlement is not supported
  and would require a conversion rate and a conversion date on the
  header.

## Decision 3: four states, and an order can only be in one live settlement

States are `draft`, `confirmed`, `paid` and `cancelled`. Transitions
happen only through public action methods that validate the source
state; the view hides buttons but does not enforce anything.

A Python constraint rejects a line whose order already appears in
another settlement whose state is not `cancelled`. The check ignores the
commission base, so the double-payment risk opened by Decision 1 is
closed here.

### Alternatives considered

**Draft and paid only.** Rejected: preparing a settlement and approving
the payment are different acts by different people. `confirmed` is the
point where the document stops being editable and no money has moved
yet.

**A database unique constraint on `order_id`.** Cheaper than a Python
constraint, but it would also block re-settling an order whose previous
settlement was cancelled, which is precisely why cancellation exists.

### Consequences
- Cancelling a settlement releases its orders for settlement again.
- Deletion is blocked outside `draft` and `cancelled` through
  `@api.ondelete(at_uninstall=False)`, so uninstalling the module is not
  obstructed by business rules.
- `sale.order.commission_settled` is a stored computed boolean over the
  live settlements of the order, so session 2.4's wizard can filter
  pending orders with a domain instead of Python.

## See also
- ADR-0001 of this repository, for the two commission bases and the
  single agent per order.