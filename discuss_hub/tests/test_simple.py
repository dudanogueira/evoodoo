"""Simple test to verify test execution."""

import logging

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

_logger = logging.getLogger(__name__)


@tagged("discuss_hub")
class TestSimple(TransactionCase):
    """Simple test case."""

    def test_simple_assertion(self):
        """Test that always passes."""
        _logger.info("\n" + "=" * 80)
        _logger.info("✅ SIMPLE TEST IS RUNNING!")
        _logger.info("=" * 80 + "\n")
        self.assertTrue(True, "This test should always pass")
