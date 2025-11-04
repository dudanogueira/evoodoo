#!/usr/bin/env python3
"""
Quick test script to verify channel membership computation.

Usage (Odoo shell):
    docker compose -f compose-dev.yaml exec odoo \
        odoo shell -c /etc/odoo/odoo.conf -d $ODOO_DB
    >>> from discuss_hub import test_channel_membership as tcm
    >>> tcm.run(env)
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def run(env):  # noqa: D401 - simple helper for Odoo shell
    """Run the membership checks using the provided Odoo environment."""
    # Get a channel with discuss_hub_connector
    channels = env["discuss.channel"].search(
        [("discuss_hub_connector", "!=", False)], limit=5
    )

    logger.info("=== Channel Membership Test ===")
    logger.info("Current user: %s (ID: %s)", env.user.name, env.user.id)
    logger.info(
        "Current partner: %s (ID: %s)",
        env.user.partner_id.name,
        env.user.partner_id.id,
    )
    logger.info("Found %s discuss hub channels", len(channels))

    for channel in channels:
        logger.info("Channel: %s (ID: %s)", channel.name, channel.id)
        logger.info("  - Active: %s", channel.active)
        logger.info(
            "  - Connector: %s",
            channel.discuss_hub_connector.name
            if channel.discuss_hub_connector
            else "None",
        )
        logger.info(
            "  - Members: %s",
            ", ".join([p.name for p in channel.channel_partner_ids]),
        )
        logger.info("  - Is current user member? %s", channel.is_current_user_member)
        logger.info(
            "  - Current partner in members? %s",
            env.user.partner_id in channel.channel_partner_ids,
        )


if __name__ == "__main__":
    logger.info("Import this module in Odoo shell and call run(env)")
