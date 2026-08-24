from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SaleCommissionSettlement(models.Model):
    _name = "sale.commission.settlement"
    _description = "Agent Commission Settlement"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_to desc, name desc"

    name = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("New"),
    )
    agent_id = fields.Many2one(
        comodel_name="res.users",
        string="Agent",
        required=True,
        domain=[("commission_agent", "=", True)],
        tracking=True,
    )
    date_from = fields.Date(string="From", required=True, tracking=True)
    date_to = fields.Date(string="To", required=True, tracking=True)
    commission_base = fields.Selection(
        selection=[
            ("untaxed", "Untaxed amount"),
            ("margin", "Margin"),
        ],
        string="Commission base",
        required=True,
        default="untaxed",
        tracking=True,
        help="Which commission figure of the order this settlement pays.",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id",
        store=True,
    )
    line_ids = fields.One2many(
        comodel_name="sale.commission.settlement.line",
        inverse_name="settlement_id",
        string="Settled orders",
    )
    amount_total = fields.Monetary(
        string="Total",
        compute="_compute_amount_total",
        store=True,
        tracking=True,
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("paid", "Paid"),
            ("cancelled", "Cancelled"),
        ],
        required=True,
        default="draft",
        copy=False,
        tracking=True,
    )

    _check_period = models.Constraint(
        "CHECK(date_to >= date_from)",
        "A settlement cannot end before it starts.",
    )

    @api.depends("line_ids.amount")
    def _compute_amount_total(self):
        for settlement in self:
            settlement.amount_total = sum(settlement.line_ids.mapped("amount"))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "sale.commission.settlement"
                ) or _("New")
        return super().create(vals_list)

    def _ensure_state(self, allowed_states):
        """Raise if any record in self is not in one of allowed_states."""
        wrong = self.filtered(lambda s: s.state not in allowed_states)
        if wrong:
            raise UserError(
                _(
                    "This action is not allowed on the following settlements, "
                    "given their current state: %(names)s",
                    names=", ".join(wrong.mapped("name")),
                )
            )

    def action_confirm(self):
        self._ensure_state(("draft",))
        empty = self.filtered(lambda s: not s.line_ids)
        if empty:
            raise UserError(
                _(
                    "A settlement cannot be confirmed without any line: %(names)s",
                    names=", ".join(empty.mapped("name")),
                )
            )
        self.write({"state": "confirmed"})

    def action_mark_as_paid(self):
        self._ensure_state(("confirmed",))
        self.write({"state": "paid"})

    def action_cancel(self):
        self._ensure_state(("draft", "confirmed"))
        self.write({"state": "cancelled"})

    def action_reset_to_draft(self):
        self._ensure_state(("cancelled",))
        self.write({"state": "draft"})

    @api.ondelete(at_uninstall=False)
    def _unlink_except_draft_or_cancelled(self):
        blocked = self.filtered(lambda s: s.state not in ("draft", "cancelled"))
        if blocked:
            raise UserError(
                _(
                    "Only draft or cancelled settlements can be deleted: %(names)s",
                    names=", ".join(blocked.mapped("name")),
                )
            )