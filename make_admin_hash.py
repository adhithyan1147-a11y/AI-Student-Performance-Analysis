from getpass import getpass
from werkzeug.security import generate_password_hash

password = getpass("Choose an administrator password (input hidden): ")
if len(password) < 10:
    raise SystemExit("Use at least 10 characters for a stronger password.")
print("\nCopy this hash into ADMIN_PASSWORD_HASH in your .env file:\n")
print(generate_password_hash(password))
