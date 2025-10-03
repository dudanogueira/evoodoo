# Discuss Hub Tests

This directory contains the automated tests for the Discuss Hub module.

## Test Structure

Tests are organized as follows:

- `test_models.py`: Unit tests for core models
- `test_controller.py`: Tests for HTTP controllers
- `test_routing_manager.py`: Tests specific to the routing system
- `test_base.py`: Base tests and shared utilities

## Running the Tests

To run the tests, use Odoo's test framework:

```bash
python3 odoo-bin -d YOUR_DATABASE -i discuss_hub --test-enable --stop-after-init
```

## Test Tags

The test suite uses the following tags:

- `discuss_hub`: General module tests
- `connector`: Connector-specific tests
- `integration`: Integration tests that may require external services to be mocked

## Best Practices

When adding or modifying tests, follow these guidelines:

1. Mock external services (Evolution API, etc.)
2. Keep unit tests isolated from each other
3. Document test scenarios with clear comments
4. Ensure tests are deterministic (no reliance on external state)
5. Cover both success and error cases

## Test Coverage

Critical areas that should be well tested:

- Webhook processing
- Message routing
- Contact synchronization
- Error handling
