# Migration from Base Automations to Native Code Hooks

## Overview

This document describes the migration from Odoo base automations to native Python code
hooks for handling webhook integrations in Discuss Hub.

## Why This Change?

**Benefits of native code hooks:**

1. **Better Performance**: Direct method calls avoid the overhead of automation
   evaluation
2. **Easier Debugging**: Stack traces show exactly where code executes
3. **Better Control**: Explicit control flow instead of implicit automation triggers
4. **Easier Testing**: Can test methods directly without setting up automation context
5. **Code Maintainability**: All logic in Python files, easier to version control and
   review

**Previous Approach (Base Automations):**

- Required XML data files with automation rules
- Logic split between XML configuration and Python code snippets
- Harder to debug (automations fire implicitly)
- Performance overhead from automation engine evaluation

## Implementation Details

### 1. Outgoing Messages (discuss.channel)

**Before:** Base automation on `discuss.channel` with trigger `on_message_sent`

**After:** Override `message_post()` method in `discuss.channel` model

**Location:** `discuss_hub/models/discuss_channel.py`

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

**Key Points:**

- Always call `super().message_post()` first to maintain normal Odoo behavior
- Only process if channel has a `discuss_hub_connector`
- Wrap in try-except to prevent errors from breaking message posting
- Logging for debugging and monitoring

### 2. Bot Automation (discuss.channel)

**Before:** Base automation on `discuss.channel` with trigger `on_message_received`

**After:** Override `_notify_thread()` method in `discuss.channel` model

**Location:** `discuss_hub/models/discuss_channel.py`

```python
def _notify_thread(self, message, msg_vals=False, **kwargs):
    """
    Override _notify_thread to handle bot automation for incoming messages.
    This replaces the base automation for bot outgoing.
    """
    # Call parent method
    result = super()._notify_thread(message, msg_vals=msg_vals, **kwargs)

    # Handle bot automation
    partners_with_bot = self.channel_partner_ids.filtered(lambda p: p.bot)
    if partners_with_bot:
        try:
            _logger.info(
                f"discuss_channel._notify_thread: processing bot for {len(partners_with_bot)} partners"
            )
            for partner in partners_with_bot:
                partner.bot.outgo(self, partner)
        except Exception as e:
            _logger.error(f"Error processing bot automation: {e}", exc_info=True)

    return result
```

**Key Points:**

- `_notify_thread` is called when messages are received/processed
- Always call `super()._notify_thread()` first
- Filter partners with bots and process each one
- Error handling to prevent bot errors from breaking message flow

### 3. Outgoing Reactions (mail.message.reaction)

**Before:** Base automation on `mail.message.reaction` with trigger `on_create_or_write`

**After:** Override `create()` and `write()` methods in new model

**Location:** `discuss_hub/models/mail_message_reaction.py` (new file)

```python
@api.model_create_multi
def create(self, vals_list):
    """
    Override create to handle outgoing reactions.
    This replaces the base automation trigger on_create_or_write.
    """
    # Call parent method to create the reaction(s)
    reactions = super().create(vals_list)

    # Process each reaction for connector notification
    for reaction in reactions:
        if reaction.message_id and reaction.message_id.discuss_hub_message_id:
            try:
                channel = self.env["discuss.channel"].search(
                    [("id", "=", reaction.message_id.res_id)], limit=1
                )
                if channel and channel.discuss_hub_connector:
                    _logger.info(
                        f"mail_message_reaction.create: connector:{channel.discuss_hub_connector} "
                        f"channel:{channel} reaction {reaction} to message {reaction.message_id}"
                    )
                    channel.discuss_hub_connector.outgo_reaction(
                        channel, reaction.message_id, reaction
                    )
            except Exception as e:
                _logger.error(
                    f"Error sending outgoing reaction to connector: {e}",
                    exc_info=True,
                )

    return reactions
```

**Key Points:**

