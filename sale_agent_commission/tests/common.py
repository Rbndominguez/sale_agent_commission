from odoo import Command
from odoo.tests.common import TransactionCase, new_test_user


class CommissionCase(TransactionCase):
    """Fixture shared by every test of this module.

    Nothing here relies on demo data: the suite must pass on a database
    installed with --without-demo=all, which is how CI installs it.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.agent_a = new_test_user(
            cls.env,
            login="commission_agent_a",
            groups="sales_team.group_sale_salesman",
            name="Agent A",
            email="agent.a@example.com",
            tz="Europe/Madrid",
            commission_agent=True,
            commission_rate=10.0,
        )
        cls.agent_b = new_test_user(
            cls.env,
            login="commission_agent_b",
            groups="sales_team.group_sale_salesman",
            name="Agent B",
            email="agent.b@example.com",
            tz="Europe/Madrid",
            commission_agent=True,
            commission_rate=5.0,
        )
        cls.manager = new_test_user(
            cls.env,
            login="commission_manager",
            groups="sales_team.group_sale_manager",
            name="Commission Manager",
            email="commission.manager@example.com",
            tz="Europe/Madrid",
        )
        cls.customer = cls.env["res.partner"].create({"name": "Commission Customer"})
        cls.product = cls.env["product.product"].create(
            {
                "name": "Commissioned Product",
                "type": "consu",
                "list_price": 1000.0,
                "standard_price": 600.0,
            }
        )

    def _create_order(
        self, agent, date_order=False, price_unit=1000.0, qty=1.0, confirm=True
    ):
        """One confirmed order: untaxed 1000, margin 400 with the defaults."""
        order = self.env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                "agent_id": agent.id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": qty,
                            "price_unit": price_unit,
                        }
                    )
                ],
            }
        )
        if confirm:
            order.action_confirm()
        if date_order:
            # action_confirm() overwrites date_order with the current time,
            # so the period under test can only be forced afterwards.
            order.date_order = date_order
        return order

    def _create_settlement(
        self,
        agent,
        orders=None,
        base="untaxed",
        date_from="2026-06-01",
        date_to="2026-06-30",
    ):
        return self.env["sale.commission.settlement"].create(
            {
                "agent_id": agent.id,
                "date_from": date_from,
                "date_to": date_to,
                "commission_base": base,
                "line_ids": [
                    Command.create({"order_id": order.id})
                    for order in (orders or self.env["sale.order"])
                ],
            }
        )
