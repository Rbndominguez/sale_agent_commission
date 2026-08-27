from odoo.tests import tagged
from odoo.tools.safe_eval import safe_eval

from .common import CommissionCase


@tagged("post_install", "-at_install")
class TestSettlementReport(CommissionCase):
    """ADR-0004: printable in every state, stored as an attachment only once paid."""

    def setUp(self):
        super().setUp()
        self.order = self._create_order(self.agent_a)
        self.settlement = self._create_settlement(self.agent_a, self.order)
        self.report = self.env.ref(
            "sale_agent_commission.action_report_commission_settlement"
        )

    def _render(self):
        content, report_type = self.env["ir.actions.report"]._render_qweb_html(
            self.report.report_name, self.settlement.ids
        )
        self.assertEqual(report_type, "html")
        return content.decode() if isinstance(content, bytes) else content

    def _attachment_name(self):
        """Evaluate the `attachment` expression the way the report engine does."""
        return safe_eval(self.report.attachment, {"object": self.settlement})

    def test_the_template_renders_the_settlement(self):
        html = self._render()
        self.assertIn(self.settlement.name, html)
        self.assertIn(self.order.name, html)

    def test_a_draft_settlement_is_printed_with_a_warning(self):
        self.assertIn("Draft settlement.", self._render())

    def test_a_confirmed_settlement_has_no_warning(self):
        self.settlement.action_confirm()
        html = self._render()
        self.assertNotIn("Draft settlement.", html)
        self.assertNotIn("Cancelled settlement.", html)

    def test_nothing_is_stored_before_the_settlement_is_paid(self):
        self.assertFalse(self._attachment_name())
        self.settlement.action_confirm()
        self.assertFalse(self._attachment_name())
        self.settlement.action_mark_as_paid()
        self.assertTrue(self._attachment_name())

    def test_a_paid_settlement_is_stored_exactly_once(self):
        domain = [
            ("res_model", "=", "sale.commission.settlement"),
            ("res_id", "=", self.settlement.id),
        ]
        Report = self.env["ir.actions.report"]

        content, report_type = Report._render_qweb_pdf(
            self.report.report_name, self.settlement.ids
        )
        if report_type != "pdf":
            self.skipTest(
                "wkhtmltopdf did not produce a PDF in this run (got "
                f"'{report_type}'). This is expected without a running "
                "HTTP server, e.g. under --stop-after-init; it is not a "
                "sign that wkhtmltopdf itself is broken."
            )
        self.assertFalse(self.env["ir.attachment"].search(domain))

        self.settlement.action_confirm()
        self.settlement.action_mark_as_paid()
        content, report_type = Report._render_qweb_pdf(
            self.report.report_name, self.settlement.ids
        )
        self.assertEqual(report_type, "pdf")
        self.assertEqual(len(self.env["ir.attachment"].search(domain)), 1)

        again, _report_type = Report._render_qweb_pdf(
            self.report.report_name, self.settlement.ids
        )
        self.assertEqual(len(self.env["ir.attachment"].search(domain)), 1)
        self.assertEqual(again, content)
