import pytest
from httpx import AsyncClient

from tests.conftest import auth_header, create_test_user, login_user


@pytest.mark.anyio  # this decorator tells pytest to run as async function
async def test_get_posts_empty(client:AsyncClient): # pytest when reaches client looks up for conftest.py finds client runs it and gets a value then injects it here
    response = await client.get("api/posts")  # test for sending a get request

    assert response.status_code == 200
    data = response.json() # parses the json response the server sends into a dictionary which python can read
    assert data["posts"] == [] # we are testing integrity here that our posts are empty and total=o so we can guarrentee that the endpoint is drawing from a isolated environment that has 0 records
    assert data["total"] == 0
    assert data["has_more"] is False  # for pagination as our list of posts is empty


@pytest.mark.anyio
async def test_get_posts_not_found(client:AsyncClient):  # test to try and fetch a post that doesnt exist
    response = await client.get("api/posts/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Post not found"
    

## Test Create Post Success
@pytest.mark.anyio
async def test_create_post_success(client: AsyncClient):
    user = await create_test_user(client)  # calling create_test_user
    token = await login_user(client)       # logging in and getting the token 
    headers = auth_header(token)           # building authorization header using the token 

    response = await client.post(
        "/api/posts",
        json={"title": "My First Post", "content": "This is the content"},
        headers=headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "My First Post"
    assert data["content"] == "This is the content"
    assert data["user_id"] == user["id"]
    assert "id" in data
    assert "date_posted" in data
    assert data["author"]["username"] == "testuser"  # checking if the correct user is populated with the author relationship


## Test Create Post Unauthorized
@pytest.mark.anyio
async def test_create_post_unauthorized(client: AsyncClient):  # when a request is made without a authorized user
    response = await client.post(
        "/api/posts",
        json={"title": "Test Post", "content": "Test content"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


## Test Update Post Success
@pytest.mark.anyio
async def test_update_post_success(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)

    response = await client.post(
        "/api/posts",
        json={"title": "Original Title", "content": "Original content"},
        headers=headers,
    )
    post_id = response.json()["id"] # extracting post id from response

    response = await client.patch(
        f"/api/posts/{post_id}",
        json={"title": "Updated Title"},
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["content"] == "Original content"



## Test Update Post Wrong User
@pytest.mark.anyio
async def test_update_post_wrong_user(client: AsyncClient): # testing what permission the user has 
    await create_test_user(client, username="user1", email="user1@example.com")  # creating user 1 and using default password 
    token1 = await login_user(client, email="user1@example.com")

    response = await client.post(
        "/api/posts",
        json={"title": "User 1's Post", "content": "Only user 1 can edit this"},
        headers=auth_header(token1),
    )
    post_id = response.json()["id"]

    await create_test_user(client, username="user2", email="user2@example.com")
    token2 = await login_user(client, email="user2@example.com")

    response = await client.patch(   # we try to update the post that user1 created by using user2
        f"/api/posts/{post_id}",
        json={"title": "Hacked Title"},
        headers=auth_header(token2),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to update this post"


## Test Pagination
@pytest.mark.anyio
async def test_get_posts_with_pagination(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)

    for i in range(5):  # creating 5 posts
        response = await client.post(
            "/api/posts",
            json={"title": f"Post {i}", "content": f"Content for post {i}"},
            headers=headers,
        )
        assert response.status_code == 201 # each one returns a 201

    response = await client.get("/api/posts")  # checking default behavior with no parameters like limiit
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["posts"]) == 5
    assert data["has_more"] is False

    response = await client.get("/api/posts?limit=2")  # checking we get atmost 2 posts
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["posts"]) == 2
    assert data["has_more"] is True

    response = await client.get("/api/posts?skip=2&limit=2") 
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["posts"]) == 2
    assert data["skip"] == 2
    assert data["limit"] == 2
