## Imports for Posts Router
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import models
from database import get_db
from schemas import PostCreate, PostResponse, PostUpdate

router = APIRouter()


# Route for querying all posts and fetching them
@router.get("", response_model=list[PostResponse])   # .get() is an HTTP Method Router. it is used for reading data.
async def get_posts(db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(
        select(models.Post)
        .options(selectinload(models.Post.author))
        .order_by(models.Post.date_posted.desc()),   # tells sql alchemy to arrange posts by the dateposted field that is newest to first.
    )
    posts = result.scalars().all()
    return posts        # returns posts ,(previously) another dummy data in json from this route. now sends data to the response model


# for creating posts by their user_id 
@router.post(                                 # a POST request means "Here is some new data, take it and store it." 
    "",  
    response_model=PostResponse,           # Response model specifies that when we return new_post, it sends the json data to the PostResponse class for validation.
    status_code=status.HTTP_201_CREATED,
) 
async def create_post(post: PostCreate, db: Annotated[AsyncSession, Depends(get_db)]): # Take the incoming JSON data from the internet, run it through the PostCreate bouncer, and convert it into a Python object named post
    # new_id = max(p["id"] for p in posts) + 1 if posts else 1     # manual way of assigning ids
     
    # new_post = {"id": new_id, "author": post.author, "title": post.title, "content": post.content, "date_posted": "April 23, 2025",} 
    # post.author fetches only the dictionary key author and assigns its corresponding value to the new dict.
    # The incoming parameter is defined as post: PostCreate. Because it passes through Pydantic first, post is not a dictionary anymore—it is an Object Instance of the PostCreate class.
    # Because it’s a Python object instance, we use dot-notation (post.author) to read its attributes, rather than dictionary brackets (post["author"]). Pydantic read the original user JSON key, validated it, and attached it to that object property for you to grab.
    # posts.append(new_post) #It's added to our dictionary list using append temporarily as there is no database yet.
    # return new_post
    result = await db.execute(
        select(models.User).where(models.User.id == post.user_id),
    )
    user = result.scalars().first()     # user :(The SQLAlchemy query result): Contains the full, live database record for that user.
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    new_post = models.Post(
        title=post.title,
        content=post.content,
        user_id=post.user_id,
    )
    db.add(new_post)
    await db.commit()
    await db.refresh(new_post, attribute_names=["author"])  # when sqlalchemy fetches the posts table it doesnt fetch a linked column. in our schema for postresponse we need a author field . here attribute_names=["author"] sqlalchemy goes down to the user_id of the post and stiches the data from the users table to the .author
    return new_post

## get_post
# Route for querying for a specific post that matches post_id
@router.get("/{post_id}", response_model=PostResponse)
async def get_post(post_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(
        select(models.Post)
        .options(selectinload(models.Post.author))
        .where(models.Post.id == post_id),
    )
    post = result.scalars().first()
    if post:
        return post              # return {"error": "post not found"} # this line is bad as our dev server shows 200(success) instead of a 404(error) as the resource wasnt found at that id.
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
# fastapi automatically provides path validation by displaying a error for wrong type like string when only int is valid.
# return here is not used as python assumes the post_id is invalid but code is flawless hence throws a 404 instead of a 200 on the dev server.


# route for full updating a users posts
@router.put("/{post_id}", response_model=PostResponse)
async def update_post_full(
    post_id: int,
    post_data: PostCreate, # we need the user to fill all fields for the put request and schema check . 
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(models.Post).where(models.Post.id == post_id))
    post = result.scalars().first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )
    if post_data.user_id != post.user_id: # right now the app doesnt have a login so user_id can be different for now.
        result = await db.execute(              # we check the user_id of the post incoming to the existing post in db . if user_id matches then all good if it doesnt then we assign that user the post after checking that the user actually exists.
            select(models.User).where(models.User.id == post_data.user_id),
        )
        user = result.scalars().first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

    post.title = post_data.title # all fields are replaced in put regarldless same or different.
    post.content = post_data.content
    post.user_id = post_data.user_id
# in the case the post was from a different user_id and not from the owner the post is updated and reassigned to the user while the previous user loses that post.

    await db.commit()
    await db.refresh(post, attribute_names=["author"])
    return post


#route for partially updating a users post
@router.patch("/{post_id}", response_model=PostResponse)
async def update_post_partial(
    post_id: int,
    post_data: PostUpdate, # we need the user to fill all fields for the put request and schema check . 
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(models.Post).where(models.Post.id == post_id))
    post = result.scalars().first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )

    update_data = post_data.model_dump(exclude_unset=True)   # model_dump a pydantic tool that converts incoming json to a dictionary. exclude_unset=True means that any fields left empty by user are not taken in dict.
    for field, value in update_data.items():
        setattr(post, field, value)                        # does the same thing as assigning the fields that user gave input for. (post,field,value) for that post set the field to the value that the user sent
                                                          # if a user_id doesnt exist that sent the patch req the db will throw error and blocks save.
    await db.commit()                                           # if the user_id is differnt and the post registered in a different user_id then the post gets transferrred to that user making put request.
    await db.refresh(post, attribute_names=["author"])
    return post


# route for deleting a post
@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT) # 204 means success but no response body
async def delete_post(post_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.Post).where(models.Post.id == post_id))
    post = result.scalars().first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )

    await db.delete(post)
    await db.commit()