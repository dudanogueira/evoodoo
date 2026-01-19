"""Simple test to verify test execution."""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("discuss_hub")
class TestSimple(TransactionCase):
    """Simple test case."""

    def test_simple_assertion(self):
        """Test that always passes."""
        print("\n" + "="*80)
        print("✅ SIMPLE TEST IS RUNNING!")
        print("="*80 + "\n")
        self.assertTrue(True, "This test should always pass")
