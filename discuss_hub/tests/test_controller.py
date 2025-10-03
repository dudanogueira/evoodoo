"""Test suite for the HTTP controllers of discuss_hub.

This test suite covers the HTTP controller functionality including:
- Connector webhook endpoint (/discuss_hub/connector/<uuid>)
- Bot manager routing endpoint (/discuss_hub/routing/<uuid>)
- Active/inactive connector/bot_manager handling
- JSON payload validation and error handling
- Different HTTP methods (GET, POST)
- Different content types (application/json, form-encoded)
- Response format validation
- Edge cases and error scenarios
"""

import json
from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import HttpCase


@tagged("discuss_hub", "discuss_hub_controller")
class TestConnectorController(HttpCase):
    """Test cases for the /discuss_hub/connector/<uuid> endpoint."""

    @classmethod
    def setUpClass(cls):
        """Set up test data and environment."""
        super().setUpClass()
        cls.connector_uuid = "11111111-1111-1111-1111-111111111111"
        cls.connector = cls.env["discuss_hub.connector"].create(
            {
                "name": "Test Connector for Controller",
                "type": "evolution",
                "enabled": True,
                "uuid": cls.connector_uuid,
                "url": "http://evolution:8080",
                "api_key": "test_api_key_1234567890",
            }
        )

    def _send_connector_request(
        self, uuid_str, payload=None, headers=None, method="POST"
    ):
        """Helper method to send requests to the connector endpoint.

        Args:
            uuid_str: UUID string for the connector
            payload: Request payload (dict or str)
            headers: Optional HTTP headers
            method: HTTP method (default: POST)

        Returns:
            Response object
        """
        url = f"/discuss_hub/connector/{uuid_str}"
        if headers is None:
            headers = {"Content-Type": "application/json"}

        if isinstance(payload, dict):
            data = json.dumps(payload)
        else:
            data = payload

        if method == "GET":
            return self.url_open(url, headers=headers)
        else:
            return self.url_open(url, data=data, headers=headers)

    # ===================================================================
    # CONNECTOR ACTIVE/INACTIVE TESTS
    # ===================================================================

    def test_connector_active_returns_200(self):
        """Test that active connector processes requests successfully."""
        payload = {
            "key": "value",
            "another_key": 42,
        }
        response = self._send_connector_request(self.connector_uuid, payload)
        self.assertEqual(
            response.status_code,
            200,
            "Active connector should return 200 status code",
        )

    def test_connector_inactive_returns_404(self):
        """Test that inactive connector returns 404 Not Found."""
        # Deactivate the connector
        self.connector.write({"enabled": False})

        payload = {"key": "value"}
        response = self._send_connector_request(self.connector_uuid, payload)

        self.assertEqual(
            response.status_code,
            404,
            "Inactive connector should return 404 status code",
        )
        response_data = json.loads(response.text)
        self.assertEqual(
            response_data.get("message"),
            "Connector Not Found",
            "Response should contain appropriate error message",
        )

        # Re-enable for other tests
        self.connector.write({"enabled": True})

    def test_connector_nonexistent_uuid_returns_404(self):
        """Test that non-existent connector UUID returns 404."""
        nonexistent_uuid = "99999999-9999-9999-9999-999999999999"
        payload = {"key": "value"}
        response = self._send_connector_request(nonexistent_uuid, payload)

        self.assertEqual(
            response.status_code,
            404,
            "Non-existent connector should return 404 status code",
        )
        response_data = json.loads(response.text)
        self.assertEqual(response_data.get("message"), "Connector Not Found")

    # ===================================================================
    # JSON VALIDATION TESTS
    # ===================================================================

    def test_connector_invalid_json_returns_400(self):
        """Test that invalid JSON payload returns 400 Bad Request."""
        invalid_json = '{"name": discuss_hub}//'
        response = self._send_connector_request(
            self.connector_uuid, payload=invalid_json
        )

        self.assertEqual(
            response.status_code,
            400,
            "Invalid JSON should return 400 status code",
        )
        response_data = json.loads(response.text)
        self.assertEqual(
            response_data.get("message"),
            "Invalid JSON Payload",
            "Response should contain appropriate error message",
        )

    def test_connector_valid_json_payload(self):
        """Test that valid JSON payload is processed successfully."""
        # Use a simple payload that won't trigger complex plugin logic
        payload = {
            "test_event": "simple_test",
            "test_data": "value",
        }
        response = self._send_connector_request(self.connector_uuid, payload)

        # Should be accepted even if not fully processed (200 or other success code)
        self.assertIn(
            response.status_code,
            [200, 201, 202],
            "Valid JSON should be accepted by the controller",
        )

    def test_connector_empty_json_payload(self):
        """Test that empty JSON payload is handled correctly."""
        payload = {}
        response = self._send_connector_request(self.connector_uuid, payload)

        self.assertEqual(
            response.status_code,
            200,
            "Empty JSON payload should be accepted",
        )

    # ===================================================================
    # CONTENT TYPE TESTS
    # ===================================================================

    def test_connector_form_encoded_payload(self):
        """Test that form-encoded data is processed correctly."""
        # Simulate form-encoded data by not setting JSON content type
        response = self.url_open(
            f"/discuss_hub/connector/{self.connector_uuid}",
            data="key=value&another_key=42",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        self.assertEqual(
            response.status_code,
            200,
            "Form-encoded data should be processed successfully",
        )

    # ===================================================================
    # HTTP METHOD TESTS
    # ===================================================================

    def test_connector_get_method(self):
        """Test that GET method is supported."""
        response = self._send_connector_request(
            self.connector_uuid, payload=None, method="GET"
        )

        # GET method without proper payload may return 400 or be handled by plugin
        self.assertIn(
            response.status_code,
            [200, 400, 404],
            "GET method should be supported",
        )

    def test_connector_post_method(self):
        """Test that POST method works correctly."""
        payload = {"test": "data"}
        response = self._send_connector_request(
            self.connector_uuid, payload=payload, method="POST"
        )

        self.assertEqual(response.status_code, 200, "POST method should work correctly")

    # ===================================================================
    # RESPONSE FORMAT TESTS
    # ===================================================================

    def test_connector_response_is_json(self):
        """Test that response is in JSON format."""
        payload = {"key": "value"}
        response = self._send_connector_request(self.connector_uuid, payload)

        self.assertIn(
            "application/json",
            response.headers.get("Content-Type", ""),
            "Response should be in JSON format",
        )

    # ===================================================================
    # LOGGING TESTS
    # ===================================================================

    @patch("odoo.addons.discuss_hub.controllers.controllers._logger")
    def test_connector_logs_warning_on_not_found(self, mock_logger):
        """Test that warning is logged when connector is not found."""
        nonexistent_uuid = "99999999-9999-9999-9999-999999999999"
        payload = {"key": "value"}
        self._send_connector_request(nonexistent_uuid, payload)

        # Verify warning was logged
        mock_logger.warning.assert_called()
        call_args = str(mock_logger.warning.call_args)
        self.assertIn("connector_not_found", call_args)

    @patch("odoo.addons.discuss_hub.controllers.controllers._logger")
    def test_connector_logs_error_on_invalid_json(self, mock_logger):
        """Test that error is logged when JSON is invalid."""
        invalid_json = '{"invalid": json}'
        self._send_connector_request(self.connector_uuid, payload=invalid_json)

        # Verify error was logged
        mock_logger.error.assert_called()
        call_args = str(mock_logger.error.call_args)
        self.assertIn("json_decode_error", call_args)

    @patch("odoo.addons.discuss_hub.controllers.controllers._logger")
    def test_connector_logs_info_on_success(self, mock_logger):
        """Test that info is logged when payload is processed successfully."""
        payload = {"test": "data"}
        self._send_connector_request(self.connector_uuid, payload)

        # Verify info was logged
        mock_logger.info.assert_called()
        call_args = str(mock_logger.info.call_args)
        self.assertIn("incoming_payload", call_args)


@tagged("discuss_hub", "discuss_hub_controller")
class TestBotManagerController(HttpCase):
    """Test cases for the /discuss_hub/routing/<uuid> endpoint."""

    @classmethod
    def setUpClass(cls):
        """Set up test data and environment."""
        super().setUpClass()
        cls.bot_uuid = "22222222-2222-2222-2222-222222222222"

        # Create bot manager
        cls.bot_manager = cls.env["discuss_hub.bot_manager"].create(
            {
                "uuid": cls.bot_uuid,
                "active": True,
                "bot_type": "typebot",
                "bot_url": "https://typebot.example.com",
                "bot_api_key": "test_typebot_id",
            }
        )

        # Create a partner with bot
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Partner with Bot",
                "phone": "+5511999999999",
                "bot": cls.bot_manager.id,
            }
        )

    def _send_routing_request(
        self, uuid_str, payload=None, headers=None, method="POST"
    ):
        """Helper method to send requests to the bot manager routing endpoint.

        Args:
            uuid_str: UUID string for the bot manager
            payload: Request payload (dict or str)
            headers: Optional HTTP headers
            method: HTTP method (default: POST)

        Returns:
            Response object
        """
        url = f"/discuss_hub/routing/{uuid_str}"
        if headers is None:
            headers = {"Content-Type": "application/json"}

        if isinstance(payload, dict):
            data = json.dumps(payload)
        else:
            data = payload

        if method == "GET":
            return self.url_open(url, headers=headers)
        else:
            return self.url_open(url, data=data, headers=headers)

    # ===================================================================
    # BOT MANAGER ACTIVE/INACTIVE TESTS
    # ===================================================================

    def test_bot_manager_active_returns_200(self):
        """Test that active bot manager processes requests successfully."""
        payload = {
            "sessionId": "test_session",
            "message": "Hello bot",
        }
        response = self._send_routing_request(self.bot_uuid, payload)

        self.assertEqual(
            response.status_code,
            200,
            "Active bot manager should return 200 status code",
        )

    def test_bot_manager_inactive_returns_404(self):
        """Test that inactive bot manager returns 404 Not Found."""
        # Deactivate the bot manager
        self.bot_manager.write({"active": False})

        payload = {"message": "test"}
        response = self._send_routing_request(self.bot_uuid, payload)

        self.assertEqual(
            response.status_code,
            404,
            "Inactive bot manager should return 404 status code",
        )
        response_data = json.loads(response.text)
        self.assertEqual(
            response_data.get("message"),
            "Bot Manager Not Found",
            "Response should contain appropriate error message",
        )

        # Re-enable for other tests
        self.bot_manager.write({"active": True})

    def test_bot_manager_nonexistent_uuid_returns_404(self):
        """Test that non-existent bot manager UUID returns 404."""
        nonexistent_uuid = "88888888-8888-8888-8888-888888888888"
        payload = {"message": "test"}
        response = self._send_routing_request(nonexistent_uuid, payload)

        self.assertEqual(
            response.status_code,
            404,
            "Non-existent bot manager should return 404 status code",
        )
        response_data = json.loads(response.text)
        self.assertEqual(response_data.get("message"), "Bot Manager Not Found")

    # ===================================================================
    # JSON VALIDATION TESTS
    # ===================================================================

    def test_bot_manager_invalid_json_returns_400(self):
        """Test that invalid JSON payload returns 400 Bad Request."""
        invalid_json = '{"message": invalid_json}}'
        response = self._send_routing_request(self.bot_uuid, payload=invalid_json)

        self.assertEqual(
            response.status_code,
            400,
            "Invalid JSON should return 400 status code",
        )
        response_data = json.loads(response.text)
        self.assertEqual(
            response_data.get("message"),
            "Invalid JSON Payload",
            "Response should contain appropriate error message",
        )

    def test_bot_manager_valid_json_payload(self):
        """Test that valid JSON payload is processed successfully."""
        payload = {
            "sessionId": "abc123",
            "message": "Test message",
            "metadata": {"source": "webhook"},
        }
        response = self._send_routing_request(self.bot_uuid, payload)

        self.assertEqual(
            response.status_code, 200, "Valid JSON should be processed successfully"
        )

    def test_bot_manager_empty_json_payload(self):
        """Test that empty JSON payload is handled correctly."""
        payload = {}
        response = self._send_routing_request(self.bot_uuid, payload)

        self.assertEqual(
            response.status_code,
            200,
            "Empty JSON payload should be accepted",
        )

    # ===================================================================
    # CONTENT TYPE TESTS
    # ===================================================================

    def test_bot_manager_form_encoded_payload(self):
        """Test that form-encoded data is processed correctly."""
        response = self.url_open(
            f"/discuss_hub/routing/{self.bot_uuid}",
            data="message=test&sessionId=123",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        self.assertEqual(
            response.status_code,
            200,
            "Form-encoded data should be processed successfully",
        )

    # ===================================================================
    # HTTP METHOD TESTS
    # ===================================================================

    def test_bot_manager_get_method(self):
        """Test that GET method is supported."""
        response = self._send_routing_request(self.bot_uuid, payload=None, method="GET")

        # GET method without proper payload may return 400 or be handled by bot manager
        self.assertIn(
            response.status_code,
            [200, 400, 404],
            "GET method should be supported",
        )

    def test_bot_manager_post_method(self):
        """Test that POST method works correctly."""
        payload = {"message": "test"}
        response = self._send_routing_request(
            self.bot_uuid, payload=payload, method="POST"
        )

        self.assertEqual(response.status_code, 200, "POST method should work correctly")

    # ===================================================================
    # RESPONSE FORMAT TESTS
    # ===================================================================

    def test_bot_manager_response_is_json(self):
        """Test that response is in JSON format."""
        payload = {"message": "test"}
        response = self._send_routing_request(self.bot_uuid, payload)

        self.assertIn(
            "application/json",
            response.headers.get("Content-Type", ""),
            "Response should be in JSON format",
        )

    # ===================================================================
    # LOGGING TESTS
    # ===================================================================

    @patch("odoo.addons.discuss_hub.controllers.controllers._logger")
    def test_bot_manager_logs_warning_on_not_found(self, mock_logger):
        """Test that warning is logged when bot manager is not found."""
        nonexistent_uuid = "88888888-8888-8888-8888-888888888888"
        payload = {"message": "test"}
        self._send_routing_request(nonexistent_uuid, payload)

        # Verify warning was logged
        mock_logger.warning.assert_called()
        call_args = str(mock_logger.warning.call_args)
        self.assertIn("botmanager_not_found", call_args)

    @patch("odoo.addons.discuss_hub.controllers.controllers._logger")
    def test_bot_manager_logs_error_on_invalid_json(self, mock_logger):
        """Test that error is logged when JSON is invalid."""
        invalid_json = '{"invalid": json}'
        self._send_routing_request(self.bot_uuid, payload=invalid_json)

        # Verify error was logged
        mock_logger.error.assert_called()
        call_args = str(mock_logger.error.call_args)
        self.assertIn("json_decode_error", call_args)

    @patch("odoo.addons.discuss_hub.controllers.controllers._logger")
    def test_bot_manager_logs_info_on_success(self, mock_logger):
        """Test that info is logged when payload is processed successfully."""
        payload = {"message": "test"}
        self._send_routing_request(self.bot_uuid, payload)

        # Verify info was logged
        mock_logger.info.assert_called()
        call_args = str(mock_logger.info.call_args)
        self.assertIn("incoming_payload", call_args)
