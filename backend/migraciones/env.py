from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from app import models  # noqa: F401  (registra las tablas en Base.metadata)
from app.config import settings
from app.db import Base

config = context.config
# Desde la aplicación no se reconfigura el logging (borraría los loggers de uvicorn)
if config.config_file_name is not None and "connection" not in config.attributes:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(url=settings.database_url, target_metadata=target_metadata, literal_binds=True,
                      compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    conectable = config.attributes.get("connection")
    if conectable is not None:  # conexión entregada por app.main.inicializar()
        context.configure(connection=conectable, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = create_engine(settings.database_url)
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
