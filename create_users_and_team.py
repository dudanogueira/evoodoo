#!/usr/bin/env python3
"""
Script to create 3 users and a Discuss Hub routing team with those users.
Usage: Run this script in the Odoo shell or as a Python script with Odoo environment.
"""

import logging
import os
import xmlrpc.client

# Configuration
ODOO_URL = os.getenv("ODOO_URL", "http://localhost:8069")
ODOO_DB = os.getenv("ODOO_DB", "odoo")
ODOO_ADMIN_USER = os.getenv("ODOO_ADMIN_USER", "admin")
ODOO_ADMIN_PASSWORD = os.getenv("ODOO_ADMIN_PASSWORD", "admin")

# Users to create
USERS_DATA = [
    {
        "login": "agent1",
        "name": "Agent 1",
        "email": "agent1@example.com",
        "password": "agent1@example.com",
    },
    {
        "login": "agent2",
        "name": "Agent 2",
        "email": "agent2@example.com",
        "password": "agent2@example.com",
    },
    {
        "login": "agent3",
        "name": "Agent 3",
        "email": "agent3@example.com",
        "password": "agent3@example.com",
    },
]

TEAM_NAME = "Support Team"
TEAM_NAME_2 = "VIP Support Team"

logger = logging.getLogger(__name__)