- Use `@api.model_create_multi` decorator for batch creation support
- Check if message has `discuss_hub_message_id` (indicates external message)
- Find the channel and connector before sending reaction
- Similar `write()` method for reaction updates

## Migration Steps

### For Existing Installations:

1. **Update the code:**

   ```bash
   git pull origin 18.0
   ```

2. **Restart Odoo:**

   ```bash
   docker compose -f compose-dev.yaml restart odoo
   ```

3. **Upgrade the module:**

   ```bash
   # Via UI: Apps -> Discuss Hub -> Upgrade
   # Or via CLI:
   docker compose -f compose-dev.yaml exec odoo odoo -u discuss_hub --stop-after-init
   ```

4. **Verify automations are disabled:**

   - Go to Settings -> Technical -> Automation -> Automated Actions
   - Search for "discuss_hub"
   - Verify all three automations show as "Inactive" or "DEPRECATED"

5. **Test functionality:**
   - Send a message from Odoo to external channel
   - Send a message from external channel to Odoo
   - Add a reaction to a message
   - Test bot responses

### For New Installations:

The code hooks are automatically active. The deprecated base automations are set to
`active=0` and won't interfere.

## Testing

### Manual Testing:

1. **Outgoing Messages:**

   ```
   1. Open a channel connected to discuss_hub connector
   2. Send a message
   3. Check logs for: "discuss_channel.message_post: sending outgoing message"
   4. Verify message appears in external platform (WhatsApp, Telegram, etc.)
   ```

2. **Bot Automation:**

   ```
   1. Configure a bot for a partner
   2. Send a message to a channel with that partner
   3. Check logs for: "discuss_channel._notify_thread: processing bot"
   4. Verify bot response is sent
   ```

3. **Reactions:**
   ```
   1. Find a message from external platform (has discuss_hub_message_id)
   2. Add a reaction in Odoo
   3. Check logs for: "mail_message_reaction.create: connector"
   4. Verify reaction appears in external platform
   ```

### Automated Testing:

Tests should continue to work without changes, as they test the public API
(`message_post`, reactions, etc.) which remains the same.

## Troubleshooting

### Messages not sending to external platform:

1. Check if channel has `discuss_hub_connector` set
2. Check logs for errors in `message_post` method
3. Verify connector is enabled and properly configured

### Bot not responding:

1. Check if partner has bot configured
2. Check logs for errors in `_notify_thread` method
3. Verify bot is active and properly configured

### Reactions not syncing:

1. Check if message has `discuss_hub_message_id` field populated
2. Check logs for errors in `mail_message_reaction.create` or `write`
3. Verify connector supports reactions

## Rollback (if needed)

If you need to rollback to base automations:

1. Edit `discuss_hub/datas/base_automation.xml` and set `active=1` for all automations
2. Comment out the override methods in:
   - `discuss_hub/models/discuss_channel.py` (`message_post` and `_notify_thread`)
   - `discuss_hub/models/mail_message_reaction.py` (entire file)
3. Restart Odoo and upgrade the module

## Performance Considerations

**Expected improvements:**

- Reduced CPU usage from automation engine evaluation
- Faster message posting (direct method call vs automation lookup)
- Reduced database queries (no automation domain evaluation)

**Monitoring:**

- Check Odoo logs for timing information
- Monitor memory usage (should be similar or better)
- Watch for any new errors in logs

## Future Enhancements

Possible improvements for the future:

1. **Async Processing:** Use Odoo's queue jobs for webhook calls to avoid blocking
2. **Batch Processing:** Batch multiple reactions/messages when possible
3. **Circuit Breaker:** Implement retry logic with exponential backoff
4. **Monitoring:** Add metrics collection for webhook success/failure rates

## References

- [Odoo Model Methods](https://www.odoo.com/documentation/18.0/developer/reference/backend/orm.html#model)
- [Message Posting](https://www.odoo.com/documentation/18.0/developer/reference/backend/mixins.html#mail-thread)
- [Automated Actions](https://www.odoo.com/documentation/18.0/applications/studio/automated_actions.html)
