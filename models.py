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
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)   # mapped acts as a type wrapper and hint for our ide.
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)  # primary_key=True makes it autoincreement. unique=true means no duplicates allowed . nullable=false means it is a required field.
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)  # password_hash for storing password hashes which are required field .
    image_file: Mapped[str | None] = mapped_column(   # image_file: Mapped[str | None] here we just take file name not the url so dir changes doesnt break db.
        String(200),
        nullable=True,
        default=None,
    )

    posts: Mapped[list[Post]] = relationship(
        back_populates="author" ,        # its a one(author or user) to many(posts) link. here back_populates="author" all the user posts are linked to the author field
         cascade="all, delete-orphan", ) # this deletes all the posts of the user when that specific user is deleted

    reset_tokens: Mapped[list[PasswordResetToken]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",  # when a user is deleted all their reset tokens will automatically will be deleted
    )

    @property
    def image_path(self) -> str:  # if the user has a custom picture then use that otherwise use default.
        if self.image_file:
            return f"/media/profile_pics/{self.image_file}"
        return "/static/profile_pics/default.jpg"
    

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
    likes: Mapped[int] = mapped_column(Integer, default=0, server_default="0") # the default=0 is for the sqlalchemy object. server_default="0" is for the database. if we dont define a default then alembic tries to make the row null but we also not allowing that and it would fail. by declaring a server default alembic will include in the generated migration. it is good for exisintg rows that now have to be given some value as likes cannot be null

    author: Mapped[User] = relationship(back_populates="posts")  # a many(posts) to one(user) relationship that links back. we can use something like post.author


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)      # foreign key links th
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)  # for storing the 64 character unique string hash of the token sent to the users mail
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(   # tracks when the token was created
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    user: Mapped[User] = relationship(back_populates="reset_tokens")  # SQLAlchemy Object Relationship created a one(token) to many(user object) relationship and vice versa