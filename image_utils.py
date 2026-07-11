import uuid
from io import BytesIO

import boto3
from PIL import Image, ImageOps
from starlette.concurrency import run_in_threadpool

from config import settings

# from pathlib import Path # now we not working with filesystem
# PROFILE_PICS_DIR = Path("media/profile_pics")


def _get_s3_client():    # _get underscore in front is a industry standard for a private helper function. this should be imported or called and run only in this specific file
    return boto3.client(    # tells boto3 to boot up a interface specifically tailored for talking to the S3 storage service
        "s3",
        region_name=settings.s3_region,  # the code routes travel directly to the data center whr the bucket lives (mumbai data center)
        aws_access_key_id=(
            settings.s3_access_key_id.get_secret_value()
            if settings.s3_access_key_id
            else None     # prevents app from crashing if keys cannot be found 
        ),
        aws_secret_access_key=(
            settings.s3_secret_access_key.get_secret_value()
            if settings.s3_secret_access_key
            else None
        ),
        endpoint_url=settings.s3_endpoint_url,   # By default, Boto3 points directly to the real, live Amazon cloud. but including a endpoint_url variable that defaults to None makes so we test locally by changing url
    )


def process_profile_image(content: bytes) -> tuple[bytes, str]:  # for image processing across different parameters. we return bytes for the raw data payload and str for filename. tuple is used to make a paired package
    with Image.open(BytesIO(content)) as original:
        img = ImageOps.exif_transpose(original)

        img = ImageOps.fit(img, (300, 300), method=Image.Resampling.LANCZOS)

        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")

        filename = f"{uuid.uuid4().hex}.jpg" # file name generator to prevent collisions
                                                  # filepath = PROFILE_PICS_DIR / filename

        output = BytesIO()  # bytes io create a temporary file in the ram of trick pillow. otherwise it would need a filepath to the physical storage and then we have to grab from there which is time taking

                                                   # PROFILE_PICS_DIR.mkdir(parents=True, exist_ok=True)

        img.save(output, "JPEG", quality=85, optimize=True)  
        output.seek(0)  # sets the pointer to the first byte so  we can read it

    return output.read(), filename  # retuns the image bytes out of ram and filename

# def delete_profile_image(filename: str | None) -> None: # for deleting a image when user updates or deletes acc
#     if filename is None:
#         return

#     filepath = PROFILE_PICS_DIR / filename
#     if filepath.exists():
#         filepath.unlink()


def _upload_to_s3(file_bytes: bytes, key: str) -> None: # takes the images bytes in ram and streams it directly up to the AWS S3 bucket
    s3 = _get_s3_client()   # spinning up a boto3 connection to mumbai data center
    s3.upload_fileobj(      
        BytesIO(file_bytes), # reads the bytes of the ram from the teporary file in ram called bytesio
        settings.s3_bucket_name, 
        key,
        ExtraArgs={"ContentType": "image/jpeg"},  # by default boto3 uploads raw bytes.  S3 marks the file type as a generic stream binary, if a user tried to load image url in a web browser it would try to download it to the users computer instead of displaying it. "image/jpeg" ensures that browsers render the profile pictures by explicitly telling aws
    )


def _delete_from_s3(key: str) -> None:
    s3 = _get_s3_client()   
    s3.delete_object(Bucket=settings.s3_bucket_name, Key=key) # tells aws exactly which bucket to open and filepath key to delete



# Async S3 wrappers 
async def upload_profile_image(file_bytes: bytes, filename: str) -> None:  # these are needed as boto3 functions are sync . so we use runin threadppol to offload it
    key = f"profile_pics/{filename}"  # key is a official aws path string . 
    await run_in_threadpool(_upload_to_s3, file_bytes, key) # takes the uuid filename and joins 


async def delete_profile_image(filename: str | None) -> None: 
    if filename is None: 
        return         # checks if the user has no profile pics and retuns 
    key = f"profile_pics/{filename}"
    await run_in_threadpool(_delete_from_s3, key)    
