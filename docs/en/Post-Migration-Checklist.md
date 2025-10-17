# Post-Migration Checklist

Use this checklist to verify that the migration from base automations to native hooks
was successful.

## Pre-Migration Preparation

### Backup

- [ ] Database backup created
- [ ] Code repository committed
- [ ] Git tag created (e.g., `pre-hooks-migration`)
- [ ] Rollback plan documented and tested

### Environment

- [ ] Staging environment available
- [ ] Monitoring tools ready
- [ ] Log aggregation configured
- [ ] Alert system active

## Deployment Steps

### 1. Code Update

- [ ] Pull latest code: `git pull origin 18.0`
- [ ] Verify branch: `git branch` shows correct branch
- [ ] Check for conflicts: `git status` is clean
- [ ] Review changes: `git log` shows migration commits

### 2. Module Update

- [ ] Stop Odoo (if full restart needed)
- [ ] Update module: `odoo -u discuss_hub --stop-after-init`
- [ ] Check for update errors in logs
- [ ] Restart Odoo service
- [ ] Verify Odoo starts successfully

### 3. Automation Verification

- [ ] Navigate to: Settings → Technical → Automation → Automated Actions
- [ ] Search for: "discuss_hub"
- [ ] Verify 3 automations exist:
  - [ ] `discuss_hub message outgo (DEPRECATED)` - Active: ❌
  - [ ] `discuss_hub reaction outgo (DEPRECATED)` - Active: ❌
  - [ ] `discuss_hub bot outgo (DEPRECATED)` - Active: ❌
- [ ] Confirm all show "DEPRECATED" in name
- [ ] Confirm all are inactive (Active = False)

## Functional Testing

### Test 1: Outgoing Messages (Odoo → External)

**Objective:** Verify messages are sent from Odoo to external platforms

- [ ] Open a channel connected to discuss_hub connector
- [ ] Send a test message: "Test outgoing message"
- [ ] **Expected in logs:**
  ```
  discuss_channel.message_post: sending outgoing message
  ```
- [ ] **Expected result:** Message appears in external platform (WhatsApp, Telegram,
      etc.)
- [ ] **NOT expected in logs:**
  ```
  automation_base: running outgo message
  ```

**Status:** ✅ Pass / ❌ Fail

**Notes:**

```
[Your notes here]
```

---

### Test 2: Incoming Messages (External → Odoo)

**Objective:** Verify messages are received from external platforms

- [ ] Send a message from external platform (WhatsApp, Telegram)
- [ ] **Expected result:** Message appears in Odoo channel
- [ ] **Expected in logs:**
  ```
  process_payload: processing message from external
  ```
- [ ] Message content matches
- [ ] Sender identified correctly
- [ ] Timestamp correct

**Status:** ✅ Pass / ❌ Fail

**Notes:**

```
[Your notes here]
```

---

### Test 3: Bot Automation

**Objective:** Verify bot responds to messages

**Prerequisites:**

- [ ] Partner with bot configured exists
- [ ] Bot is active

**Test steps:**

- [ ] Send message to channel with bot partner
- [ ] **Expected in logs:**
  ```
  discuss_channel._notify_thread: processing bot for N partners
  ```
- [ ] **Expected result:** Bot sends automated response
- [ ] **NOT expected in logs:**
  ```
  automation_base: connector:... bot
  ```

**Status:** ✅ Pass / ❌ Fail

**Notes:**

```
[Your notes here]
```

---

### Test 4: Reactions (Odoo → External)

**Objective:** Verify reactions sync to external platform

**Prerequisites:**

- [ ] Message from external platform exists (has `discuss_hub_message_id`)

**Test steps:**

- [ ] Find message from external source in Odoo
- [ ] Add a reaction (e.g., 👍) in Odoo
- [ ] **Expected in logs:**
  ```
  mail_message_reaction.create: connector:... channel:... reaction
  ```
- [ ] **Expected result:** Reaction appears in external platform
- [ ] **NOT expected in logs:**
  ```
  automation_base: connector:... reaction
  ```

**Status:** ✅ Pass / ❌ Fail

**Notes:**

```
[Your notes here]
```

---

### Test 5: Error Handling

**Objective:** Verify errors don't break normal Odoo flow

**Test steps:**

- [ ] Temporarily disable external API (or break connection)
- [ ] Send message from Odoo
- [ ] **Expected result:** Message created in Odoo successfully
- [ ] **Expected in logs:**
  ```
  ERROR ... Error sending outgoing message to connector
  ```
- [ ] Message visible in Odoo channel
- [ ] User can continue using Odoo normally

**Status:** ✅ Pass / ❌ Fail

