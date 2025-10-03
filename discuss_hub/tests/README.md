# Discuss Hub Tests

This directory contains the automated tests for the Discuss Hub module.

## Test Structure

Tests are organized as follows:

- `test_models.py`: Unit tests for core models
- `test_controller.py`: Tests for HTTP controllers and webhook endpoints
- `test_routing_manager.py`: Tests for message routing strategies
- `test_base.py`: Base plugin tests and shared utilities
- `test_base_extra.py`: Additional base plugin tests
- `test_evolution.py`: Comprehensive tests for the Evolution plugin
- `test_example.py`: Example plugin tests
- `test_utils.py`: Utility function tests

## Running the Tests

To run the tests, use Odoo's test framework:

```bash
python3 odoo-bin -d YOUR_DATABASE -i discuss_hub --test-enable --stop-after-init
```

## Test Tags

The test suite uses the following tags:

- `discuss_hub`: General module tests
- `connector`: Connector-specific tests
- `plugin_base`: Base plugin functionality tests
- `plugin_evolution`: Evolution plugin-specific tests
- `integration`: Integration tests that may require external services to be mocked

## Running the Tests

### Run All Tests

To run all tests in the module:

```bash
# Using Docker Compose (recommended for development)
docker exec odoo odoo -d test_db -i discuss_hub --test-enable --stop-after-init

# Or using pytest (if configured)
docker exec odoo python -m pytest /mnt/extra-addons/discuss_hub/tests/
```

### Run Specific Test Files

```bash
# Run only evolution plugin tests
docker exec odoo odoo -d test_db --test-tags discuss_hub,plugin_evolution --test-enable --stop-after-init

# Run only base plugin tests
docker exec odoo odoo -d test_db --test-tags discuss_hub,plugin_base --test-enable --stop-after-init

# Run controller tests
docker exec odoo odoo -d test_db --test-tags discuss_hub,controller --test-enable --stop-after-init
```

### Run Individual Test Classes

```bash
# Run specific test class
docker exec odoo python -m pytest /mnt/extra-addons/discuss_hub/tests/test_evolution.py::TestEvolutionPlugin

# Run specific test method
docker exec odoo python -m pytest /mnt/extra-addons/discuss_hub/tests/test_evolution.py::TestEvolutionPlugin::test_get_status_connected
```

## Best Practices

When adding or modifying tests, follow these guidelines:

### General Guidelines

1. **Mock External Services**: Always mock calls to Evolution API, N8N, or other
   external services
2. **Isolated Tests**: Keep unit tests independent - no shared state between tests
3. **Clear Documentation**: Document test scenarios with descriptive names and
   docstrings
4. **Deterministic Tests**: Tests should produce the same results every run (no
   randomness or external dependencies)
5. **Both Paths**: Cover both success and error/edge cases for each function

### Evolution Plugin Testing Patterns

```python
# Example: Mocking Evolution API responses
@patch('requests.Session.post')
def test_send_message(self, mock_post):
    mock_response = Mock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"key": {"id": "msg123"}}
    mock_post.return_value = mock_response

    result = self.plugin.send_text_message(channel, message)
    self.assertIsNotNone(result)
```

### Test Data Setup

- Use `setUpClass` for test fixtures that don't change
- Create minimal test data needed for each test
- Clean up created records if needed (though TransactionCase handles rollback)
- Use descriptive names for test partners, channels, etc.

### Assertions

- Use specific assertions (`assertEqual`, `assertTrue`, etc.) over generic `assert`
- Check both the return value and side effects (database changes, message creation)
- Verify error messages contain expected content
- Assert on the presence of expected data structures

### Tags

Tag your tests appropriately for selective execution:

```python
@tagged("discuss_hub", "plugin_evolution", "message_processing")
class TestEvolutionMessageProcessing(HttpCase):
    pass
```

## Test Coverage

### Evolution Plugin Test Coverage

The `test_evolution.py` file provides comprehensive coverage for the Evolution plugin:

#### Initialization & Configuration (8 tests)

- Plugin initialization and connector reference
- Evolution URL configuration (from connector and environment)
- Request session creation with API key handling

#### Status Management (6 tests)

- Connected, disconnected, and QR code states
- Automatic instance creation on 404
- Unauthorized and error handling
- JSON parsing errors

#### Contact & Message Identifiers (8 tests)

- Contact identifier extraction from various payload structures
- Brazilian mobile number formatting
- Contact name resolution with fallbacks
- Channel name generation (individual and group chats)
- Message ID extraction from different payload formats

#### Administrative Events (5 tests)

- QR code updates with attachment creation
- Connection state changes (connecting, open, closed)
- Logout events
- Manager channel notifications
- Missing manager channel handling

