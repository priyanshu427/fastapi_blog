## Imports for Users Router
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import (APIRouter, BackgroundTasks, Depends, HTTPException, Query,
                     UploadFile, status)
from fastapi.security import OAuth2PasswordRequestForm
from PIL import UnidentifiedImageError
from sqlalchemy import delete as sql_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.concurrency import run_in_threadpool

import models
from auth import (CurrentUser, create_access_token, generate_reset_token,
                  hash_password, hash_reset_token, verify_password)
from config import settings
from database import get_db
from email_utils import send_password_reset_email
from image_utils import delete_profile_image, process_profile_image
from schemas import (ChangePasswordRequest, ForgotPasswordRequest,
                     PaginatedPostsResponse, PostResponse,
                     ResetPasswordRequest, Token, UserCreate, UserPrivate,
                     UserPublic, UserUpdate)

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
    # token: Annotated[str, Depends(oauth2_scheme)], # oauth2... takes the token strips word bearer from the request header and drops it in token
    # db: Annotated[AsyncSession, Depends(get_db)], # dont need all this dependencies code till below we already have current user
current_user:CurrentUser):
    return current_user
    
    # """Get the currently authenticated user."""
    # user_id = verify_access_token(token) # check for a valid token 
    # if user_id is None:
    #     raise HTTPException(
    #         status_code=status.HTTP_401_UNAUTHORIZED,
    #         detail="Invalid or expired token",
    #         headers={"WWW-Authenticate": "Bearer"},
    #     )

    # # Validate user_id is a valid integer (defense against malformed JWT)
    # try:  # when we integrate logging using google account or third party accounts the user_id/sub they give can be a abc which if parsed by sqllite will throw internal server error as user_id/sub can only be integer
    #     user_id_int = int(user_id) # python checks here if the user_id it gets can be converted to math integer 1 or not . if yes it saves into useridint. for an input like abc it cannot convert to integer and except block
    # except (TypeError, ValueError):
    #     raise HTTPException(
    #         status_code=status.HTTP_401_UNAUTHORIZED,
    #         detail="Invalid or expired token",
    #         headers={"WWW-Authenticate": "Bearer"},
    #     )

    # result = await db.execute( # checks if the user was maybe deleted but the token exists then it check if that user has a sql alchemy object with them
    #     select(models.User).where(models.User.id == user_id_int), # we use useridint as the userid we get is a string not a integer
    # )
    # user = result.scalars().first()
    # if not user:
    #     raise HTTPException(
    #         status_code=status.HTTP_401_UNAUTHORIZED,
    #         detail="User not found",
    #         headers={"WWW-Authenticate": "Bearer"},
    #     )
    # return user


