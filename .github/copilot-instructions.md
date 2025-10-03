# Discuss Hub - AI Coding Assistant Instructions

## Architecture Overview

Discuss Hub is an Odoo 18.0 addon that integrates third-party messaging channels (WhatsApp, Telegram, etc.) into Odoo's Discuss system through a **plugin-based architecture**.

### Core Components

- **`discuss_hub.connector`**: Central hub managing external message providers via webhooks
- **Plugin System**: Modular plugins in `models/plugins/` (base.py, evolution.py, whatsapp_cloud.py, etc.)
- **Routing Manager**: `models/routing_manager.py` handles message routing to agents via round-robin/random strategies
- **Bot Manager**: `models/bot_manager.py` manages automated responses (generic, typebot integration)
- **HTTP Controller**: `controllers/controllers.py` handles webhook endpoints at `/discuss_hub/connector/<uuid>`

### Data Flow
```
External Webhook → Controller → Connector → Plugin → process_payload() → Discuss Channel → Mail Message
```

## Development Workflow

### Quick Start
```bash
# Development environment uses Docker Compose
docker compose -f compose-dev.yaml up -d
sleep 30
# Load N8N workflows for automation
docker compose -f compose-dev.yaml exec -u node -it n8n sh -c "n8n import:workflow --input=/n8n-workflows.yaml"
docker compose -f compose-dev.yaml exec -u node -it n8n sh -c "n8n update:workflow --all --active=true"
docker compose -f compose-dev.yaml restart n8n
```

### Testing
- Tests use `@tagged("discuss_hub", "plugin_name")` decorators
- Base test class: `HttpCase` from `odoo.tests.common`
- Run specific tests: `docker exec odoo python -m pytest discuss_hub/tests/test_*.py`
- Test data in `demo/demo.xml`, security in `security/ir.model.access.csv`

## Plugin Development Patterns

### Plugin Structure
All plugins inherit from `models/plugins/base.py`:
```python
class Plugin(PluginBase):
    plugin_name = "your_plugin_name"
    
    def process_payload(self):
        # Main message processing logic
        
    def get_message_id(self, payload):
        # Extract unique message identifier
        
    def get_contact_identifier(self, payload):
        # Extract sender identifier (phone, user_id, etc.)
```

### Key Plugin Methods
- `process_payload()`: Core method that processes incoming webhook data
- `get_status()`: Returns connection status, may include QR code for authentication
- `get_contact_name()`: Extracts sender display name
- `send_message()`: Sends outbound messages via the external API

### Evolution Plugin Specifics
- Uses WhatsApp Business API via Evolution API
- QR code authentication flow handled in `get_status()`
- Instance management: creates instances automatically on 404 responses
- Media handling: downloads and processes images/documents via `process_media()`

## Configuration Patterns

### Environment Variables
```python
# Common patterns in plugins
self.evolution_url = os.getenv("DISCUSS_HUB_EVOLUTION_URL", "http://evolution:8080")
base_url = os.getenv("DISCUSS_HUB_INTERNAL_HOST") or self.connector.env["ir.config_parameter"].sudo().get_param("web.base.url")
```

### Connector Configuration
- Each connector has `uuid`, `name`, `type`, `enabled` fields
- Webhook URLs: `{base_url}/discuss_hub/connector/{uuid}`
- Plugin type must match filename in `models/plugins/`

## Odoo Integration Patterns

### Model Relationships
- `res.partner.bot`: One2many to `discuss_hub.bot_manager`
- `discuss.channel`: Extended with routing and bot capabilities  
- `mail.message`: Enhanced for external message handling

### Automation Integration
- Base automation triggered on `discuss.channel` incoming messages
- Domain filter: `[("channel_partner_ids.bot", "!=", False)]`
- N8N workflows handle complex automation scenarios

### Security Considerations
- All webhook endpoints use `auth="public"` with UUID-based authentication
- Connector lookup: `search([("enabled", "=", True), ("uuid", "=", str(identifier))])`
- Always use `.sudo(flag=True)` for webhook operations

## Code Quality Standards

### Error Handling
```python
# Prefer specific exception handling
try:
    response = self.session.get(url, timeout=10)
except requests.exceptions.RequestException as e:
    _logger.error(f"API request failed: {e}")
    return {"status": "error", "message": str(e)}
```

### Logging Patterns
```python
_logger.debug(f"Processing payload for connector: {self.connector.name}")
_logger.warning(f"action:connector_not_found identifier:{identifier}")
_logger.error(f"action:json_decode_error payload:{payload}")
```

### File Locations
- Models: `discuss_hub/models/`
- Controllers: `discuss_hub/controllers/`  
- Tests: `discuss_hub/tests/` with `test_*.py` naming
- Views: `discuss_hub/views/`
- Security: `discuss_hub/security/`
- Static assets: `discuss_hub/static/src/js/`

## Branch Strategy
- Main development: `18.0` branch
- Feature branches: `melhorias/feature-name` or `feature/feature-name`
- Current active branch: `melhorias/qualidade-codigo`