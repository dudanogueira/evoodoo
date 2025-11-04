from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("discuss_hub", "bot_manager")
class TestBotManagerInactive(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create a simple channel and seed with one message
        cls.channel = cls.env["discuss.channel"].create(
            {
                "name": "Test Bot Channel",
                "channel_type": "group",
            }
        )
        # Create a partner to act as author and as the bot's partner link
        cls.partner = cls.env["res.partner"].create({"name": "Test Visitor"})

        # Post an initial message so outgo() can access channel.message_ids[0]
        cls.channel.message_post(
            body="<p>Incoming message</p>",
            author_id=cls.partner.id,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )

        # Create a bot manager marked as inactive, linked to a partner
        cls.bot_manager = cls.env["discuss_hub.bot_manager"].create(
            {
                "active": False,
                "bot_type": "generic",
                "bot_url": "http://localhost:9999/echo",
                "bot_api_key": "dummy",
                # Link at least one partner through o2m using commands
                "partner": [
                    (
                        0,
                        0,
                        {
                            "name": "Bot Partner",
                        },
                    )
                ],
            }
        )

    def test_outgo_not_triggered_when_inactive(self):
        # Ensure generic_handle is NOT called when bot is inactive
        with patch.object(
            type(self.bot_manager), "generic_handle", autospec=True
        ) as mock_generic:
            result = self.bot_manager.outgo(self.channel, self.partner)
            self.assertFalse(result, "outgo should return False when bot is inactive")
            mock_generic.assert_not_called()
