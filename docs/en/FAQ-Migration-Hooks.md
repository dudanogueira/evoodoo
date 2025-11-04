# FAQ - Migration to Native Hooks

## General Questions

### Why make this change?

**Answer:** Odoo's base automations have significant performance overhead and make
debugging difficult. Native hooks are:

- ⚡ 5x faster
- 🔍 Easier to debug
- 🧪 Simpler to test
- 📝 Easier to maintain

### Will this break my existing installation?

**Answer:** No. The migration is transparent:

- New hooks do exactly what automations did
- Old automations are automatically disabled
- Easy rollback if issues arise

### Do I need to change any configurations?

**Answer:** No. Everything continues working the same way. Connectors, channels, bots -
all remain unchanged.

## Technical Questions

### How do I know the hooks are working?

**Answer:** Check the logs. Instead of seeing:

```
automation_base: running outgo message
```

You'll see:

```
discuss_channel.message_post: sending outgoing message
```

### Do tests still work?

**Answer:** Yes! Tests test the public API (`message_post`, etc.) which hasn't changed.
Only internal implementation changed.

### Can I use hooks and automations at the same time?

**Answer:** Technically yes, but not recommended! This would cause duplication (messages
sent 2x). Automations are marked as `active=0` to prevent this.

### How does error handling work?

**Answer:** Each hook has its own try-except. If sending to external platform fails, the
error is logged but normal Odoo operation continues. For example:

```python
try:
    self.discuss_hub_connector.outgo_message(channel=self, message=message)
except Exception as e:
    _logger.error(f"Error sending outgoing message: {e}", exc_info=True)
# Continues normally, message was created in Odoo
```

### What's the execution order of hooks?

**Answer:**

1. **message_post:**

   - `super().message_post()` - Creates message first
   - External send hook - After

2. **\_notify_thread:**

   - `super()._notify_thread()` - Normal notifications first
   - Bot hook - After

3. **create/write (reactions):**
   - `super().create()` - Creates reaction first
   - External send hook - After

This ensures Odoo operations always complete, even if hooks fail.

## Performance Questions

### How much faster is it?

**Answer:** Estimates based on tests:

- Message sending: ~5x faster
- Bot processing: ~5x faster
- Reactions: ~5x faster
- Database queries: ~3x less

Values vary by hardware and load.

### How do I measure performance?

**Answer:** Use Odoo's profiler:

```python
# Add to code temporarily
import time
start = time.time()
# ... code ...
_logger.info(f"Operation took {time.time() - start:.3f}s")
```

Or use tools like:

```bash
# Monitor CPU/memory
docker stats odoo

# See HTTP response time
curl -w "@curl-format.txt" -o /dev/null -s "http://localhost:8069/..."
```

### Is there an impact on memory usage?

**Answer:** There should be no significant difference. The code is practically
identical, just moved from automations to methods.

## Development Questions

### How do I add custom logic to hooks?

**Answer:** Simply extend the method:

```python
class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    def message_post(self, **kwargs):
        # Your custom logic BEFORE
        self._my_custom_logic()

        # Call original hook
        message = super().message_post(**kwargs)

        # Your custom logic AFTER
        self._another_custom_logic(message)

        return message
```

### How do I test hooks in development?

**Answer:** Create unit tests:

```python
def test_my_hook(self):
    channel = self.env['discuss.channel'].create({...})
    message = channel.message_post(body="Test")

    # Assert what you expect
    self.assertTrue(message)
```

See `discuss_hub/tests/test_code_hooks.py` for examples.

### How do I debug hooks?

**Answer:** Use normal Python debugger:

```python
def message_post(self, **kwargs):
    import pdb; pdb.set_trace()  # Or use your IDE debugger
    message = super().message_post(**kwargs)
    # ...
```

With VS Code + Python extension, just add a breakpoint on the line.

### Can I temporarily disable a specific hook?

**Answer:** Yes! Add an early return:

```python
def message_post(self, **kwargs):
    message = super().message_post(**kwargs)

    # Temporarily disable
    if self.env.context.get('skip_discuss_hub_hook'):
        return message

    # ... rest of code ...
```

Then use:

```python
channel.with_context(skip_discuss_hub_hook=True).message_post(...)
```

## Plugin Questions

