## database.py
from sqlalchemy import create_engine
# central connection manager between your FastAPI app and your physical database file (like blog.db)
from sqlalchemy.orm import DeclarativeBase, sessionmaker
# Base is created using DeclarativeBase. allows a standard Python class to register itself as a database table
# Session is your actual conversation link with the database that is created using sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./blog.db"
# '.' is the current root directory. it is a protocol that tells sqlalchemy using url that it is a lightweight, serverless SQLite database engine. if the blog.db is absent sqllite creates it.

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
# engine serves as the core internal translation core manager—it intercepts your clean object-oriented Python expressions and converts them into optimization-wrapped, raw SQL transactional query
# traditionally sqllite only allows one working thread line 13 tells sqllite that allow multiple threads.

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# each request gets its own session. sessionlocal a factory that creates db sessions on req.
# the three configurations: changes to db are not saved automaticallly, validation checks are not sent before the changes are completed, connects sessionlocal to the engine.

class Base(DeclarativeBase):
    pass
# all the db models are linked to this

def get_db():
    with SessionLocal() as db:
        yield db
# a dependency function that provides sessions to our routes.
# with makes sessionlocal acts a context manager that opens and close properly even if error occurs .
# yield pauses this function and delivers the session directly to any route requesting it.