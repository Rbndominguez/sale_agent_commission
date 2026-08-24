from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    commission_agent = fields.Boolean(
        string="Commission Agent",
        help="Make this user selectable as an agent on sales orders.",
    )
    commission_rate = fields.Float(
        string="Default Commission Rate (%)",
        digits=(5, 2),
        help="Rate proposed on new sales orders assigned to this agent.",
    )

    _commission_rate_range = models.Constraint(
        "CHECK(commission_rate >= 0 AND commission_rate <= 100)",
        "The commission rate must be between 0 and 100.",
    )