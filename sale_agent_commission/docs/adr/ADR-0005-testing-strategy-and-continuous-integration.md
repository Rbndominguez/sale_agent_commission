# ADR-0005: Testing strategy and continuous integration

## Status
Accepted, 2026-08-27

## Context
Sessions 2.1 to 2.5 built a module whose value is almost entirely in its
business rules: which orders are candidates, which figure a line freezes,
who may see a settlement, when a printout becomes an archived document.
All of them were verified by hand, once, in a browser. Session 2.4 found
that the record rules written in 2.3 had never been loaded at all, and
nothing had noticed for two sessions. That class of silent regression is
what this decision exists to prevent.

## Decision 1: ORM-level tests, no browser tours

Tests subclass `odoo.tests.common.TransactionCase` and drive the models
directly. The suite asserts business rules, not rendering: state
transitions, constraints, record rules, access rights, candidate
selection and the frozen line amounts.

Views are exercised only indirectly, through the QWeb report, which is
rendered as HTML and inspected as text.

### Alternatives considered

**HTTP tours (`HttpCase` and JavaScript tours).** They would cover the
views, the Action menu binding and the buttons, which are precisely
where two of the four bugs of session 2.4 lived. Rejected for now
because a tour is slow, brittle against upstream markup changes, and
needs a browser in CI. The gap is real and accepted: a green suite says
the rules hold, not that the buttons are reachable.

**`SingleTransactionCase`.** Faster, since the whole class shares one
transaction and nothing is rolled back between tests. Rejected because
tests then depend on execution order, and a failure halfway leaves the
rest of the class running on corrupted data.

### Consequences
- Every test builds its own data. No test may rely on demo records, so
  the suite runs on a database installed with `--without-demo=all`.
- The fixture creates users with an explicit `tz`, because the acting
  user's timezone changes query results (see Decision 2).
- Tests that must exercise access rights use `with_user()`. The default
  test environment runs as superuser and bypasses both ACLs and record
  rules, so a security test written with it would pass unconditionally.

## Decision 2: the acting user is part of the fixture, not a detail

Every test that touches a date range or a permission states which user it
runs as, and the fixture sets `tz` explicitly on each one.

This is not stylistic. Odoo 19's ORM converts a `date` value compared
against a `Datetime` field in a domain using the acting user's `tz`,
automatically. Session 2.6 established this empirically: the same domain,
the same data and the same PostgreSQL session return different rows
depending only on whether the acting user has a `tz` set. A test that
does not control the acting user is therefore not testing a fixed
question.

The corollary is uncomfortable and is recorded here rather than hidden:
a test asserting timezone-correct period boundaries passes under a user
with `tz` **whether or not the code under test does any conversion at
all**, because the ORM does it anyway. Such a test guards behaviour, not
implementation. Where the distinction matters, the test must run as a
user without `tz`.

### Consequences
- `test_period_bounds_follow_the_user_timezone` documents in its
  docstring what it cannot prove, instead of implying more than it does.
- `test_a_user_without_tz_gets_naive_utc_bounds` pins the cron-shaped
  case separately, asserting current behaviour rather than desired
  behaviour.
- Whether an automated run should use the company timezone instead of
  falling back to UTC is left open for session 2.6b. See ADR-0003.

## Decision 3: the PDF is tested as HTML plus an expression

The report suite renders the template with `_render_qweb_html` and
evaluates the `attachment` expression with `safe_eval`. A single
end-to-end test calls `_render_qweb_pdf` and skips itself, loudly, when
the returned `report_type` is not `pdf`.

Rendering a real PDF requires wkhtmltopdf, and wkhtmltopdf needs a
running HTTP server to fetch report assets. `--stop-after-init` starts no
server, so under the test runner Odoo falls back to HTML without raising.
A test built on `_render_qweb_pdf` alone would silently assert something
different from what it asserts in an environment where the PDF pipeline
does run.

Probing the actual `report_type` and skipping is preferred over guarding
on `shutil.which("wkhtmltopdf")`: the binary being installed and the
pipeline being usable are two different conditions, and session 2.6 hit
exactly that gap.

### Consequences
- Template errors and the state banners of ADR-0004 are covered
  everywhere.
- The `ir.attachment` row is only really asserted in an environment where
  the PDF pipeline runs. Locally under `--stop-after-init` that test
  reports as skipped, which is visible in the log, not as passed.

## Decision 4: CI runs on the official Odoo Docker image

The GitHub Actions workflow runs the test job inside `odoo:19.0` with a
`postgres:16` service container, rather than cloning `odoo/odoo` and
installing `requirements.txt` on every run.

### Alternatives considered

**Cloning odoo/odoo at branch 19.0 with `--depth 1`.** Tests the module
against the current state of the branch, which is what a partner deploys
from. Rejected as the default because it adds several minutes and
hundreds of megabytes to every run for a module of this size. It is the
right choice for a repository that must track upstream daily, and
switching later is a change to one job.

**OCA's Maintainer Quality Tools.** The ecosystem standard, and it also
enforces the OCA metadata conventions. Rejected because it pins its own
Odoo checkout and its own linter set, which would obscure what this
repository decides for itself, and because it lags behind on new
versions.

### Consequences
- The image is built from stable releases, so it can be behind the 19.0
  branch. A regression caused by a recent upstream commit is not caught
  until the image is rebuilt.
- The suite is pinned to a single Odoo version. Supporting another
  version means a matrix over image tags, not new code.
- Linting runs in a separate job on a plain runner, so a style failure is
  visible without waiting for the database to install.
- CI is the only environment where the suite runs against a PostgreSQL
  session that is not the developer's own. Session 2.6 showed how easily
  a local environment can agree with the code by coincidence.

## See also
- ADR-0001 to ADR-0004 of this repository: every decision they record has
  at least one test asserting it.
- ADR-0003, revisited note on `_period_bounds`.