#### Message Processing (12 tests)

- Text messages (individual and group chats)
- Quoted/replied messages
- Reactions with notification options
- Image, video, audio messages with attachments
- Location messages with Google Maps links
- Document messages with file handling
- Contact messages with vCard data

#### Outgoing Messages (6 tests)

- Text message sending with success/failure handling
- Quoted message support
- Attachment sending (images, documents)
- Request exception handling

#### Message Updates & Deletion (4 tests)

- Read receipt processing with channel member updates
- Read receipts toggle (enabled/disabled)
- Message deletion with strikethrough formatting
- Deletion notification messages

#### Contact Synchronization (3 tests)

- Bulk contact sync from Evolution API
- Contact upsert event processing
- Profile picture fetching from URL and API

#### Payload Routing (8 tests)

- Event routing to appropriate handlers
- Contact import toggle behavior
- Unknown event handling

#### Error Handling (9 tests)

- Missing remoteJid
- Partner creation failures
- Channel creation failures
- Network errors in send operations
- Message not found scenarios

**Total Evolution Plugin Tests: 69**

### Other Test Files Coverage

- **test_base.py**: Base plugin functionality, partner/channel creation, profile
  pictures
- **test_base_extra.py**: Extended base plugin scenarios
- **test_controller.py**: Webhook endpoint handling, payload validation
- **test_routing_manager.py**: Round-robin and random routing strategies
- **test_utils.py**: Utility functions (HTML to WhatsApp conversion, strikethrough,
  etc.)
- **test_models.py**: Core model functionality
- **test_example.py**: Example plugin reference implementation

### Critical Areas Covered

✅ **Webhook Processing**: Complete coverage of all Evolution webhook events ✅
**Message Routing**: Routing strategies and assignment logic ✅ **Contact
Synchronization**: Profile pictures, contact creation, Brazilian number formatting ✅
**Error Handling**: Network errors, missing data, invalid payloads ✅ **Message Types**:
Text, images, videos, audio, documents, locations, contacts, reactions ✅
**Administrative Events**: QR codes, connection states, logout ✅ **Outgoing Messages**:
Text, attachments, quoted messages

## Debugging Tests

### Viewing Test Output

When tests fail, Odoo provides detailed error messages. To see more verbose output:

```bash
# Add log level for more details
docker exec odoo odoo -d test_db --test-tags discuss_hub,plugin_evolution --test-enable --stop-after-init --log-level=test:DEBUG
```

### Common Issues

**Issue: "Module not found" errors**

- Ensure the module is properly installed: `-i discuss_hub`
- Check that all dependencies are installed

**Issue: "Database does not exist"**

- Create a test database first or use an existing one
- The database will be modified during tests (use a dedicated test DB)

**Issue: Mock objects not working**

- Verify the import path in `@patch` decorators matches the actual import in the code
- Use `patch.object()` for instance methods

**Issue: Transaction errors**

- Tests using `HttpCase` or `TransactionCase` automatically handle rollback
- Don't manually commit in tests unless absolutely necessary

### Test Debugging Tips

1. **Add print statements** (will show in test output):

   ```python
   print(f"DEBUG: payload = {payload}")
   ```

2. **Use breakpoints** with pdb (if running interactively):

   ```python
   import pdb; pdb.set_trace()
   ```

3. **Check created records**:

   ```python
   partners = self.env['res.partner'].search([])
   print(f"Found {len(partners)} partners")
   ```

4. **Inspect mock calls**:
   ```python
   print(f"Mock called {mock_post.call_count} times")
   print(f"Call args: {mock_post.call_args}")
   ```

## Contributing

When contributing new tests:

1. **Follow naming conventions**: `test_<feature>_<scenario>`
2. **Add docstrings**: Explain what the test validates
3. **Group related tests**: Use test classes to organize related functionality
4. **Update this README**: Document new test files or significant test additions
5. **Run tests locally**: Verify all tests pass before submitting PR

## Continuous Integration

The test suite is designed to run in CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run Discuss Hub Tests
  run: |
    docker exec odoo odoo -d test_db -i discuss_hub --test-enable --stop-after-init
```

### Coverage Reports

To generate test coverage reports (if coverage.py is installed):

```bash
docker exec odoo coverage run --source=/mnt/extra-addons/discuss_hub odoo -d test_db --test-tags discuss_hub --test-enable --stop-after-init
docker exec odoo coverage report
docker exec odoo coverage html  # Generate HTML report
```

---

**Last Updated**: October 2025 **Test Count**: 69 Evolution plugin tests + additional
tests in other files **Maintained By**: Discuss Hub Team
