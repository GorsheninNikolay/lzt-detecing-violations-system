"""Provision the owner through a private terminal; never print the credential."""
import getpass
import hashlib
import hmac
import os
import secrets

from sqlalchemy import create_engine, text


def hash_password(password: str) -> str:
    if not isinstance(password, str) or not 8 <= len(password) <= 1024:
        raise ValueError("password_length")
    salt = secrets.token_bytes(16)
    key = hashlib.scrypt(password.encode(), salt=salt, n=32768, r=8, p=1, dklen=32, maxmem=64 * 1024 * 1024)
    return f"scrypt$32768$8$1${salt.hex()}${key.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt, expected = encoded.split('$')
        if (algorithm, n, r, p) != ('scrypt', '32768', '8', '1') or len(salt) != 32 or len(expected) != 64 or len(password) > 1024:
            return False
        key = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=1, dklen=32, maxmem=64 * 1024 * 1024)
        return hmac.compare_digest(key.hex(), expected)
    except (ValueError, TypeError, AttributeError):
        return False


def main():
    password = getpass.getpass('New owner password (8+ characters): ')
    if password != getpass.getpass('Repeat password: '):
        raise SystemExit('Passwords do not match')
    encoded = hash_password(password)
    engine = create_engine(os.environ['DATABASE_URL'])
    with engine.begin() as connection:
        connection.execute(text("""INSERT INTO admin_credentials(login,password_hash)
            VALUES ('gorshenin-nik',:hash) ON CONFLICT(login)
            DO UPDATE SET password_hash=excluded.password_hash"""), {'hash': encoded})
        connection.execute(text('DELETE FROM admin_sessions'))
    engine.dispose()
    print('Owner configured. All previous sessions revoked.')


if __name__ == '__main__':
    main()
