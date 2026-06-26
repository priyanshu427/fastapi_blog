from pydantic import BaseModel, ConfigDict, Field, EmailStr
from datetime import datetime

class UserBase(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    email: EmailStr = Field(max_length=120)
# EmailStr validates from pydantic that its in proper email format 

class UserCreate(UserBase):
    pass


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    image_file: str | None
    image_path: str # image_path is a property on user model
    # includes all these for response model

class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=50)
    email: EmailStr | None = Field(default=None, max_length=120)
    image_file: str | None = Field(default=None, min_length=1, max_length=200)    
# schema used incoming json data from patch request of the user path


class PostBase(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1)
    # author: str = Field(min_length=1, max_length=50) # not needed as it comes from relationship
# master blueprint : Every single post in our entire system MUST have a title, content, and an author. No exceptions, and they all must be text strings.

class PostCreate(PostBase):
    user_id: int # temporary

# takes the incoming json data from the browser and runs it through the constraints. if validaton is passed , data is sent into the function.

class PostUpdate(BaseModel): # takes the incominng json for patch and runs that given field data with this schema
    title: str | None = Field(default=None,min_length=1, max_length=100)
    content: str | None = Field(default=None,min_length=1)

class PostResponse(PostBase):
    model_config = ConfigDict(from_attributes=True)
# to change pydantic behaviour as it can only read python dictionaries.

    id: int
    user_id: int
    date_posted: datetime
    author: UserResponse # we get nested json with all the things in userresponse.
    # after the execution of the function and retrun new_post. FastAPI intercepts that returned variable and pushes it through the PostResponse schema filter. it ensures payload matches the criteria and adds id and date_posted and its sent to the browser.
    