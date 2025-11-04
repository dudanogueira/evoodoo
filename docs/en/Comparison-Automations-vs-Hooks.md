# Visual Comparison: Base Automations vs Native Hooks

## Before: Base Automations ❌

```mermaid
sequenceDiagram
    participant User as User
    participant Odoo as Odoo Core
    participant AutoEngine as Automation Engine
    participant AutoRule as Base Automation
    participant Connector as Discuss Hub Connector
    participant External as External Platform

    User->>Odoo: Sends message
    Odoo->>Odoo: message_post()
    Odoo->>Odoo: Creates message
    Odoo-->>AutoEngine: Triggers on_message_sent event
    AutoEngine->>AutoEngine: Evaluates all automations
    AutoEngine->>AutoRule: Finds discuss_hub rule
    AutoRule->>AutoRule: Checks domain
    AutoRule->>AutoRule: Executes Python code
    AutoRule->>Connector: outgo_message()
    Connector->>External: Sends via API

    Note over AutoEngine,AutoRule: Overhead: rule evaluation,<br/>domains, actions
```

**Problems:**

- 🐌 Performance: Evaluation of all automations on every event
- 🔍 Hard to debug: Stack trace goes through automation engine
- 📄 Scattered code: XML + Python snippets
- 🧪 Complex tests: Need to setup automations

---

## After: Native Hooks ✅

```mermaid
sequenceDiagram
    participant User as User
    participant Channel as Discuss Channel
    participant Connector as Discuss Hub Connector
    participant External as External Platform

    User->>Channel: Sends message
    Channel->>Channel: message_post()
    Note over Channel: Native override
    Channel->>Channel: super().message_post()
    Channel->>Channel: Creates message
    Channel->>Channel: if self.discuss_hub_connector
    Channel->>Connector: outgo_message()
    Connector->>External: Sends via API

    Note over Channel,Connector: Direct and simple:<br/>no intermediate overhead
```

**Benefits:**

- ⚡ Performance: Direct method call
- 🔍 Easy debugging: Clean stack trace
- 📝 Centralized code: Everything in Python
- 🧪 Simple tests: Test methods directly

---

## Detailed Comparison

### 1. Outgoing Messages

| Aspect          | Base Automation           | Native Hook               |
| --------------- | ------------------------- | ------------------------- |
| **Trigger**     | `on_message_sent` event   | `message_post()` override |
| **Location**    | XML + Python snippet      | `discuss_channel.py`      |
| **Performance** | ~10-50ms overhead         | ~0ms overhead             |
| **Stack trace** | 8-12 frames               | 3-5 frames                |
| **Testability** | Need to create automation | Test method directly      |

### 2. Bot Automation

| Aspect          | Base Automation             | Native Hook                 |
| --------------- | --------------------------- | --------------------------- |
| **Trigger**     | `on_message_received` event | `_notify_thread()` override |
| **Location**    | XML + Python snippet        | `discuss_channel.py`        |
| **Filter**      | Domain filter               | Python code                 |
| **Flexibility** | Limited to domains          | Custom logic                |

### 3. Reactions

| Aspect            | Base Automation            | Native Hook                  |
| ----------------- | -------------------------- | ---------------------------- |
| **Trigger**       | `on_create_or_write` event | `create()/write()` overrides |
| **Location**      | XML + Python snippet       | `mail_message_reaction.py`   |
| **Batch support** | Limited                    | `@api.model_create_multi`    |
| **Control**       | Implicit                   | Explicit                     |

---

## Complete Data Flow

### Message: External → Odoo

```mermaid
graph LR
    A[WhatsApp] -->|Webhook| B[Controller]
    B -->|process_payload| C[Plugin]
    C -->|create_message| D[Discuss Channel]
    D -->|_notify_thread HOOK| E{Has Bot?}
    E -->|Yes| F[Bot Manager]
    E -->|No| G[Normal Flow]
    F -->|Auto Reply| D
    D -->|message_post HOOK| H[Connector]
    H -->|Send| A
```

### Message: Odoo → External

```mermaid
graph LR
    A[User] -->|Types| B[Odoo UI]
    B -->|message_post| C[Discuss Channel]
    C -->|HOOK Override| D{Has Connector?}
    D -->|Yes| E[Connector]
    D -->|No| F[Normal Flow]
    E -->|outgo_message| G[Plugin]
    G -->|API Call| H[WhatsApp]
```

### Reaction: Odoo → External

```mermaid
graph LR
    A[User] -->|Adds Reaction| B[Odoo UI]
    B -->|create| C[Mail Message Reaction]
    C -->|HOOK Override| D{External Message?}
    D -->|Yes| E[Find Channel]
    D -->|No| F[Normal Flow]
    E -->|Has Connector?| G[Connector]
    G -->|outgo_reaction| H[Plugin]
    H -->|API Call| I[WhatsApp]
```

---

## Performance Metrics (Estimated)

| Operation    | Base Automation | Native Hook | Improvement     |
| ------------ | --------------- | ----------- | --------------- |
| Send message | 50-100ms        | 10-20ms     | **5x faster**   |
| Process bot  | 30-60ms         | 5-10ms      | **5x faster**   |
| Add reaction | 40-80ms         | 8-15ms      | **5x faster**   |
| DB Queries   | 8-12            | 2-4         | **3x less**     |
| CPU overhead | High            | Low         | **Significant** |

_Note: Estimated values, vary by hardware and load_

---

## Code Example: Before vs After

### Before (Base Automation XML)

```xml
<record model="base.automation" id="rule_discuss_hub_outgo_message">
    <field name="name">discuss_hub message outgo</field>
    <field name="model_id" ref="mail.model_discuss_channel" />
    <field name="active">1</field>
    <field name="trigger">on_message_sent</field>
    <field name="filter_domain">[("discuss_hub_connector", "!=", False)]</field>
</record>
<record model="ir.actions.server" id="discuss_hub_outgo_message">
    <field name="name">discuss_hub outgo message</field>
    <field name="state">code</field>
    <field name="code">
last_message = record.message_ids[0]
_logger.info(f"automation_base: running outgo message ({last_message}) to {record}")
record.discuss_hub_connector.outgo_message(channel=record, message=last_message)
    </field>
</record>
```

### After (Native Hook Python)

```python
@api.returns("mail.message", lambda value: value.id)
def message_post(self, **kwargs):
    """
    Override message_post to handle outgoing messages to external connectors.
    This replaces the base automation for outgoing messages.
    """
    # Call the parent method first to create the message
    message = super().message_post(**kwargs)

    # Handle outgoing message to connector
    if self.discuss_hub_connector and message:
        try:
            _logger.info(
                f"discuss_channel.message_post: sending outgoing message ({message}) to {self}"
            )
            self.discuss_hub_connector.outgo_message(channel=self, message=message)
        except Exception as e:
            _logger.error(
                f"Error sending outgoing message to connector: {e}", exc_info=True
            )

    return message
```

**Advantages:**

- ✅ Pure Python code
- ✅ Type hints possible
- ✅ IDE autocomplete
- ✅ Easy refactoring
- ✅ Readable git diff
- ✅ Explicit error handling
