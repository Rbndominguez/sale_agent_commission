from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    agent_id = fields.Many2one(
        comodel_name="res.users",
        string="Commission Agent",
        domain="[('commission_agent', '=', True)]",
        tracking=True,
        help="User who earns a commission on this order.",
    )
    commission_rate = fields.Float(
        string="Commission Rate (%)",
        digits=(5, 2),
        compute="_compute_commission_rate",
        store=True,
        readonly=False,
        precompute=True,
        tracking=True,
        help="Proposed from the agent, then frozen on this order.",
    )
    commission_amount = fields.Monetary(
        string="Commission",
        currency_field="currency_id",
        compute="_compute_commission_amount",
        store=True,
    )
    _commission_rate_range = models.Constraint(
        "CHECK(commission_rate >= 0 AND commission_rate <= 100)",
        "The commission rate must be between 0 and 100.",
    )
    commission_amount_margin = fields.Monetary(
        string="Commission (on Margin)",
        currency_field="currency_id",
        compute="_compute_commission_amount_margin",
        store=True,
    )
    settlement_line_ids = fields.One2many(
        comodel_name="sale.commission.settlement.line",
        inverse_name="order_id",
        string="Settlement lines",
    )
    commission_settled = fields.Boolean(
        compute="_compute_commission_settled",
        store=True,
        help="Set when this order belongs to a settlement that is not cancelled.",
    )

    @api.depends("settlement_line_ids.settlement_id.state")
    def _compute_commission_settled(self):
        for order in self:
            order.commission_settled = any(
                line.settlement_id.state != "cancelled"
                for line in order.settlement_line_ids
            )

    @api.depends("margin", "commission_rate")
    def _compute_commission_amount_margin(self):
        for order in self:
            amount = order.margin * order.commission_rate / 100.0
            order.commission_amount_margin = (
                order.currency_id.round(amount) if order.currency_id else amount
            )

    @api.depends("agent_id")
    def _compute_commission_rate(self):
        for order in self:
            order.commission_rate = order.agent_id.commission_rate

    @api.depends("amount_untaxed", "commission_rate")
    def _compute_commission_amount(self):
        for order in self:
            amount = order.amount_untaxed * order.commission_rate / 100.0
            order.commission_amount = (
                order.currency_id.round(amount) if order.currency_id else amount
            )
