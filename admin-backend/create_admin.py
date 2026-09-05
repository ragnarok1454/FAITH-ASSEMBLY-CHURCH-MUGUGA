"""
Run this once to create login accounts.

Usage:
    python create_admin.py

It will ask you interactively for each account's details.
Run it again any time you need to add another ministry admin.
"""

import sqlite3
import os
import getpass
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "church.db")

VALID_MINISTRIES = {"men", "women", "youth", "praise", "instruments", "church"}


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('superadmin', 'ministry_admin')),
            ministry TEXT
        )
    """)
    conn.commit()

    print("=== Create a new admin account ===")
    username = input("Username: ").strip()
    password = getpass.getpass("Password: ")

    print("Role options: 1) Super Admin   2) Ministry Admin")
    role_choice = input("Choose role (1 or 2): ").strip()

    if role_choice == "1":
        role = "superadmin"
        ministry = None
    else:
        role = "ministry_admin"
        print(f"Valid ministries: {', '.join(sorted(VALID_MINISTRIES))}")
        ministry = input("Which ministry will they manage?: ").strip().lower()
        if ministry not in VALID_MINISTRIES:
            print(f"'{ministry}' is not in the valid ministries list. Add it to "
                  f"VALID_MINISTRIES in app.py and create_admin.py first.")
            return

    password_hash = generate_password_hash(password)

    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, role, ministry) VALUES (?, ?, ?, ?)",
            (username, password_hash, role, ministry),
        )
        conn.commit()
        print(f"\n✅ Created {role} account '{username}'"
              + (f" for {ministry} ministry." if ministry else " (full access)."))
    except sqlite3.IntegrityError:
        print(f"\n❌ Username '{username}' already exists. Choose a different one.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
