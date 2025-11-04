#!/usr/bin/env python3
"""
Bot Manager Diagnostic Tool

This script helps diagnose why bots are not being triggered.
Run it in the Odoo shell or as a Python script in the Odoo environment.
"""

import logging

_logger = logging.getLogger(__name__)


def diagnose_bot_configuration(  # noqa: C901
    env, connector_id=None, channel_id=None
):
    """
    Diagnose bot configuration issues.

    Args:
        env: Odoo environment
        connector_id: Optional connector ID to check
        channel_id: Optional channel ID to check
    """
    print("\n" + "=" * 80)
    print("BOT MANAGER DIAGNOSTIC TOOL")
    print("=" * 80 + "\n")

    # Check all bot managers
    print("1. CHECKING BOT MANAGERS")
    print("-" * 80)
    bots = env["discuss_hub.bot_manager"].search([])
    print(f"Total bot managers found: {len(bots)}")

    for bot in bots:
        status = "✓ ACTIVE" if bot.active else "✗ INACTIVE"
        dm_status = "✓" if bot.respond_to_internal_direct_messages else "✗"
        print(f"  - Bot #{bot.id}: {bot.bot_type} - {status}")
        print(f"    URL: {bot.bot_url}")
        print(f"    Respond to Internal DMs: {dm_status}")
        print(f"    Partners: {len(bot.partner)} partner(s)")
        for partner in bot.partner:
            print(f"      - {partner.name} (ID: {partner.id})")

    if not bots:
        print("  ⚠ WARNING: No bot managers found!")
        print("  → Create a bot manager first")

    print()

    # Check partners with bots
    print("2. CHECKING PARTNERS WITH BOTS")
    print("-" * 80)
    partners_with_bot = env["res.partner"].search([("bot", "!=", False)])
    print(f"Total partners with bot: {len(partners_with_bot)}")

    for partner in partners_with_bot:
        print(f"  - {partner.name} (ID: {partner.id})")
        print(f"    Bot: #{partner.bot.id} ({partner.bot.bot_type})")
        print(f"    Bot Active: {'Yes' if partner.bot.active else 'No'}")

    if not partners_with_bot:
        print("  ⚠ WARNING: No partners have bots configured!")
        print("  → Assign a bot manager to a partner")

    print()

    # Check connectors
    print("3. CHECKING CONNECTORS")
    print("-" * 80)

    if connector_id:
        connectors = env["discuss_hub.connector"].browse(connector_id)
    else:
        connectors = env["discuss_hub.connector"].search([("enabled", "=", True)])

    print(f"Checking {len(connectors)} connector(s)")

    for connector in connectors:
        print(f"\n  Connector: {connector.name} (ID: {connector.id})")
        print(f"  Type: {connector.type}")
        print(f"  Enabled: {'Yes' if connector.enabled else 'No'}")

        auto_partners = connector.automatic_added_partners
        print(f"  Automatic Added Partners: {len(auto_partners)}")

        partners_with_bot_in_auto = auto_partners.filtered(lambda p: p.bot)
        print(f"  Partners with bot in auto: {len(partners_with_bot_in_auto)}")

        if partners_with_bot_in_auto:
            for partner in partners_with_bot_in_auto:
                status = "✓" if partner.bot.active else "✗"
                bot_info = f"Bot #{partner.bot.id} ({partner.bot.bot_type})"
                print(f"    {status} {partner.name} → {bot_info}")
        else:
            print("    ⚠ WARNING: No partners with bots in automatic_added_partners!")
            print("    → Add a partner with a bot to automatic_added_partners")

        # Check automatic teams
        auto_teams = connector.automatic_added_teams
        print(f"  Automatic Added Teams: {len(auto_teams)}")

    if not connectors:
        print("  ⚠ WARNING: No enabled connectors found!")

    print()

    # Check specific channel
    if channel_id:
        print("4. CHECKING SPECIFIC CHANNEL")
        print("-" * 80)
        channel = env["discuss.channel"].browse(channel_id)

        if not channel.exists():
            print(f"  ✗ ERROR: Channel {channel_id} not found!")
        else:
            print(f"  Channel: {channel.name} (ID: {channel.id})")
            print(f"  Channel Type: {channel.channel_type}")
            connector_name = (
                channel.discuss_hub_connector.name
                if channel.discuss_hub_connector
                else "None"
            )
            print(f"  Connector: {connector_name}")
            print(f"  Partners in channel: {len(channel.channel_partner_ids)}")

            partners_with_bot_in_channel = channel.channel_partner_ids.filtered(
                lambda p: p.bot
            )
            print(f"  Partners with bot: {len(partners_with_bot_in_channel)}")

            if partners_with_bot_in_channel:
                for partner in partners_with_bot_in_channel:
                    status = "✓" if partner.bot.active else "✗"
                    bot_info = f"Bot #{partner.bot.id} ({partner.bot.bot_type})"
                    print(f"    {status} {partner.name} → {bot_info}")
            else:
                print("    ⚠ WARNING: No partners with bots in this channel!")
                print("    → The channel needs at least one partner with a bot")

            # Check last message
            if channel.message_ids:
                last_msg = channel.message_ids.sorted(
                    key=lambda m: m.create_date, reverse=True
                )[0]
                print("\n  Last message:")
                print(f"    ID: {last_msg.id}")
                print(f"    Author: {last_msg.author_id.name}")
                print(f"    Date: {last_msg.create_date}")
                body_preview = last_msg.body[:100] if last_msg.body else "No body"
                print(f"    Body: {body_preview}...")

                # Check if author is internal user (has base.group_user)
                is_internal_user = False
                if last_msg.author_id:
                    author_user = env["res.users"].search(
                        [("partner_id", "=", last_msg.author_id.id)], limit=1
                    )
                    if author_user:
                        is_internal_user = author_user.has_group("base.group_user")

                if is_internal_user:
                    print("    Is internal user: Yes")
                    if channel.channel_type == "chat":
                        # Check if any bot responds to internal DMs
                        bots_responding_to_internal = (
                            partners_with_bot_in_channel.filtered(
                                lambda p: p.bot.respond_to_internal_direct_messages
                            )
                        )
                        if bots_responding_to_internal:
                            msg = "bot WILL be triggered"
                            print(f"    → Channel type 'chat' (DM): {msg}")
                            count = len(bots_responding_to_internal)
                            print(
                                f"    → {count} bot(s) configured to "
                                "respond to internal DMs"
                            )
                        else:
                            msg = "bot will NOT be triggered"
                            print(f"    → Channel type 'chat' (DM): {msg}")
                            print(
                                "    → No bots configured to respond to " "internal DMs"
                            )
                    else:
                        ch_type = channel.channel_type
                        msg = "bot will NOT be triggered"
                        print(f"    → Channel type '{ch_type}' (group): {msg}")
                        print(
                            "    → Internal users only trigger bots in "
                            "DMs (if configured)"
                        )
                else:
                    print("    Is internal user: No (bot WILL be triggered)")
                    user_type = "external"
                    if last_msg.author_id:
                        author_user = env["res.users"].search(
                            [("partner_id", "=", last_msg.author_id.id)], limit=1
                        )
                        if author_user:
                            if author_user.has_group("base.group_portal"):
                                user_type = "portal"
                            elif author_user.has_group("base.group_public"):
                                user_type = "public"
                    print(f"    → User type: {user_type}")
            else:
                print("\n  ⚠ No messages in channel yet")

    print()

    # Summary and recommendations
    print("5. SUMMARY & RECOMMENDATIONS")
    print("-" * 80)

    issues_found = []

    if not bots:
        issues_found.append("No bot managers found")
    elif not any(bot.active for bot in bots):
        issues_found.append("No active bot managers")

    if not partners_with_bot:
        issues_found.append("No partners have bots configured")

    if connectors:
        for connector in connectors:
            if not connector.automatic_added_partners.filtered(lambda p: p.bot):
                msg = (
                    f"Connector '{connector.name}' has no partners "
                    "with bots in automatic_added_partners"
                )
                issues_found.append(msg)

    if issues_found:
        print("  ⚠ ISSUES FOUND:")
        for i, issue in enumerate(issues_found, 1):
            print(f"    {i}. {issue}")

        print("\n  📋 REQUIRED STEPS:")
        print("    1. Create a Bot Manager (Discuss Hub → Bots/Agents)")
        print("    2. Create or select a Partner (Contacts)")
        print("    3. Set the Bot Manager field on the Partner")
        print("    4. Add the Partner to Connector's 'Automatic Added Partners'")
        print("    5. Test by sending a message through the connector")
    else:
        print("  ✓ Configuration looks good!")
        print("  If bot is still not triggering, check the logs:")
        print("    docker compose -f compose-dev.yaml logs -f odoo | grep -i bot")

    print("\n" + "=" * 80 + "\n")


# Example usage in Odoo shell:
# from discuss_hub.tests.diagnose_bot import diagnose_bot_configuration
# diagnose_bot_configuration(env)
# diagnose_bot_configuration(env, connector_id=1)
# diagnose_bot_configuration(env, channel_id=42)

if __name__ == "__main__":
    print("This script should be run in the Odoo shell:")
    print("  docker compose -f compose-dev.yaml exec odoo odoo shell -d odoo")
    print("  >>> from discuss_hub.tests.diagnose_bot import diagnose_bot_configuration")
    print("  >>> diagnose_bot_configuration(env)")
