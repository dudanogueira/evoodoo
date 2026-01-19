import json

from odoo.tests import tagged
from odoo.tests.common import HttpCase


@tagged("discuss_hub", "plugin_base")
class TestExamplePlugin(HttpCase):
    @classmethod
    def setUpClass(cls):
        # add env on cls and many other things
        super().setUpClass()
        # create a connector
        cls.connector = cls.env["discuss_hub.connector"].create(
            {
                "name": "test_example_plugin",
                "type": "example",
                "enabled": True,
                "uuid": "11111111-1111-1111-1111-111111111112",
                "url": "http://example.com",
                "api_key": "1234567890",
            }
        )
        cls.plugin = cls.connector.get_plugin()

    def test_example_plugin_new_message(self):
        """
        Test the example plugin with a new message
        """
        # create a payload
        payload = {
            "message_id": "4567",
            "message_type": "text",
            "message": "Hello World",
            "contact_name": "John Doe",
            "contact_identifier": "1234567890",
            "profile_picture": "https://cataas.com/cat",
        }
        response = self.url_open(
            f"/discuss_hub/connector/{self.connector.uuid}",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        data = response.json()
        # get new message id
        message_id = payload.get("message_id")
        # check if message with same id exists
        message = self.env["mail.message"].search(
            [
                ("discuss_hub_message_id", "=", message_id),
            ],
            limit=1,
        )
        # assert the message
        assert message, "Message should be created"
        assert message.discuss_hub_message_id == message_id, "Message id should match"
        assert payload["message"] in message.body, "Message body should match"
        # assert the response
        assert data["success"] is True, "Response should be successful"
        assert data["status"] == "success", "Response status should be success"
