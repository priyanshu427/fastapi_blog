## Imports for Users Router
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import models
from auth import (create_access_token, hash_password, oauth2_scheme,
                  verify_access_token, verify_password)
from config import settings
from database import get_db
from schemas import (PostResponse, Token, UserCreate, UserPrivate, UserPublic,
                     UserUpdate)

router = APIRouter()   # creates a sub-apps which we can include in the main.py.
# by dividing main.py in multiple files using apirouter according to features it makes cleaner and maintable.

# route for create_user
@router.post(
    "",        # the blank string url holds for equal to /api/users . fastapi takes the combined path by joining the /api/users prefix from maiin.py to our router path
    response_model=UserPrivate,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(user: UserCreate, db: Annotated[AsyncSession, Depends(get_db)]):  # (dependency injection) before running the function get db is called and gives a db session and close when the request is completed.
    result = await db.execute(
        select(models.User).where(
            func.lower(models.User.username) == user.username.lower()),  # a select query to check if the user exists. we compare the user.username that we are trying to create to the usernames in db
    )   # we use lowercase checks to prevent duplicate usernames and impersonation . func here is a native db command that checks for lowercase in db
    existing_user = result.scalars().first()  # get the first user object(here object has everthing like id,ussername,etc) if there is one (existing_user becomes a instance of the user class if there is a match) or none if the user doesnt exist
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists",
        )

    result = await db.execute(
        select(models.User).where(func.lower(models.User.email) == user.email.lower()),  # checking for existing email and also checks in lowercase as emailstr in userprivate only lowercases the domain like gmail.com . in modern world gmails are case insensitive.
    )
    existing_email = result.scalars().first()  # we dont use existing_user.email() to check as a none earlier will crash everything
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    new_user = models.User(  # creating new user
        username=user.username,
        email=user.email.lower(),
        password_hash=hash_password(user.password), # storing password safely using our hash function
    )
    db.add(new_user)  # await not used as this just adds the new user to the session memory
    await db.commit()
    await db.refresh(new_user)  # await used here as both operate directly on db
    # add inserts the user while commit executes it and saves it. refresh reloads the object from db because a id and date is assigned which the current object in ram doesnt know.
    return new_user

# login_for_access_token
@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()], # OAuth2pass... handles parsing the form data and its a global standard for login requests that are sent as form data. otherwise we use a staandard pydantic schema model that reads json
    db: Annotated[AsyncSession, Depends(get_db)],               # OAuth2pass... then extract the string that user types and then packs in obj supplies it to form_data
):
    # Look up user by email (case-insensitive)
    # Note: OAuth2PasswordRequestForm uses "username" field, but we treat it as email. it only has that username field but can be used universally
    result = await db.execute(
        select(models.User).where(
            func.lower(models.User.email) == form_data.username.lower(), # as all fields are named .username we use email-only login approach
        ),
    )
    user = result.scalars().first()

    # Verify user exists and password is correct
    # Don't reveal which one failed (security best practice)
    if not user or not verify_password(form_data.password, user.password_hash): # oauthpass... intially dumps the username and password in the form_data. after the above query if the user has the sqlalchemy it results to true. only checks passowrd if user is true.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",   # a generic error to not reveal an attacker if an email exists in our system or not
            headers={"WWW-Authenticate": "Bearer"}, # legal requirement that the server cant just say no and has to explain entry requirements . here it said access denied and not logged in. a valid/bearer token is required and redirects to the login screen
        )

    # Create access token with user id as subject
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes) # expiration time from setings and convert into timedelta object
    access_token = create_access_token( # returning parameters to the token generating function
        data={"sub": str(user.id)},     # we pass the user.id in sub and it should be string in jwt. data here is a dictionary created
        expires_delta=access_token_expires, # specific expiration time
    )
    return Token(access_token=access_token, token_type="bearer") # validated by token schema . we send this token to the browser and label as bearer so the browser can save the token in its local memory

# route for getting the current logged in user.
@router.get("/me", response_model=UserPrivate) # the frontend sends the jwt token straight to this route /api/users/me. the server decodes token and sends profile data of that logged in user using that jwt
async def get_current_user(  # we place this route above all variable routes cuz if me goes in like {user_id} it would throw a validation error. if url is /me this route is taken
    token: Annotated[str, Depends(oauth2_scheme)], # oauth2... takes the token strips word bearer from the request header and drops it in token
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get the currently authenticated user."""
    user_id = verify_access_token(token) # check for a valid token 
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate user_id is a valid integer (defense against malformed JWT)
    try:  # when we integrate logging using google account or third party accounts the user_id/sub they give can be a abc which if parsed by sqllite will throw internal server error as user_id/sub can only be integer
        user_id_int = int(user_id) # python checks here if the user_id it gets can be converted to math integer 1 or not . if yes it saves into useridint. for an input like abc it cannot convert to integer and except block
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute( # checks if the user was maybe deleted but the token exists then it check if that user has a sql alchemy object with them
        select(models.User).where(models.User.id == user_id_int), # we use useridint as the userid we get is a string not a integer
    )
    user = result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

# route for fetching a specific user. 
@router.get("/{user_id}", response_model=UserPublic)
async def get_user(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(
        select(models.User).where(models.User.id == user_id) # we compare the user.id table in models to the current user_id to check if the user exists or not.
    )
    user = result.scalars().first()
    if user:
        return user
    # return {"error": "post not found"} # this line is bad as our dev server shows 200(success) instead of a 404(error) as the resource wasnt found at that id.
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

# route : we fetch all the posts of a specific user
@router.get("/{user_id}/posts", response_model=list[PostResponse]) # used list as fetching from db the data is not organized and sql alchemy have meta data.
async def get_user_posts(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.User).where(models.User.id == user_id)) # we check if the user exists or not before querying for all posts
    user = result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    result = await db.execute(
        select(models.Post)
        .options(selectinload(models.Post.author))
        .where(models.Post.user_id == user_id)
        .order_by(models.Post.date_posted.desc()),
    )
    posts = result.scalars().all()
    return posts

# route for updating users
@router.patch("/{user_id}", response_model=UserPrivate)
async def update_user(
    user_id: int,
    user_update: UserUpdate,                                   # takes the validation from userupdate
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(models.User).where(models.User.id == user_id)) # checks if the user exists or not
    user = result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if user_update.username is not None and user_update.username.lower() != user.username.lower(): # checks if the username is not blank and is differnt from existing one then the username is updated
        result = await db.execute(                                                                                 # blank is not considered as update as it will crash at validation during schema check
            select(models.User).where(
                func.lower(models.User.username) == user_update.username.lower()),
        )
        existing_user = result.scalars().first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists",
            )
    if user_update.email is not None and user_update.email.lower() != user.email.lower():
        result = await db.execute(
            select(models.User).where(func.lower(models.User.email) == user_update.email.lower()),
        )
        existing_email = result.scalars().first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

    if user_update.username is not None:          # can be done using setattr and dict iteration
        user.username = user_update.username
    if user_update.email is not None:
        user.email = user_update.email.lower()
    if user_update.image_file is not None:
        user.image_file = user_update.image_file

    await db.commit()
    await db.refresh(user)
    return user


# route for deleting a user and all their posts
@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    await db.delete(user)  # await is used here as the db will have to cascades delete the posts of the user in the relationship.
    await db.commit()
 