[![CI](https://github.com/Rbndominguez/sale_agent_commission/actions/workflows/ci.yml/badge.svg)](https://github.com/Rbndominguez/sale_agent_commission/actions/workflows/ci.yml)
# Sale Agent Commission

Commission calculation and settlement for sales agents, for Odoo 19.

## Status

Work in progress. See the roadmap below.

## What it does

Assigns a sales agent to a sale order, computes the commission for
each confirmed order, and groups commissions into settlement
documents with their own state flow and PDF report.

## Requirements

- Odoo 19.0 (Community)
- Depends on `sale`

## Installation

Clone this repository into a directory listed in `addons_path`, then:

    odoo -i sale_agent_commission -d YOUR_DATABASE

## Roadmap

- [ ] Agent and commission fields on sale orders
- [ ] Settlement model and state flow
- [ ] Wizard to generate settlements
- [ ] QWeb PDF report
- [ ] Automated tests

## Licence

AGPL-3. See `LICENSE`.

## Author

Ruben Iglesias Dominguez