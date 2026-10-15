from alembic import context
from app.db.base import Base
import app.models  # noqa: F401
from app.db.session import engine
from app.core.config import settings

if context.is_offline_mode():
    context.configure(url=settings().database_url, target_metadata=Base.metadata, literal_binds=True, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
