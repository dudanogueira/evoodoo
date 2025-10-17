#!/usr/bin/env python3
"""
Quick test script to verify channel membership computation
Run this in Odoo shell:
docker compose -f compose-dev.yaml exec odoo odoo shell -c /etc/odoo/odoo.conf
"""

# Get a channel with discuss_hub_connector
channels = env["discuss.channel"].search(  # noqa: F821
    [("discuss_hub_connector", "!=", False)], limit=5
)

print("\n=== Channel Membership Test ===")
print(f"Current user: {env.user.name} (ID: {env.user.id})")  # noqa: F821
print(  # noqa: F821
    f"Current partner: {env.user.partner_id.name} "  # noqa: F821
    f"(ID: {env.user.partner_id.id})"  # noqa: F821
)
print(f"\nFound {len(channels)} discuss hub channels\n")

for channel in channels:
    print(f"Channel: {channel.name} (ID: {channel.id})")
    print(f"  - Active: {channel.active}")
    connector_name = (
        channel.discuss_hub_connector.name if channel.discuss_hub_connector else "None"
    )
    print(f"  - Connector: {connector_name}")
    print(f"  - Members: {', '.join([p.name for p in channel.channel_partner_ids])}")
    print(f"  - Is current user member? {channel.is_current_user_member}")
    print(  # noqa: F821
        f"  - Current partner in members? "
        f"{env.user.partner_id in channel.channel_partner_ids}"  # noqa: F821
    )
    print()
