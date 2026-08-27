from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SaleCommissionSettlementLine(models.Model):
    _name = "sale.commission.settlement.line"
    _description = "Agent Commission Settlement Line"
    _order = "settlement_id, order_id"

    settlement_id = fields.Many2one(
        comodel_name="sale.commission.settlement",
        string="Settlement",
        required=True,
        ondelete="cascade",
        index=True,
    )
    order_id = fields.Many2one(
        comodel_name="sale.order",
        string="Sales order",
        required=True,
        ondelete="restrict",
        domain="[('agent_id', '!=', False), ('state', '=', 'sale')]",
    )
    currency_id = fields.Many2one(
        related="settlement_id.currency_id",
    )
    base_amount = fields.Monetary(
        string="Base",
        compute="_compute_amounts",
        store=True,
        readonly=False,
        help="Order figure the commission was computed on, frozen when the "
        "line was created.",
    )
    commission_rate = fields.Float(
        string="Rate (%)",
        compute="_compute_amounts",
        store=True,
        readonly=False,
    )
    amount = fields.Monetary(
        string="Commission",
        compute="_compute_amounts",
        store=True,
        readonly=False,
    )
    _unique_order_per_settlement = models.Constraint(
        "UNIQUE(settlement_id, order_id)",
        "A sales order can only appear once in the same settlement.",
    )

    @api.depends("order_id", "settlement_id.commission_base")
    def _compute_amounts(self):
        for line in self:
            order = line.order_id
            if not order:
                line.base_amount = 0.0
                line.commission_rate = 0.0
                line.amount = 0.0
                continue
            line.commission_rate = order.commission_rate
            if line.settlement_id.commission_base == "margin":
                line.base_amount = order.margin
                line.amount = order.commission_amount_margin
            else:
                line.base_amount = order.amount_untaxed
                line.amount = order.commission_amount

    @api.constrains("order_id", "settlement_id")
    def _check_order_consistency(self):
        for line in self:
            if line.order_id.agent_id != line.settlement_id.agent_id:
                raise ValidationError(
                    _(
                        "Order %(order)s does not belong to the agent of this "
                        "settlement.",
                        order=line.order_id.name,
                    )
                )
            if line.order_id.currency_id != line.settlement_id.currency_id:
                raise ValidationError(
                    _(
                        "Order %(order)s is not in the settlement currency.",
                        order=line.order_id.name,
                    )
                )

    @api.constrains("order_id", "settlement_id")
    def _check_order_not_settled_twice(self):
        for line in self:
            if line.settlement_id.state == "cancelled":
                continue
            duplicate = self.search(
                [
                    ("id", "!=", line.id),
                    ("order_id", "=", line.order_id.id),
                    ("settlement_id.state", "!=", "cancelled"),
                ],
                limit=1,
            )
            if duplicate:
                raise ValidationError(
                    _(
                        "Order %(order)s is already settled in %(settlement)s.",
                        order=line.order_id.name,
                        settlement=duplicate.settlement_id.name,
                    )
                )
