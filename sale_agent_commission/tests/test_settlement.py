from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import CommissionCase


@tagged("post_install", "-at_install")
class TestSettlement(CommissionCase):
    """ADR-0002: a document with frozen lines and a four-state flow."""

    def test_reference_comes_from_the_sequence(self):
        settlement = self._create_settlement(self.agent_a)
        self.assertNotEqual(settlement.name, "New")
        self.assertTrue(settlement.name.startswith("COM/"))

    def test_line_amounts_are_frozen_when_the_order_changes(self):
        order = self._create_order(self.agent_a)
        settlement = self._create_settlement(self.agent_a, order)
        self.assertEqual(settlement.amount_total, 100.0)

        order.order_line.product_uom_qty = 2.0

        self.assertEqual(order.commission_amount, 200.0)
        self.assertEqual(settlement.line_ids.amount, 100.0)
        self.assertEqual(settlement.amount_total, 100.0)

    def test_changing_the_base_recomputes_the_lines(self):
        order = self._create_order(self.agent_a)
        settlement = self._create_settlement(self.agent_a, order)

        settlement.commission_base = "margin"

        self.assertEqual(settlement.line_ids.base_amount, 400.0)
        self.assertEqual(settlement.line_ids.amount, 40.0)
        self.assertEqual(settlement.amount_total, 40.0)

    def test_an_empty_settlement_cannot_be_confirmed(self):
        settlement = self._create_settlement(self.agent_a)
        with self.assertRaises(UserError):
            settlement.action_confirm()

    def test_states_only_move_forward_through_their_own_action(self):
        settlement = self._create_settlement(
            self.agent_a, self._create_order(self.agent_a)
        )
        with self.assertRaises(UserError):
            settlement.action_mark_as_paid()

        settlement.action_confirm()
        self.assertEqual(settlement.state, "confirmed")
        settlement.action_mark_as_paid()
        self.assertEqual(settlement.state, "paid")

        with self.assertRaises(UserError):
            settlement.action_cancel()

    def test_a_confirmed_settlement_cannot_be_deleted(self):
        settlement = self._create_settlement(
            self.agent_a, self._create_order(self.agent_a)
        )
        settlement.action_confirm()
        with self.assertRaises(UserError):
            settlement.unlink()

    def test_an_order_of_another_agent_is_rejected(self):
        order = self._create_order(self.agent_b)
        with self.assertRaises(ValidationError):
            self._create_settlement(self.agent_a, order)

    def test_an_order_is_settled_once_until_the_settlement_is_cancelled(self):
        order = self._create_order(self.agent_a)
        first = self._create_settlement(self.agent_a, order)
        self.assertTrue(order.commission_settled)

        with self.assertRaises(ValidationError), self.cr.savepoint():
            self._create_settlement(self.agent_a, order, base="margin")

        first.action_cancel()
        self.assertFalse(order.commission_settled)

        second = self._create_settlement(self.agent_a, order)
        self.assertEqual(second.line_ids.order_id, order)
        self.assertTrue(order.commission_settled)
