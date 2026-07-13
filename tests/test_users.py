from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from tests.conftest import auth_header, create_test_user, login_user


## Test Create User Validation Error
@pytest.mark.anyio
async def test_create_user_validation_error(client: AsyncClient): # missing credentials
    response = await client.post(
        "/api/users",
        json={
            "username": "testuser", # password and email missing 
        },
    )

    assert response.status_code == 422
    assert "email" in response.text  # we check if the json response have email or password which is does but pydantic alidation error specifies exactly which fields failed ("loc": ["body", "email"] and "loc": ["body", "password"]), the substrings match perfectly
    assert "password" in response.text


## Test Create User Duplicate Email
@pytest.mark.anyio
async def test_create_user_duplicate_email(client: AsyncClient):
    await create_test_user(client) # creating a user

    response = await client.post(  # creating a diff user but same email
        "/api/users",
        json={
            "username": "different_user",
            "email": "test@example.com",
            "password": "password123",
        },
    )

    assert response.status_code == 400  # data is correct but breaks rules
    assert response.json()["detail"] == "Email already registered"


## Test Create User Success
@pytest.mark.anyio
async def test_create_user_success(client: AsyncClient):
    response = await client.post(
        "/api/users",
        json={
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "securepassword123",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "newuser"
    assert data["email"] == "newuser@example.com"
    assert "id" in data
    assert "image_path" in data
    assert "password" not in data
    assert "password_hash" not in data


## Test Upload Profile Picture
@pytest.mark.anyio
async def test_upload_profile_picture(client: AsyncClient, mocked_aws):
    user = await create_test_user(client)
    token = await login_user(client)

    test_image_path = Path(__file__).parent / "test_image.jpg"  # reading test image from disk . Path(__file__).  getting the path to the current test file and the parent gets our test directory and then we get the test img from our test dir
    image_bytes = test_image_path.read_bytes() # raw image bytes

    response = await client.patch(
        f"/api/users/{user['id']}/picture",
        files={"file": ("profile.jpg", BytesIO(image_bytes), "image/jpeg")}, # we have file which tells httpx to send it as multi part form data like a file upload. the tuple has file name, image bytes and img type
        headers=auth_header(token), 
    )

    assert response.status_code == 200
    data = response.json()
    assert data["image_file"] is not None
    assert data["image_file"].endswith(".jpg")
    assert "s3" in data["image_path"]  # should have s3 as it is a s3 url  

    s3_objects = mocked_aws.list_objects_v2(Bucket="test-bucket") # creating a test bucket and using mocked aws to take requests
    assert "Contents" in s3_objects  # Amazon's API returns a dictionary containing a key named "Contents". If the bucket is completely empty, that key won't even exist. This line proves that something was successfully written to the virtual memory.
    assert len(s3_objects["Contents"]) == 1  # checking if there is one obj in the bucket that means only one file was uploaded
    assert s3_objects["Contents"][0]["Key"].endswith(data["image_file"])  # [0] grabs the first fie in list, path name [key] and compares the filename that was generated and saved in our db


## Test Forgot Password Sends Email
@pytest.mark.anyio
async def test_forgot_password_sends_email(client: AsyncClient):
    await create_test_user(client)

    with patch(  # patch is here from unittest.mock and is acting as a contest manager
        "routers.users.send_password_reset_email", # send_password_reset_email lives in email utils. but our routers.users routes using that function from its module namespace . so we have same function pointing at two different places. we can use email utils but our route hander will still use the function from its namespace.
        new_callable=AsyncMock,  # using async mock as email func is async . when we mock the rule is we patch where the func was looked up not where it was defined
    ) as mock_send:  # whenever send_password_reset_email is executed patch freezes it and replaces with a dummy object mock_send
        response = await client.post(
            "/api/users/forgot-password",
            json={"email": "test@example.com"},
        )

        assert response.status_code == 202
        mock_send.assert_awaited_once()  # we check if the mock was awaited once or not. our backgrond_task is the one that awaits and that await is passed here
        call_kwargs = mock_send.call_args.kwargs # Whenever a mock object is called in Python, it acts like a recorder. It automatically logs all arguments passed into it inside an internal property called call_args. .kwargs gets the dict that has all the parameter values that API passed into that function.
        assert call_kwargs["to_email"] == "test@example.com"
        assert call_kwargs["username"] == "testuser"
        assert "token" in call_kwargs