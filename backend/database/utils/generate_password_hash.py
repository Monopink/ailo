#!/usr/bin/env python3
"""Generate bcrypt password hash for database initialization."""

import sys

import bcrypt

if len(sys.argv) > 1:
    password = sys.argv[1]
else:
    password = input("Enter password: ")

hash_bytes = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
print(hash_bytes.decode("utf-8"))
