from sqlalchemy.ext.asyncio import (AsyncSession, async_sessionmaker,
                                    create_async_engine)
# central connection manager between your FastAPI app and your physical database file (like blog.db)
from sqlalchemy.orm import DeclarativeBase

from config import settings

# Base is created using DeclarativeBase. allows a standard Python class to register itself as a database table
# Session is your actual conversation link with the database that is created using sessionmaker


# SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///./blog.db"  # +aiosqlite is the async driver . url not needed we are now using postgres
# '.' is the current root directory. it is a protocol that tells sqlalchemy using url that it is a lightweight, serverless SQLite database engine. if the blog.db is absent sqllite creates it.

engine = create_async_engine(settings.database_url)   # engine serves as the core internal translation core manager—it intercepts your clean object-oriented Python expressions and converts them into optimization-wrapped, raw SQL transactional query
    # SQLALCHEMY_DATABASE_URL,
    # connect_args={"check_same_thread": False},)  # traditionally sqllite only allows one working thread .this tells sqllite that allow multiple threads.


# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# each request gets its own session. sessionlocal a factory that creates db sessions on req.
# the three configurations: changes to db are not saved automaticallly, validation checks are not sent before the changes are completed, connects sessionlocal to the engine.
AsyncSessionLocal = async_sessionmaker( # tuned for async behaviour
    engine,                             # db engine is passed
    class_=AsyncSession,                # By default, SQLAlchemy makes standard synchronous sessions. This parameter overrides that default behavior. It explicitly commands the factory
    expire_on_commit=False,             # when a python object is expired by default sql alchemy will wipe its data and run a hidden select if that data is needed. this will crash with async and await . setting to false sqlalchemy keeps that object alive in memory.
)


class Base(DeclarativeBase):  # all the db models are linked to this
    pass

async def get_db():  # a dependency function that provides sessions to our routes.
    async with AsyncSessionLocal() as session:  # session is just a variable but industry standard as session is just a a single, short-lived database connection window for one specific request.
        yield session   # yield pauses this function and delivers the session directly to any route requesting it.
# with makes sessionlocal acts a context manager that opens and close properly even if error occurs .
