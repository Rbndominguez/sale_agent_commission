from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import CommissionCase


@tagged("post_install", "-at_install")
class TestSettlementSecurity(CommissionCase):
    """ADR-0002 consequence: an agent only ever sees their own settlements."""

    def test_an_agent_only_sees_their_own_settlements(self):
        mine = self._create_settlement(self.agent_a)
        other = self._create_settlement(self.agent_b)

        visible = (
            self.env["sale.commission.settlement"].with_user(self.agent_a).search([])
        )

        self.assertIn(mine, visible)
        self.assertNotIn(other, visible)

    def test_an_agent_only_sees_their_own_settlement_lines(self):
        order = self._create_order(self.agent_b)
        self._create_settlement(self.agent_b, order)

        visible = (
            self.env["sale.commission.settlement.line"]
            .with_user(self.agent_a)
            .search([])
        )

        self.assertFalse(visible)

    def test_a_manager_sees_every_settlement(self):
        mine = self._create_settlement(self.agent_a)
        other = self._create_settlement(self.agent_b)

        visible = (
            self.env["sale.commission.settlement"].with_user(self.manager).search([])
        )

        self.assertIn(mine, visible)
        self.assertIn(other, visible)

    def test_an_agent_cannot_create_a_settlement(self):
        with self.assertRaises(AccessError):
            self.env["sale.commission.settlement"].with_user(self.agent_a).create(
                {
                    "agent_id": self.agent_a.id,
                    "date_from": "2026-06-01",
                    "date_to": "2026-06-30",
                }
            )

    def test_an_agent_cannot_open_the_generate_wizard(self):
        with self.assertRaises(AccessError):
            self.env["sale.commission.settlement.generate"].with_user(
                self.agent_a
            ).create(
                {
                    "agent_ids": [Command.set(self.agent_a.ids)],
                    "date_from": "2026-06-01",
                    "date_to": "2026-06-30",
                }
            )
