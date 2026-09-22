from alembic import context
from sqlalchemy import create_engine

from app.config import Config


def run_migrations_online() -> None:
    engine = create_engine(Config.database_url_from_env())
    try:
        with engine.connect() as connection:
            context.configure(connection=connection)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


run_migrations_online()
