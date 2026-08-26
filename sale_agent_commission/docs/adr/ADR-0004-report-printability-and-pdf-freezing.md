# ADR-0004: Report printable in every state, PDF frozen only when paid

## Status
Accepted, 2026-08-26

## Context
Session 2.5 adds the QWeb PDF report of `sale.commission.settlement`. Two
questions had to be answered before writing the template, because both
change what the printed document means rather than how it looks.

The first is whether a document that is not yet payable should be
printable at all. The second is when, if ever, Odoo should stop
re-rendering the PDF and start returning a stored copy, which is what
`ir.actions.report` does through its `attachment` expression and the
`attachment_use` flag.

## Decision 1: the report prints in every state, with a visible warning

There is no state guard on the report action. A settlement can be printed
in `draft`, `confirmed`, `paid` and `cancelled`. The template shows a
warning banner in `draft` ("lines can still be edited") and in
`cancelled` ("does not represent a payable amount"), and prints the
state as a field in the header block of every copy.

A settlement in draft is a work document: the person preparing it needs
to review it on paper or send it to the agent for checking before
confirming. Refusing to print it does not prevent that need, it pushes
the user to export the list view instead, which produces a document with
no company header, no state and no audit value.

### Alternatives considered

**Printing allowed only from `confirmed` onwards.** Guarantees that
every PDF in circulation is a real commitment. Rejected because the
guarantee is weaker than it looks: a confirmed settlement can still be
cancelled, so a confirmed printout is not proof of payment either. The
banner carries the same information at a lower cost, and it keeps
working for the cancelled case, which a state guard would not cover.

### Consequences
- Every printed copy states its own state, so a draft copy is never
  mistaken for a payable one.
- The report action needs no group restriction: read access and the
  record rule from session 2.3 already limit an agent to their own
  settlements.

## Decision 2: the PDF is stored as an attachment only in state `paid`

The report action sets `attachment_use` to true and an `attachment`
expression that returns a filename only when the record is in `paid`,
and a falsy value otherwise. The first print of a paid settlement is
stored as an `ir.attachment` on the record; every later print returns
those same bytes instead of rendering again.

`paid` is the terminal state of the flow: no transition leaves it, and
it is the point where money has moved. Freezing there means the archived
copy is exactly the document that supported the payment, byte for byte,
independent of anything that changes afterwards in the company layout,
the report template, or the module itself.

### Alternatives considered

**Never store, always re-render.** Simplest, and always consistent with
current data. Rejected because a settlement paid in January and
reprinted in June would come out with June's letterhead and June's
version of the template. For a document that justifies a payment, the
copy has to be stable, not current.

**Store from `confirmed` onwards.** Tempting, because ADR-0002 makes
`confirmed` the point where the document stops being editable. Rejected
because of how `attachment_use` behaves: once the file exists it is
returned unchanged forever, so a settlement stored at `confirmed` would
keep printing "Confirmed" long after being paid. Freezing at a state
that is not terminal freezes a lie.

**Store in every state.** Rejected outright: a draft PDF would be frozen
while its lines are still editable, so the printout would silently stop
matching the record.

### Consequences
- Paid settlements accumulate one `ir.attachment` each. This is intended
  storage, not leakage, and it is the same mechanism Odoo uses for
  posted invoices.
- Changing the template later does not change already paid documents.
  Fixing a genuine error in an archived copy requires deleting the
  attachment by hand, which is the intended friction.
- Uninstalling the module does not remove those attachments: they belong
  to a record created by a user, not to the module's `ir_model_data`.

## See also
- ADR-0002 of this repository, for the four states and the frozen lines
  of the settlement document.