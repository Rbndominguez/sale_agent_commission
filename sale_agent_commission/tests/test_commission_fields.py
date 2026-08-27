from psycopg2 import IntegrityError

from odoo.tests import tagged
from odoo.tools import mute_logger
# from odoo.tools.misc import mute_logger

from .common import CommissionCase


@tagged("post_install", "-at_install")
class TestCommissionFields(CommissionCase):
    """ADR-0001: two commission bases, one agent, rate frozen on the order."""

    def test_rate_is_proposed_from_the_agent(self):
        order = self._create_order(self.agent_a, confirm=False)
        self.assertEqual(order.commission_rate, 10.0)

    def test_rate_stays_frozen_when_the_agent_default_changes(self):
        order = self._create_order(self.agent_a, confirm=False)
        self.agent_a.commission_rate = 20.0
        # _compute_commission_rate depends on agent_id only, so a later
        # change to the agent default never rewrites a past order.
        self.assertEqual(order.commission_rate, 10.0)

    def test_both_commission_bases_are_computed(self):
        order = self._create_order(self.agent_a)
        self.assertEqual(order.amount_untaxed, 1000.0)
        self.assertEqual(order.margin, 400.0)
        self.assertEqual(order.commission_amount, 100.0)
        self.assertEqual(order.commission_amount_margin, 40.0)

    def test_rate_above_one_hundred_is_rejected(self):
        order = self._create_order(self.agent_a, confirm=False)
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            with self.cr.savepoint():
                order.commission_rate = 150.0
                # The CHECK lives in PostgreSQL, and the ORM batches writes
                # in cache: without an explicit flush the write looks fine.
                self.env.flush_all()

    def test_an_order_without_agent_has_no_commission(self):
        order = self._create_order(self.agent_a, confirm=False)
        order.agent_id = False
        self.assertEqual(order.commission_rate, 0.0)
        self.assertEqual(order.commission_amount, 0.0)

    def test_agent_rate_above_one_hundred_is_rejected(self):
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            with self.cr.savepoint():
                self.agent_a.commission_rate = 150.0
                self.env.flush_all()