def main():
    """Main function to create users and team."""
    logger.info("Connecting to Odoo at %s...", ODOO_URL)

    # Connect to Odoo
    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")

    # Authenticate
    uid = common.authenticate(ODOO_DB, ODOO_ADMIN_USER, ODOO_ADMIN_PASSWORD, {})

    if not uid:
        logger.error("Authentication failed! Check your credentials.")
        return

    logger.info("Authenticated as user ID: %s", uid)

    # Connect to object endpoint
    models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")

    # Create users
    created_user_ids = []
    logger.info("📝 Creating users...")

    for user_data in USERS_DATA:
        # Check if user already exists
        existing_user = models.execute_kw(
            ODOO_DB,
            uid,
            ODOO_ADMIN_PASSWORD,
            "res.users",
            "search",
            [[("login", "=", user_data["login"])]],
        )

        if existing_user:
            logger.warning(
                "User '%s' already exists (ID: %s)",
                user_data["login"],
                existing_user[0],
            )
            created_user_ids.append(existing_user[0])
        else:
            # Create new user
            user_id = models.execute_kw(
                ODOO_DB,
                uid,
                ODOO_ADMIN_PASSWORD,
                "res.users",
                "create",
                [
                    {
                        "name": user_data["name"],
                        "login": user_data["login"],
                        "email": user_data["email"],
                        "password": user_data["password"],
                        "groups_id": [(6, 0, [])],  # Base user group
                    }
                ],
            )
            logger.info("Created user '%s' (ID: %s)", user_data["login"], user_id)
            created_user_ids.append(user_id)

    # Check if team already exists
    logger.info("🔍 Checking if team '%s' exists...", TEAM_NAME)
    existing_team = models.execute_kw(
        ODOO_DB,
        uid,
        ODOO_ADMIN_PASSWORD,
        "discuss_hub.routing_team",
        "search",
        [[("name", "=", TEAM_NAME)]],
    )

    if existing_team:
        team_id = existing_team[0]
        logger.warning("Team '%s' already exists (ID: %s)", TEAM_NAME, team_id)
        logger.info("Updating team members...")

        # Get existing team member IDs
        team_data = models.execute_kw(
            ODOO_DB,
            uid,
            ODOO_ADMIN_PASSWORD,
            "discuss_hub.routing_team",
            "read",
            [team_id],
            {"fields": ["team_member_ids"]},
        )

        # Delete existing team members
        if team_data[0]["team_member_ids"]:
            models.execute_kw(
                ODOO_DB,
                uid,
                ODOO_ADMIN_PASSWORD,
                "discuss_hub.routing_team_member",
                "unlink",
                [team_data[0]["team_member_ids"]],
            )
    else:
        # Create new team
        logger.info("📝 Creating team '%s'...", TEAM_NAME)
        team_id = models.execute_kw(
            ODOO_DB,
            uid,
            ODOO_ADMIN_PASSWORD,
            "discuss_hub.routing_team",
            "create",
            [
                {
                    "name": TEAM_NAME,
                    "active": True,
                    "routing_strategy": "round_robin",
                    "online_users_only": True,
                }
            ],
        )
        logger.info("Created team '%s' (ID: %s)", TEAM_NAME, team_id)

    # Create team members
    logger.info("👥 Adding users to team...")
    for order, user_id in enumerate(created_user_ids, start=1):
        member_id = models.execute_kw(
            ODOO_DB,
            uid,
            ODOO_ADMIN_PASSWORD,
            "discuss_hub.routing_team_member",
            "create",
            [
                {
                    "team_id": team_id,
                    "user_id": user_id,
                    "order": order,
                    "count": 0,
                }
            ],
        )

        user_name = models.execute_kw(
            ODOO_DB,
            uid,
            ODOO_ADMIN_PASSWORD,
            "res.users",
            "read",
            [user_id],
            {"fields": ["name"]},
        )[0]["name"]

        logger.info("Added '%s' to team (Member ID: %s)", user_name, member_id)

    # Create second team with only agent1
    logger.info("🔍 Checking if team '%s' exists...", TEAM_NAME_2)
    existing_team_2 = models.execute_kw(
        ODOO_DB,
        uid,
        ODOO_ADMIN_PASSWORD,
        "discuss_hub.routing_team",
        "search",
        [[("name", "=", TEAM_NAME_2)]],
    )

    if existing_team_2:
        team_id_2 = existing_team_2[0]
        logger.warning("Team '%s' already exists (ID: %s)", TEAM_NAME_2, team_id_2)
        logger.info("Updating team members...")

        # Get existing team member IDs
        team_data_2 = models.execute_kw(
            ODOO_DB,
            uid,
            ODOO_ADMIN_PASSWORD,
            "discuss_hub.routing_team",
            "read",
            [team_id_2],
            {"fields": ["team_member_ids"]},
        )

        # Delete existing team members
        if team_data_2[0]["team_member_ids"]:
            models.execute_kw(
                ODOO_DB,
                uid,
                ODOO_ADMIN_PASSWORD,
                "discuss_hub.routing_team_member",
                "unlink",
                [team_data_2[0]["team_member_ids"]],
            )
    else:
        # Create new team
        logger.info("📝 Creating team '%s'...", TEAM_NAME_2)
        team_id_2 = models.execute_kw(
            ODOO_DB,
            uid,
            ODOO_ADMIN_PASSWORD,
            "discuss_hub.routing_team",
            "create",
            [
                {
                    "name": TEAM_NAME_2,
                    "active": True,
                    "routing_strategy": "round_robin",
                    "online_users_only": True,
                }
            ],
        )
        logger.info("Created team '%s' (ID: %s)", TEAM_NAME_2, team_id_2)

    # Add only agent1 to the second team
    logger.info("👥 Adding agent1 to '%s'...", TEAM_NAME_2)
    agent1_user_id = created_user_ids[0]  # First user is agent1

    member_id_2 = models.execute_kw(
        ODOO_DB,
        uid,
        ODOO_ADMIN_PASSWORD,
        "discuss_hub.routing_team_member",
        "create",
        [
            {
                "team_id": team_id_2,
                "user_id": agent1_user_id,
                "order": 1,
                "count": 0,
            }
        ],
    )

    agent1_name = models.execute_kw(
        ODOO_DB,
        uid,
        ODOO_ADMIN_PASSWORD,
        "res.users",
        "read",
        [agent1_user_id],
        {"fields": ["name"]},
    )[0]["name"]

    logger.info("Added '%s' to team (Member ID: %s)", agent1_name, member_id_2)

    logger.info("🎉 Setup complete!")
    logger.info("   - Created/Updated %s users", len(created_user_ids))
    logger.info(
        "   - Team '%s' (ID: %s) has %s members",
        TEAM_NAME,
        team_id,
        len(created_user_ids),
    )
    logger.info(
        "   - Team '%s' (ID: %s) has 1 member (agent1)",
        TEAM_NAME_2,
        team_id_2,
    )
    logger.info("📋 User credentials:")
    for user_data in USERS_DATA:
        logger.info(
            "   Login: %s | Password: %s",
            user_data["login"],
            user_data["password"],
        )


if __name__ == "__main__":
    main()
