from datetime import UTC, datetime, timedelta

import jwt
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash

from config import settings

password_hash = PasswordHash.recommended() # creates a password hasher using argon2 . recommended just selets the best currenty security standards like argon2id for hashing 

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/users/token") # OAuth2PasswordBearer extracts the jwt token from the header of the login http path which is api/users/token.
# also gives us a authorize button in docs which makes testing easier

def hash_password(password: str) -> str:  # takes in a plain test password and returns a hash . 
    return password_hash.hash(password)   # password :str here is just type hints for the vscode and human documentation. -> is the return type of the function that isnt necesary but tells vscode that if we use this function anywhere across codebase it knows its output is a string

def verify_password(plain_password: str, hashed_password: str)->bool:  # takes the plain password and the hashed one and compares if they are match or not. 
    return password_hash.verify(plain_password,hashed_password)

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str: # data:dict takes the python dictionary out of the user info that we put in payload of login route ourselves. expires_delta is when we want to create a custom token for a different amount of time. return type for jwt is a string
    """Create a JWT access token."""
    to_encode = data.copy()  # we copy/clone the payload dictionary so that the data doesnt modify user objects somewhere else in the program
    if expires_delta:        # token lifespan calculator. if expires delta has a value a custom token is created in the if block. if expiresdelta is none then it goes to else.
        expire = datetime.now(UTC) + expires_delta 
    else:
        expire = datetime.now(UTC) + timedelta(
            minutes=settings.access_token_expire_minutes, # takes the default time provided in config.py if no custom expiredelta expire time isnt provided
        )
    to_encode.update({"exp": expire}) # injects expire time directly in the data dictionary. exp is standardized in jwt security
    encoded_jwt = jwt.encode( # here the library already has the header . it converts both the header and payload into Base64 strings and blends it with the secret key
        to_encode,
        settings.secret_key.get_secret_value(), # getsecret value is required to unmask the secret key here as it has a safety blanket called secretstr
        algorithm=settings.algorithm,
    )
    return encoded_jwt

def verify_access_token(token: str) -> str | None: # takes the base64 string as an argument. type hint of str|none means it can return either the user_id if token is legimate or none if the token is broken, altered, fake, or expired.
    """Verify a JWT access token and return the subject (user id) if valid."""
    try:
        payload = jwt.decode( # jwt.decode takes the secret key,splits the header and payload and does base64 decode. now it hashes using the algo and compares that hash to the signature part in the token. if it matches no error straight to else block, if error then catch block
            token,            # jwt.decode also checks the expiration time and rejects if exp is missing 
            settings.secret_key.get_secret_value(),
            algorithms=[settings.algorithm],
            options={"require": ["exp", "sub"]}, # enforces strict rules that token should have a expiration and a unique user_id 
        )
    except jwt.InvalidTokenError: # throws InvalidTokenError if token expired,bad signature ,etc 
        return None  # signals endpoint user is either unaunthenticated or expired token
    else:
        return payload.get("sub")  # if no error in the try block it takes the decoded payload and gets the user_id and returns it to the route to give permission to edit,delete blog,etc
    
