from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError


class SaleCommissionSettlementGenerate(models.TransientModel):
    _name = "sale.commission.settlement.generate"
    _description = "Generate Agent Commission Settlements"

    def _default_date_from(self):
        first_of_month = fields.Date.context_today(self).replace(day=1)
        return first_of_month - relativedelta(months=1)

    def _default_date_to(self):
        first_of_month = fields.Date.context_today(self).replace(day=1)
        return first_of_month - relativedelta(days=1)

    agent_ids = fields.Many2many(
        comodel_name="res.users",
        string="Agents",
        required=True,
        domain=[("commission_agent", "=", True)],
        help="One settlement is created per agent with pending orders.",
    )
    date_from = fields.Date(
        string="From",
        required=True,
        default=_default_date_from,
    )
    date_to = fields.Date(
        string="To",
        required=True,
        default=_default_date_to,
    )
    commission_base = fields.Selection(
        selection=[
            ("untaxed", "Untaxed amount"),
            ("margin", "Margin"),
        ],
        string="Commission base",
        required=True,
        default="untaxed",
        help="Which commission figure of the order the settlements will pay.",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id",
    )
    candidate_order_ids = fields.Many2many(
        comodel_name="sale.order",
        string="Orders to settle",
        compute="_compute_candidates",
    )
    candidate_count = fields.Integer(
        string="Orders found",
        compute="_compute_candidates",
    )
    estimated_amount = fields.Monetary(
        string="Estimated total",
        compute="_compute_candidates",
    )
    _check_period = models.Constraint(
        "CHECK(date_to >= date_from)",
        "A settlement period cannot end before it starts.",
    )

    def _commission_field(self):
        """Order field holding the commission for the selected base."""
        self.ensure_one()
        if self.commission_base == "margin":
            return "commission_amount_margin"
        return "commission_amount"

    def _period_bounds(self):
        """Return the period as naive UTC datetimes, as stored by the ORM.

        date_order is a Datetime stored in UTC, while date_from and date_to
        are Dates read by the user in their own time zone. Comparing them
        directly would shift the period by the user's UTC offset.
        """
        self.ensure_one()
        user_tz = ZoneInfo(self.env.user.tz or "UTC")
        start = datetime.combine(self.date_from, time.min, tzinfo=user_tz)
        end = datetime.combine(self.date_to, time.max, tzinfo=user_tz)
        return (
            start.astimezone(timezone.utc).replace(tzinfo=None),
            end.astimezone(timezone.utc).replace(tzinfo=None),
        )

    def _candidate_domain(self):
        """Domain of the orders this wizard would settle."""
        self.ensure_one()
        date_start, date_end = self._period_bounds()
        return [
            ("state", "=", "sale"),
            ("agent_id", "in", self.agent_ids.ids),
            ("commission_settled", "=", False),
            ("company_id", "=", self.company_id.id),
            ("currency_id", "=", self.currency_id.id),
            ("date_order", ">=", date_start),
            ("date_order", "<=", date_end),
            (self._commission_field(), "!=", 0),
        ]

    def _candidate_orders(self):
        self.ensure_one()
        if not (self.agent_ids and self.date_from and self.date_to):
            return self.env["sale.order"]
        if self.date_to < self.date_from:
            return self.env["sale.order"]
        return self.env["sale.order"].search(self._candidate_domain())

    @api.depends(
        "agent_ids",
        "date_from",
        "date_to",
        "commission_base",
        "company_id",
    )
    def _compute_candidates(self):
        for wizard in self:
            orders = wizard._candidate_orders()
            wizard.candidate_order_ids = orders
            wizard.candidate_count = len(orders)
            wizard.estimated_amount = sum(
                orders.mapped(wizard._commission_field())
            )

    def _settlement_values(self, agent, orders):
        """Values of the settlement created for one agent."""
        self.ensure_one()
        return {
            "agent_id": agent.id,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "commission_base": self.commission_base,
            "company_id": self.company_id.id,
            "line_ids": [
                Command.create({"order_id": order.id}) for order in orders
            ],
        }

    def action_generate(self):
        self.ensure_one()
        orders = self._candidate_orders()
        if not orders:
            raise UserError(
                _(
                    "No pending order matches this period, base and set of "
                    "agents. Nothing to settle."
                )
            )
        vals_list = []
        for agent in self.agent_ids:
            agent_orders = orders.filtered(
                lambda order, agent=agent: order.agent_id == agent
            )
            if not agent_orders:
                continue
            vals_list.append(self._settlement_values(agent, agent_orders))
        settlements = self.env["sale.commission.settlement"].create(vals_list)
        return self._open_settlements(settlements)

    def _open_settlements(self, settlements):
        action = self.env["ir.actions.actions"]._for_xml_id(
            "sale_agent_commission.sale_commission_settlement_action"
        )
        if len(settlements) == 1:
            action["views"] = [(False, "form")]
            action["res_id"] = settlements.id
        else:
            action["domain"] = [("id", "in", settlements.ids)]
        return action