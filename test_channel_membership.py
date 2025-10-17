#!/usr/bin/env python3
"""
Quick test script to verify channel membership computation
Run this in Odoo shell: docker compose -f compose-dev.yaml exec odoo odoo shell -c /etc/odoo/odoo.conf
"""

# Get a channel with discuss_hub_connector
channels = env['discuss.channel'].search([('discuss_hub_connector', '!=', False)], limit=5)

print("\n=== Channel Membership Test ===")
print(f"Current user: {env.user.name} (ID: {env.user.id})")
print(f"Current partner: {env.user.partner_id.name} (ID: {env.user.partner_id.id})")
print(f"\nFound {len(channels)} discuss hub channels\n")

for channel in channels:
    print(f"Channel: {channel.name} (ID: {channel.id})")
    print(f"  - Active: {channel.active}")
    print(f"  - Connector: {channel.discuss_hub_connector.name if channel.discuss_hub_connector else 'None'}")
    print(f"  - Members: {', '.join([p.name for p in channel.channel_partner_ids])}")
    print(f"  - Is current user member? {channel.is_current_user_member}")
    print(f"  - Current partner in members? {env.user.partner_id in channel.channel_partner_ids}")
    print()
