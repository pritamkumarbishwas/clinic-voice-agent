import argparse
import asyncio
import getpass
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth import hash_password, is_valid_email, normalize_email
from app.database import close_database, initialize_database, users


async def create_admin(
    email: str,
    password: str,
    name: str = "",
    update_existing: bool = True,
) -> None:
    normalized = normalize_email(email)
    if not is_valid_email(normalized):
        raise SystemExit("Please provide a valid email address.")
    if len(password) < 8:
        raise SystemExit("Password must be at least 8 characters long.")

    await initialize_database()

    try:
        existing = await users.find_one({"email": normalized})
        if existing and not update_existing:
            raise SystemExit(
                f"User {normalized} already exists. "
                "Remove --no-update to reset the password."
            )

        now = datetime.now(timezone.utc)
        password_hash = hash_password(password)

        if existing:
            await users.update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "password_hash": password_hash,
                        "name": name or existing.get("name", "Admin"),
                        "role": "admin",
                        "active": True,
                        "updated_at": now,
                    }
                },
            )
            print(f"Admin user {normalized} updated.")
        else:
            await users.insert_one(
                {
                    "email": normalized,
                    "password_hash": password_hash,
                    "name": name or "Admin",
                    "role": "admin",
                    "active": True,
                    "created_at": now,
                    "updated_at": now,
                }
            )
            print(f"Admin user {normalized} created.")
    finally:
        await close_database()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create or update an admin user for the dashboard."
    )
    parser.add_argument("--email", help="Admin email address.")
    parser.add_argument("--name", default="", help="Display name.")
    parser.add_argument(
        "--password",
        help="Admin password. Omit to be prompted securely.",
    )
    parser.add_argument(
        "--no-update",
        action="store_true",
        help="Refuse to update an existing user.",
    )
    args = parser.parse_args()

    email = args.email or input("Admin email: ").strip()
    password = args.password
    if not password:
        password = getpass.getpass("Admin password: ")
        confirmation = getpass.getpass("Confirm password: ")
        if password != confirmation:
            raise SystemExit("Passwords do not match.")

    asyncio.run(
        create_admin(
            email=email,
            password=password,
            name=args.name,
            update_existing=not args.no_update,
        )
    )


if __name__ == "__main__":
    main()
