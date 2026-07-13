from fastapi import FastAPI
from fastapi.testclient import TestClient

demo_app = FastAPI()   # creating a temporary mock instance of an app

@demo_app.get("/")  # a get home route
def demo_home():
    return {"message": "Hello"}


client = TestClient(demo_app) # TestClient class wraps application inside a mock HTTP session . it allows us to do fake get,post requests within memory without spinning up uvicorn

def test_homepage():  # pystest detect test_ and executes these. 
    response = client.get("/")  # triggers test client to hit home route of the application
    assert response.status_code == 200  # assert works if given a statement is true then nothing happen test continues , if it false then it raises assertion error .pytest catches that and marks the test as fail

# the test file is mainly for sync unit tests and as our app is async . we need to build test for our specific app   