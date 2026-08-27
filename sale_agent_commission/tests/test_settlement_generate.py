from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import new_test_user

from .common import CommissionCase


@tagged("post_install", "-at_install")
class TestSettlementGenerate(CommissionCase):
    """ADR-0003: candidate selection and one settlement per agent per run."""

    def _create_wizard(self, agents, date_from="2026-06-01", date_to="2026-06-30"):
        # Created as the manager: _period_bounds() reads self.env.user.tz,
        # and the ACL of the transient model is manager only.
        return (
            self.env["sale.commission.settlement.generate"]
            .with_user(self.manager)
            .create(
                {
                    "agent_ids": [Command.set(agents.ids)],
                    "date_from": date_from,
                    "date_to": date_to,
                }
            )
        )

    def test_candidates_are_filtered_by_agent(self):
        order_a = self._create_order(self.agent_a, date_order="2026-06-15 10:00:00")
        self._create_order(self.agent_b, date_order="2026-06-15 10:00:00")

        wizard = self._create_wizard(self.agent_a)

        self.assertEqual(wizard.candidate_order_ids, order_a)
        self.assertEqual(wizard.candidate_count, 1)
        self.assertEqual(wizard.estimated_amount, 100.0)

    def test_a_draft_order_is_not_a_candidate(self):
        order = self._create_order(self.agent_a, confirm=False)
        order.date_order = "2026-06-15 10:00:00"

        wizard = self._create_wizard(self.agent_a)

        self.assertNotIn(order, wizard.candidate_order_ids)

    def test_period_bounds_follow_the_user_timezone(self):
        """Period boundaries land on local midnight, not UTC midnight.

        Europe/Madrid is UTC+2 in June and date_order is stored naive UTC,
        so the June period runs from 2026-05-31 22:00 to 2026-06-30 21:59:59
        in stored terms.

        Note on what this test does and does not prove: Odoo 19's ORM
        converts a `date` value compared against a Datetime field using the
        acting user's tz on its own, so this test also passes if
        _period_bounds returns date_from/date_to unconverted. It is a
        regression guard on the resulting behaviour, not a proof that
        _period_bounds itself is doing the conversion. See the dev-log for
        session 2.6 and the note in ADR-0003.
        """
        last_minute = self._create_order(
            self.agent_a, date_order="2026-06-30 21:59:00"
        )  # 23:59 local, still June
        next_month = self._create_order(
            self.agent_a, date_order="2026-06-30 22:30:00"
        )  # 00:30 local, already July
        first_minute = self._create_order(
            self.agent_a, date_order="2026-05-31 22:30:00"
        )  # 00:30 local, already June

        wizard = self._create_wizard(self.agent_a)

        self.assertIn(last_minute, wizard.candidate_order_ids)
        self.assertIn(first_minute, wizard.candidate_order_ids)
        self.assertNotIn(next_month, wizard.candidate_order_ids)

    def test_a_user_without_tz_gets_naive_utc_bounds(self):
        """A user with no tz gets UTC boundaries, with no further correction.

        `_period_bounds` falls back to `or "UTC"`, and the ORM does not
        convert either when the acting user has no tz, so both agree on a
        naive UTC comparison. A cron's technical account is normally in
        exactly this situation.

        This asserts the CURRENT behaviour so a change to it is visible, not
        that it is the desired one: settling on the company timezone instead
        is the open question left for session 2.6b.
        """
        no_tz_manager = new_test_user(
            self.env,
            login="commission_manager_no_tz",
            groups="sales_team.group_sale_manager",
            name="Commission Manager No TZ",
        )
        self.assertFalse(no_tz_manager.tz)

        last_minute = self._create_order(self.agent_a, date_order="2026-06-30 21:59:00")
        next_month = self._create_order(self.agent_a, date_order="2026-06-30 22:30:00")
        first_minute = self._create_order(
            self.agent_a, date_order="2026-05-31 22:30:00"
        )

        wizard = (
            self.env["sale.commission.settlement.generate"]
            .with_user(no_tz_manager)
            .create(
                {
                    "agent_ids": [Command.set(self.agent_a.ids)],
                    "date_from": "2026-06-01",
                    "date_to": "2026-06-30",
                }
            )
        )

        # Naive UTC: the July order is wrongly kept and the June one wrongly
        # dropped, both by exactly the agent's UTC offset.
        self.assertIn(last_minute, wizard.candidate_order_ids)
        self.assertIn(next_month, wizard.candidate_order_ids)
        self.assertNotIn(first_minute, wizard.candidate_order_ids)

    def test_one_settlement_is_created_per_agent(self):
        order_a = self._create_order(self.agent_a, date_order="2026-06-15 10:00:00")
        order_b = self._create_order(self.agent_b, date_order="2026-06-16 10:00:00")

        wizard = self._create_wizard(self.agent_a | self.agent_b)
        self.assertEqual(wizard.candidate_count, 2)
        wizard.action_generate()

        settlements = self.env["sale.commission.settlement"].search(
            [("agent_id", "in", (self.agent_a | self.agent_b).ids)]
        )
        self.assertEqual(len(settlements), 2)

        settlement_a = settlements.filtered(lambda s: s.agent_id == self.agent_a)
        settlement_b = settlements.filtered(lambda s: s.agent_id == self.agent_b)
        self.assertEqual(settlement_a.line_ids.order_id, order_a)
        self.assertEqual(settlement_a.amount_total, 100.0)
        self.assertEqual(settlement_b.line_ids.order_id, order_b)
        self.assertEqual(settlement_b.amount_total, 50.0)
        self.assertTrue(order_a.commission_settled)

    def test_a_settled_order_is_not_offered_again(self):
        self._create_order(self.agent_a, date_order="2026-06-15 10:00:00")
        self._create_wizard(self.agent_a).action_generate()

        second_run = self._create_wizard(self.agent_a)

        self.assertEqual(second_run.candidate_count, 0)

    def test_generating_without_candidates_is_refused(self):
        self._create_order(self.agent_a, date_order="2026-06-15 10:00:00")

        wizard = self._create_wizard(
            self.agent_a, date_from="2020-01-01", date_to="2020-01-31"
        )

        self.assertEqual(wizard.candidate_count, 0)
        with self.assertRaises(UserError):
            wizard.action_generate()
