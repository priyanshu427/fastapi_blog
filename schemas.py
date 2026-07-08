from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    email: EmailStr = Field(max_length=120)   # EmailStr validates from pydantic that its in proper email format 

class UserCreate(UserBase):
    password: str = Field(min_length=8)


class UserPublic(BaseModel):   # when someone else wants to see a authorss posts but shouldnt see authors private email so we cannot inherit from userbase
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    image_file: str | None
    image_path: str # image_path is a property on user model
    # includes all these for response model
    

class UserPrivate(UserPublic):   # response model for when the author wants to view their own details and posts    
    email: EmailStr

class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=50)
    email: EmailStr | None = Field(default=None, max_length=120)
    # image_file: str | None = Field(default=None, min_length=1, max_length=200)   # removed as it can be a security vulnerability that someone could guess an existing filename. declared a dedicated file: UploadFile parameter in our function argument
# schema used incoming json data from patch request of the user path

class Token(BaseModel):  # for login responses
    access_token: str    # holds a cryptographically signed, unreadable string of text characters which holds metadata of config.py 
    token_type: str      

class PostBase(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1)
    # author: str = Field(min_length=1, max_length=50) # not needed as it comes from relationship
# master blueprint : Every single post in our entire system MUST have a title, content, and an author. No exceptions, and they all must be text strings.

class PostCreate(PostBase):  # takes the incoming json data from the browser and runs it through the constraints. if validaton is passed , data is sent into the function.
    pass     # user_id is removed as we are using dependency injection to get the current logged in user sqlalchemy object

class PostUpdate(BaseModel): # takes the incominng json for patch and runs that given field data with this schema
    title: str | None = Field(default=None,min_length=1, max_length=100)
    content: str | None = Field(default=None,min_length=1)

class PostResponse(PostBase):
    model_config = ConfigDict(from_attributes=True)   # to change pydantic behaviour as it can only read python dictionaries.

    id: int
    user_id: int
    date_posted: datetime
    author: UserPublic # we get nested json with all the things in userresponse/(userpublic now).
    # after the execution of the function and retrun new_post. FastAPI intercepts that returned variable and pushes it through the PostResponse schema filter. it ensures payload matches the criteria and adds id and date_posted and its sent to the browser.


class PaginatedPostsResponse(BaseModel): # response model for paginated  
    posts: list[PostResponse]  # post data
    total: int      # total no. of posts in db
    skip: int       # offset tells where to start reading posts in db from
    limit: int      # no. of posts requested
    has_more: bool  # tell if there are more posts after this batch. for frontend to show the load more button or not

    