## models.py
# defines database tables

from __future__ import annotations
# python is an interpreted language that parses from top to bottom and throws a name error if parsing is not completed. this module alters the compilar behavior . it enables forward referencing allowing us to reference user to post model before post is explicitly declared down in file.
from datetime import UTC, datetime
# to get accurate timestamps
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
# importing column types and relations
from sqlalchemy.orm import Mapped, mapped_column, relationship
# relationship helps in traversing and cross table row queries. mapped_column gives constraints.
from database import Base


class User(Base):
    __tablename__ = "users"
# creates a tablename called users.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    image_file: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        default=None,
    )
# mapped acts as a type wrapper and hint for our ide.
# primary_key=True makes it autoincreement. unique=true means no duplicates allowed . nullable=false means it is a required field.
# image_file: Mapped[str | None] here we just take file name not the url so dir changes doesnt break db.

    posts: Mapped[list[Post]] = relationship(
        back_populates="author" ,
         cascade="all, delete-orphan", ) # this deletes all the posts of the user when that specific user is deleted
# its a one(author or user) to many(posts) link. here back_populates="author" all the user posts are linked to the author field
    
    @property
    def image_path(self) -> str:
        if self.image_file:
            return f"/media/profile_pics/{self.image_file}"
        return "/static/profile_pics/default.jpg"
    # if the user has a custom picture then use that otherwise use default.


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), # cross relation between separate and differnt db columns users.id and posts.id. 
        nullable=False,
        index=True,  # the db will look up the user id and query the relevant posts.
    )
    date_posted: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), # It tells SQL to allocate a column type capable of storing date, time, and timezone offset parameters
        default=lambda: datetime.now(UTC), # tells sqlalchemy to not register the date for the post till its published bascially lambda tells to not execute the function till publish is hit. if not the date is just frozen to when the server first started.
    ) 

    author: Mapped[User] = relationship(back_populates="posts")
    # a many(posts) to one(user) relationship that links back. we can use something like post.author