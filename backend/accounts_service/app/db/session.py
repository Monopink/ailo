from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings

# Create an async engine to connect to the database
engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)

# Create a sessionmaker to generate new Session objects, which will be used for dependency injection
SessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)
