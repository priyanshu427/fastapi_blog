## Imports for Users Router
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import models
from database import get_db
from schemas import PostResponse, UserCreate, UserResponse, UserUpdate

router = APIRouter()   # creates a sub-apps which we can include in the main.py.
# by dividing main.py in multiple files using apirouter according to features it makes cleaner and maintable.

# route for create_user
@router.post(
    "",        # the blank string url holds for equal to /api/users . fastapi takes the combined path by joining the /api/users prefix from maiin.py to our router path
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(user: UserCreate, db: Annotated[AsyncSession, Depends(get_db)]):  # (dependency injection) before running the function get db is called and gives a db session and close when the request is completed.
    result = await db.execute(
        select(models.User).where(models.User.username == user.username),  # a select query to check if the user exists. we compare the user.username that we are trying to create to the usernames in db
    )
    existing_user = result.scalars().first()  # get the first user object(here object has everthing like id,ussername,etc) if there is one (existing_user becomes a instance of the user class if there is a match) or none if the user doesnt exist
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists",
        )

    result = await db.execute(
        select(models.User).where(models.User.email == user.email),  # checking for existing email
    )
    existing_email = result.scalars().first()  # we dont use existing_user.email() to check as a none earlier will crash everything
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    new_user = models.User(  # creating new user
        username=user.username,
        email=user.email,
    )
    db.add(new_user)  # await not used as this just adds the new user to the session memory
    await db.commit()
    await db.refresh(new_user)  # await used here as both operate directly on db
    # add inserts the user while commit executes it and saves it. refresh reloads the object from db because a id and date is assigned which the current object in ram doesnt know.
    return new_user

# route for fetching a specific user. 
@router.get("/{user_id}", response_model=UserResponse)
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
@router.patch("/{user_id}", response_model=UserResponse)
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
    if user_update.username is not None and user_update.username != user.username: # checks if the username is not blank and is differnt from existing one then the username is updated
        result = await db.execute(                                                                                 # blank is not considered as update as it will crash at validation during schema check
            select(models.User).where(models.User.username == user_update.username),
        )
        existing_user = result.scalars().first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists",
            )
    if user_update.email is not None and user_update.email != user.email:
        result = await db.execute(
            select(models.User).where(models.User.email == user_update.email),
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
        user.email = user_update.email
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
 