import asyncio
from logging.config import fileConfig

# 导入所有模型以确保 Alembic 能检测到表变更
import app.models.account  # noqa: F401
import app.models.analytics  # noqa: F401
import app.models.content  # noqa: F401
import app.models.interaction  # noqa: F401
import app.models.knowledge  # noqa: F401
import app.models.risk  # noqa: F401
from alembic import context
from app.config import settings
from app.db.session import Base
from sqlalchemy.ext.asyncio import create_async_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(settings.database_url)
    async with engine.connect() as connection:
        await connection.run_sync(
            lambda conn: context.configure(
                connection=conn, target_metadata=target_metadata
            )
        )
        async with connection.begin():
            await connection.run_sync(lambda _: context.run_migrations())
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