**Notes:**

```
[Your notes here]
```

---

## Performance Verification

### Log Analysis

- [ ] Search logs for hook execution time
- [ ] Compare with baseline (if available)
- [ ] Verify no significant performance degradation

**Commands:**

```bash
# Count hook executions
docker compose logs odoo | grep "message_post:" | wc -l

# Check for errors
docker compose logs odoo | grep "ERROR.*discuss_channel\|mail_message_reaction"

# Monitor response times
# Use your monitoring tool
```

### Metrics to Monitor

- [ ] **Response time:** Average message send time < 50ms
- [ ] **Error rate:** < 0.1% of operations
- [ ] **CPU usage:** Similar or better than baseline
- [ ] **Memory usage:** No memory leaks
- [ ] **Database queries:** Reduced from baseline

**Baseline Metrics:**

```
Average response time: _____ ms
Error rate: _____ %
CPU usage: _____ %
Memory usage: _____ MB
DB queries per operation: _____
```

**Post-Migration Metrics:**

```
Average response time: _____ ms (Expected: 5x faster)
Error rate: _____ % (Expected: < 0.1%)
CPU usage: _____ % (Expected: similar or lower)
Memory usage: _____ MB (Expected: similar)
DB queries per operation: _____ (Expected: ~3x less)
```

## Integration Testing

### N8N Workflows

- [ ] N8N workflows still triggering correctly
- [ ] Webhook endpoints responding
- [ ] Workflow executions successful
- [ ] No errors in N8N logs

### Typebot Integration

- [ ] Typebot bots responding
- [ ] Bot conversations flowing correctly
- [ ] Typebot webhook working
- [ ] No errors in bot manager logs

### External APIs

- [ ] Evolution API responding
- [ ] WhatsApp Cloud API responding
- [ ] Telegram Bot API responding
- [ ] Other integrations working

## Monitoring and Alerts

### First 24 Hours

- [ ] Monitor error rates every hour
- [ ] Check message delivery success rate
- [ ] Verify bot response times
- [ ] Watch for memory leaks
- [ ] Monitor CPU spikes

### First Week

- [ ] Daily error rate review
- [ ] Weekly performance report
- [ ] User feedback collection
- [ ] Incident tracking

## User Acceptance

### End User Testing

- [ ] Select group of users testing
- [ ] User feedback collected
- [ ] No blocking issues reported
- [ ] Performance improvement noticed

### Stakeholder Sign-off

- [ ] Technical lead approval
- [ ] Product owner approval
- [ ] Operations approval

## Documentation

- [ ] Migration documented in CHANGELOG.md
- [ ] Team notified of changes
- [ ] Wiki/documentation updated
- [ ] Training materials updated (if needed)

## Rollback Plan

### If Issues Arise

**Criteria for rollback:**

- [ ] Error rate > 5%
- [ ] Critical functionality broken
- [ ] Performance worse than baseline
- [ ] Data loss or corruption

**Rollback steps:**

1. **Reactivate automations:**

   ```bash
   # Via UI: Settings → Technical → Automated Actions
   # Search for "discuss_hub"
   # Activate all 3 automations
   ```

2. **Comment out hooks:**

   - Edit `discuss_hub/models/discuss_channel.py`
   - Comment out `message_post()` and `_notify_thread()` methods
   - Edit `discuss_hub/models/mail_message_reaction.py`
   - Comment out entire file content

3. **Update module:**

   ```bash
   odoo -u discuss_hub --stop-after-init
   ```

4. **Restart Odoo:**

   ```bash
   docker compose restart odoo
   ```

5. **Verify old behavior:**
   - [ ] Automations running
   - [ ] Messages sending via automations
   - [ ] Logs show "automation_base:" messages

## Success Criteria

Migration is considered successful when:

- ✅ All functional tests pass
- ✅ Performance improved or similar
- ✅ No critical errors in 24h
- ✅ No data loss
- ✅ User feedback positive
- ✅ All integrations working

## Sign-off

**Tested by:** \***\*\*\*\*\***\_\***\*\*\*\*\*** Date: **\_\_\_**

**Technical Lead:** \***\*\*\*\*\***\_\***\*\*\*\*\*** Date: **\_\_\_**

**Product Owner:** \***\*\*\*\*\***\_\***\*\*\*\*\*** Date: **\_\_\_**

**Operations:** \***\*\*\*\*\***\_\***\*\*\*\*\*** Date: **\_\_\_**

---

**Migration Status:** 🟢 Success / 🟡 Partial / 🔴 Failed

**Final Notes:**

```
[Add any final observations, lessons learned, or recommendations]
```