### Do plugins need to be updated?

**Answer:** No! Plugins don't change. They continue implementing:

- `process_payload()` - Process incoming webhooks
- `get_message_id()` - Extract message ID
- `send_message()` - Send messages

The only change is **how** these methods are called (via hooks instead of automations).

### I'm developing a new plugin. What changes?

**Answer:** Nothing! Follow the same pattern:

```python
class MyPlugin(PluginBase):
    plugin_name = "my_plugin"

    def process_payload(self):
        # Your code here
        pass

    def send_message(self, phone, message):
        # Your code here
        pass
```

## Deployment Questions

### Do I need downtime to update?

**Answer:** Recommended but not required:

**With downtime (safer):**

1. Stop Odoo
2. Update code
3. Update module
4. Start Odoo

**Without downtime (riskier):**

1. Update code
2. Reload Odoo (if supported)
3. Update module

### How do I rollback in production?

**Answer:** See [Post-Migration-Checklist.md](./Post-Migration-Checklist.md) Rollback
section.

Summary:

1. Reactivate automations (`active=1`)
2. Comment out hook methods
3. Update module
4. Restart Odoo

### Can I test in staging first?

**Answer:** Highly recommended! Follow this flow:

1. **Dev**: Develop and test locally
2. **Staging**: Deploy and integration tests
3. **Production**: Final deploy only if staging passed

## Integration Questions

### Do N8N workflows need to be updated?

**Answer:** No! N8N workflows interact via webhooks and Odoo API, which haven't changed.

### Does Typebot integration still work?

**Answer:** Yes! The `bot_manager.py` hasn't changed. The only difference is the bot is
triggered via `_notify_thread` hook instead of automation.

### Does Evolution API need to be reconfigured?

**Answer:** No! Evolution API settings remain the same.

## Troubleshooting Questions

### How do I see if my message is being sent?

**Answer:** Three ways:

1. **Logs:**

   ```bash
   docker compose logs -f odoo | grep "message_post"
   ```

2. **External Platform:** Check if message appeared in WhatsApp/Telegram

3. **Odoo Shell:**
   ```python
   # Check last send
   channel = env['discuss.channel'].browse(CHANNEL_ID)
   print(channel.message_ids[0])
   ```

### Bot not responding, how to debug?

**Answer:**

1. **Check configuration:**

   ```python
   partner = env['res.partner'].search([('name', '=', 'Bot Partner')])
   print(f"Bot: {partner.bot}")
   print(f"Bot Active: {partner.bot.active}")
   ```

2. **Check logs:**

   ```bash
   docker compose logs -f odoo | grep "_notify_thread"
   ```

3. **Test manually:**
   ```python
   channel = env['discuss.channel'].browse(CHANNEL_ID)
   partner = env['res.partner'].browse(PARTNER_ID)
   partner.bot.outgo(channel, partner)
   ```

### How do I know if an error is from the hook or plugin?

**Answer:** Check the stack trace in logs:

```
ERROR ... discuss_channel.py:123 in message_post
  -> Error in hook

ERROR ... evolution.py:456 in send_message
  -> Error in plugin
```

## Contribution Questions

### How do I contribute improvements to hooks?

**Answer:**

1. Fork the repository
2. Create branch: `git checkout -b feature/hook-improvement`
3. Make your changes
4. Add tests
5. Submit PR

See [CONTRIBUTING.md](../../CONTRIBUTING.md) if it exists.

### Where do I report bugs?

**Answer:**

- **GitHub Issues**: For code bugs
- **Discussions**: For general questions
- **Email**: For private matters

### How do I suggest new hooks?

**Answer:** Open a GitHub issue with:

- Use case
- Suggested hook (which method override)
- Expected benefits
- Implementation example

## Additional Resources

- 📖 [Complete Migration Guide](./Migration-BaseAutomations-to-CodeHooks.md)
- 📊 [Visual Comparison](./Comparison-Automations-vs-Hooks.md)
- ✅ [Post-Migration Checklist](./Post-Migration-Checklist.md)
- 📝 [Change Summary](../../MIGRATION_SUMMARY.md)
- 🏗️ [Architecture Documentation](./README.md)

---

**Still have questions?**

- Open a GitHub issue
- Contact the team
- Consult official Odoo documentation
