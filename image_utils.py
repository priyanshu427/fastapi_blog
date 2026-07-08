import uuid
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

PROFILE_PICS_DIR = Path("media/profile_pics")

def process_profile_image(content: bytes) -> str:  # for image processing across different parameters
    with Image.open(BytesIO(content)) as original:
        img = ImageOps.exif_transpose(original)

        img = ImageOps.fit(img, (300, 300), method=Image.Resampling.LANCZOS)

        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")

        filename = f"{uuid.uuid4().hex}.jpg" # file name generator to prevent collisions
        filepath = PROFILE_PICS_DIR / filename

        PROFILE_PICS_DIR.mkdir(parents=True, exist_ok=True)

        img.save(filepath, "JPEG", quality=85, optimize=True)  # saves image in the hard drive from ram to the given filepath

    return filename  # storing the filename in db

def delete_profile_image(filename: str | None) -> None: # for deleting a image when user updates or deletes acc
    if filename is None:
        return

    filepath = PROFILE_PICS_DIR / filename
    if filepath.exists():
        filepath.unlink()