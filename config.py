from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):    # inheriting from basesettings class gives us the power to look outside the python script and look into the OS to scan for computer system environment variables
    # basesettingss also checks validation like token expiration and throws error. Finally basesettings maps the variables automatically
    model_config = SettingsConfigDict(  # SettingsConfigDict is the onfiguration dictionary inside the class that tells BaseSettings exactly where to look for your hidden files.
        env_file=".env",   # looks for .env file in the project folder
        env_file_encoding="utf-8",  # tells pydantic use utf-8 dictionary to use for decoding the complex cryptographic secret key containing random symbols
    )

    secret_key: SecretStr   # prevents accidental display of secret key if settings or server logs get accidently printed 
    algorithm: str = "HS256" # specifes what algorithm will be used on the secret_key + input data of user and run it in a hs256 stands for HMAC using SHA-256 and generates a signature string . when server receives jwt this algo validates if its from that user.
    access_token_expire_minutes: int = 30 # gives the login token a expiration time

    max_upload_size_bytes: int = 5 * 1024 * 1024 # restricts file uploads to 5mb and protects server from large file uploads

    posts_per_page: int = 10
    

settings = Settings()  # Loaded from .env file # object settings is made for convinience so that it can imported to any file and Pydantic opens, reads, validates, and processes .env file exactly ONCE at the moment the server boots up. next time it just picks the settings obj from ram to check anything like token expiration
# settings loads up the values from .env but if it doesnt find any value it default to the ones we give here like algorithm hs256