# route for forgot password . user sends a request to the server 
@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)  # 202 request accepted and will process it but doesnt confirm email
async def forgot_password(
    request_data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,  # BackgroundTasks, the endpoint hands off the heavy lifting to an asynchronous execution worker thread otherwise the browser would just freeze for 1-3 sec for the user as email requires a network round trip
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(   # email check for user
        select(models.User).where(
            func.lower(models.User.email) == request_data.email.lower(),
        ),  
    )
    user = result.scalars().first()

    if user:  # for that user we delete any previous reset tokens incase they request again old tokens are invalid
        await db.execute(
            sql_delete(models.PasswordResetToken).where(
                models.PasswordResetToken.user_id == user.id,
            ),
        )

        token = generate_reset_token()       # generating token
        token_hash = hash_reset_token(token) # hashing token
        expires_at = datetime.now(UTC) + timedelta(  
            minutes=settings.reset_token_expire_minutes
        )

        reset_token = models.PasswordResetToken(  # a reset token is created with all these parameters and a live, tracked SQLAlchemy ORM instance object
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        db.add(reset_token)
        await db.commit()

        background_tasks.add_task(     # using backgroundtask.addtask we are scheduling a email to be sent in background
            send_password_reset_email, # task here is send_password_reset_email function
            to_email=user.email,       # and the required parameters for that task
            username=user.username,
            token=token,               # sending unhashed token so url can be constructed
        )

    return {  # message always shown to the user as soon as the request is received . doesnt matter if backgroundtask is scheduled or any if statement
        "message": "If an account exists with this email, you will receive password reset instructions."  # a generic message to not give hints to attacker like email not found or doesnt exist
    }

# route for reset password . when the user click the link and sends the new password
@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    request_data: ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    token_hash = hash_reset_token(request_data.token)  # hashing the subimtted token

    result = await db.execute(  # comparing the hashed token to the hash in db
        select(models.PasswordResetToken).where(
            models.PasswordResetToken.token_hash == token_hash,
        ),
    )
    reset_token = result.scalars().first()

    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",   # generic message
        )

    if reset_token.expires_at.replace(tzinfo=UTC) < datetime.now(UTC):  # sqllite stores datetimes but doesnt store timezone info it strips that out and cannot compare directly with datetime. replace adds the timezone
        await db.delete(reset_token)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    result = await db.execute(  # checking if the user exists . the user might have deleted acc incase
        select(models.User).where(models.User.id == reset_token.user_id),
    )
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    user.password_hash = hash_password(request_data.new_password)  # hashing the new password and updating it for that user

    await db.execute(  # deleting all reset tokens for the user
        sql_delete(models.PasswordResetToken).where(
            models.PasswordResetToken.user_id == user.id,
        ),
    )

    await db.commit()
    return {
        "message": "Password reset successfully. You can now log in with your new password."
    }
   

#route for change password for logged in users
@router.patch("/me/password", status_code=status.HTTP_200_OK)  # /me makes that no authorization checks are needed. its just a url name but is best practice and creates a clean logical group of endpoints
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if not verify_password(password_data.current_password, current_user.password_hash):  # verifying current password
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    current_user.password_hash = hash_password(password_data.new_password) # hashing the new password and storing it

    await db.execute(
        sql_delete(models.PasswordResetToken).where(
            models.PasswordResetToken.user_id == current_user.id,
        ),
    )

    await db.commit()
    return {"message": "Password changed successfully"}
   

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

# route : we fetch all the posts of a specific user(paginated)
@router.get("/{user_id}/posts", response_model=PaginatedPostsResponse) # used list as fetching from db the data is not organized and sql alchemy have meta data. now used PaginatedPostsResponse schema
async def get_user_posts(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = settings.posts_per_page,
):
    result = await db.execute(select(models.User).where(models.User.id == user_id)) # we check if the user exists or not before querying for all posts
    user = result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    count_result = await db.execute(
        select(func.count())
        .select_from(models.Post)
        .where(models.Post.user_id == user_id), # counting posts for the speicifc user
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(models.Post)
        .options(selectinload(models.Post.author))
        .where(models.Post.user_id == user_id)
        .order_by(models.Post.date_posted.desc())
        .offset(skip)
        .limit(limit),
    )
    posts = result.scalars().all()

    has_more = skip + len(posts) < total

    return PaginatedPostsResponse(
        posts=[PostResponse.model_validate(post) for post in posts],
        total=total,
        skip=skip,
        limit=limit,
        has_more=has_more,
    )

# route for updating users
@router.patch("/{user_id}", response_model=UserPrivate)
async def update_user(
    user_id: int,
    user_update: UserUpdate,            # takes the validation from userupdate
    current_user:CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if user_id != current_user.id:  # ownership check
        raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Not authorized to update this user",
            )

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
    # if user_update.image_file is not None: # not rewuired as image_file is removed from schema
    #     user.image_file = user_update.image_file 

    await db.commit()
    await db.refresh(user)
    return user


# route for deleting a user and all their posts
@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, current_user:CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]
                      ):
    if user_id != current_user.id:  # ownership check
        raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Not authorized to delete this user",
            )
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    old_filename = user.image_file

    await db.delete(user)  # await is used here as the db will have to cascades delete the posts of the user in the relationship.
    await db.commit()

    if old_filename :      # deleting the profile image after commit incase commit fails
     delete_profile_image(old_filename) 

# route for updating a profile image file
@router.patch("/{user_id}/picture", response_model=UserPrivate)
async def upload_profile_picture(
    user_id: int,
    file: UploadFile, # UploadFile a special type in fastapi for handling file uploads. if the file uploads in ram are too much it offloads it to harddisk
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this user's picture",
        )

    content = await file.read() # reading the file content. await is used as reading the file from disk takes time

    if len(content) > settings.max_upload_size_bytes:  # checking file size if the file is too long according to our setting > 5mb then we throw error
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size is {settings.max_upload_size_bytes // (1024 * 1024)}MB",
        )

    try:  # image processing is a cpubound work so we keep our function process_profile_image in the run_in_threadpool function which offloads it in a thread pool while keeping our endpoint async otherwise it would have blocked the main event loop
        new_filename = await run_in_threadpool(process_profile_image, content) # await pauses the req of the current user till the image is processed in a differnt background thread . process_profile_image also saves the file in our hardrive
    except UnidentifiedImageError as err:   # if file is not an image its caught here
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image file. Please upload a valid image (JPEG, PNG, GIF, WebP).",
        ) from err

    old_filename = current_user.image_file  # default filename of the user in db

    current_user.image_file = new_filename  # replacing the old filename with newfilename
    await db.commit()
    await db.refresh(current_user) # we save the new file first so that incase we failed db commit then atleast we still have users old profile pic

    if old_filename: # after successful commit then we delete the old profile image file
        delete_profile_image(old_filename)

    return current_user

#route for Deleting Profile Picture 
@router.delete("/{user_id}/picture", response_model=UserPrivate)
async def delete_user_picture(
    user_id: int,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this user's picture",
        )

    old_filename = current_user.image_file # fetches the image file of the current user

    if old_filename is None:  # check for if a image exists for that user or not
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No profile picture to delete",
        )

    current_user.image_file = None # none here means default image path
    await db.commit()
    await db.refresh(current_user)

    delete_profile_image(old_filename)  # once the filename is gone then we delete the actual file

    return current_user
