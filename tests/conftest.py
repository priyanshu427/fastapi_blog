
import os
from collections.abc import AsyncGenerator

# Test DB and Bucket . we dont want any senstive info. to leak into testing from .env so we are overrriding all environment variables here. so we can safely import our app
os.environ["DATABASE_URL"] = (  # pointing to a completely separate test db called test_blog . our app db is blog
    "postgresql+psycopg://bloguser:blogpass@localhost/test_blog" # on app startup python loads files . environment variables are guaranteed to load first before main application code ever boots up.
)
os.environ["S3_BUCKET_NAME"] = "test-bucket"  # fake s3 bucket name for boto mocking 
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"

# Dummy S3/AWS Credentials
os.environ["S3_ACCESS_KEY_ID"] = "testing" # our app reads s3 variables through pydantic settings
os.environ["S3_SECRET_ACCESS_KEY"] = "testing"
os.environ["S3_REGION"] = "us-east-1"

os.environ["AWS_ACCESS_KEY_ID"] = "testing" # moto has its own credential chain which looks for these s3 and aws access keys
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

import boto3
import pytest
from httpx import ASGITransport, AsyncClient
from moto import mock_aws
from sqlalchemy.ext.asyncio import (AsyncSession, async_sessionmaker,
                                    create_async_engine)
from sqlalchemy.pool import NullPool

from database import Base, get_db
from main import app

pytest_plugins = ["anyio"] # by default pytest only sync functions but this plugin gives a pytest anyio decorator that we put on test functions to tell pytest that this is an async function. anyio is a low level library that manages the async event loops

@pytest.fixture(scope="session") # @pytest.fixture decorator turns a normal function to a fixture. session parameter runs. scope="session" tells pytest: "Create this engine exactly ONCE when the testing suite starts up, share it across every single test file, and destroy it only when all tests are entirely finished."
def anyio_backend():    # fixture called by test functions for isolated Asyncio Event Loop for the test execution block
    return "asyncio"

# Test Engine
@pytest.fixture(scope="session") # scope="session" By default, fixtures have a scope of "function". This means if we have 10 test functions, pytest will run the fixture 10 separate times. we dont want to create  a new engine for each test function , slow and old engines might leave ghost connections. 
def test_engine():  # whenever a test function needs to talk to the database, simply pass test_engine as an argument into the test function's definition, and pytest automatically injects it
    engine = create_async_engine(  # a async link to the test db
        os.environ["DATABASE_URL"],
        poolclass=NullPool, # by deffault SQLAlchemy holds onto database connections in a "pool" to reuse them. In a testing environment, we want absolute isolation. doing this swlalchemy opens up a fresh connection each and prevents tests from leaking data
    )
    return engine

## Setup Database
@pytest.fixture(scope="session")
async def setup_database(test_engine): # creates a db at startup
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all) # run_sync is used as createall expects a sync db connection object but conn is async . run_sync extracts a lowlevel sync socket from conn and injects in createall. it translates the and captures createall commands using greenlet and makes sure it integrates with the network traffic

    yield # pauses till all tests are done

    async with test_engine.begin() as conn: # after all test are done
        await conn.run_sync(Base.metadata.drop_all) # drop the tables

    await test_engine.dispose() # engine cleanup

## DB Session (Transactional Rollback)
@pytest.fixture # no session scope it runs with each test that is function scoped
async def db_session(
    test_engine,
    setup_database,
) -> AsyncGenerator[AsyncSession]:  # type hint that we are returning a session object
    conn = await test_engine.connect()  # creating a connection
    trans = await conn.begin()   # creating a transaction . basically a blank notepad

    test_async_session = async_sessionmaker(  # creating a session that is bound to this connection not to the engine. session is like a managet that sits on top of connection tracks python objects, changes and fires sql query down the connection line
        bind=conn,
        class_=AsyncSession,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint", # its a fake commit. sqlalchemy instead creates a save point, to the app data looks commited but nothing is commited
    )

    async with test_async_session() as session:
        try:
            yield session  # returns the session object to the test funnction . yield here is a generator
        finally:
            await session.close()  # Wipes out the high-level memory object tracking layer.
            await trans.rollback()  # rollsback all changes that the test did 
            await conn.close()


# Mocked AWS
@pytest.fixture       # a library moto intercept any outbound AWS S3 traffic and run a 100% fake, in-memory simulation of Amazon Web Services inside RAM.
def mocked_aws():     # moto mock aws is sync so the function is also sync
    with mock_aws():  # context block closes once the test function is closed 
        s3 = boto3.client("s3", region_name="us-east-1")  # builds a fake s3 client 
        s3.create_bucket(Bucket=os.environ["S3_BUCKET_NAME"])   # a virtual bucket 
        yield s3      # hands the fake s3 client to the test function

## Client Fixture
@pytest.fixture
async def client(
    db_session: AsyncSession,
    mocked_aws,
) -> AsyncGenerator[AsyncClient]:

    async def override_get_db():
        yield db_session   # yields the db_session

    app.dependency_overrides[get_db] = override_get_db # app.dependency_overrides is a dictionary that lets us swap out any depends function for testing. now the routes instead of getting our getdb session they get the transactional session

    async with AsyncClient(  # AsyncClient lets our app send inmemory requests from async clients it simulates  a web browser completely in memory. asyncclient belongs to the httpx library. It calls the internal Python code functions of your FastAPI app directly in memory, gets the response, and hands it back to test in milliseconds. with here acts like a context manager. once the last line is executed it unloads the asyncclient from ram
        transport=ASGITransport(app=app), # we pass our app directly into the client 
        base_url="http://test",  # a dummy url
    ) as ac:
        yield ac # freezes the with block to keep the fake browser ac alive . hands it over to the test function and waits. once test is over it comes back to yield and it executes further down 

    app.dependency_overrides.clear()  # clearing the dependency overrides so they dont leak between tests


## Auth Helpers
async def create_test_user( # creating a dummy user using our api
    client: AsyncClient,
    username: str = "testuser",  # we dont pass these in json as we can just call create_test_user later for other tests
    email: str = "test@example.com",
    password: str = "testpassword123",
) -> dict:
    response = await client.post(
        "/api/users",
        json={  
            "username": username,
            "email": email,
            "password": password,
        },
    )
    assert response.status_code == 201, f"Failed to create user: {response.text}"  # returns this message if it fails to create a user . if success then assert evaluates to true . response.test has the message that the server returned
    return response.json()  # returns user profile details


async def login_user(
    client: AsyncClient,
    email: str = "test@example.com",
    password: str = "testpassword123",
) -> str:
    response = await client.post(
        "/api/users/token",
        data={  # for oauth2 it uses form data. so we use data here
            "username": email,
            "password": password,
        },
    )
    assert response.status_code == 200, f"Failed to login: {response.text}"
    return response.json()["access_token"]  # the function returns the value of the key access token from this server response {"access_token": "eyJhbGciOi...", "token_type": "bearer"} . acess token here is jwt


def auth_header(token: str) -> dict[str, str]:  
    return {"Authorization": f"Bearer {token}"} # the exact format that web browsers send to present a token to the server
 