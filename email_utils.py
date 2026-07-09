from email.message import EmailMessage

import aiosmtplib
from fastapi.templating import Jinja2Templates

from config import settings

templates = Jinja2Templates(directory="templates")

# send_email function
async def send_email(   # we get all these input parameters from our route in auth.py
    to_email: str,
    subject: str,
    plain_text: str,
    html_content: str | None = None,
) -> None:
    message = EmailMessage()   # EmailMessage() class gives a MIME structure universal format that email systems read
    message["From"] = settings.mail_from  # we use the message[] as it indicates an email is a http payload but with very specific metadata
    message["To"] = to_email
    message["Subject"] = subject

    message.set_content(plain_text)   # If a user has a hyper-secure or old email client that blocks HTML, they will still see this readable plain text layout.

    if html_content:   # if email client supports renderng web structures then show this. when mail is sent it sends both plain text and html and see if the user has html rendering 
        message.add_alternative(html_content, subtype="html")

    await aiosmtplib.send(   # async keeps taking requests even if the email is going across the network to the mail server 
    message,                            # The payload package to deliver
    hostname=settings.mail_server,      # "sandbox.smtp.mailtrap.io"
    port=settings.mail_port,            # 587 (The secure door number)
    username=settings.mail_username,    # Mailtrap private account ID
    password=settings.mail_password.get_secret_value() or None,   # Mailtrap private credential key
    start_tls=settings.mail_use_tls,    # Tells the port to encrypt the data stream
)

# send_password_reset_email function
async def send_password_reset_email(to_email: str, username: str, token: str) -> None:
    reset_url = f"{settings.frontend_url}/reset-password?token={token}"  # building reset url using frontend url setting , specific page path (/reset-password), and appends a URL Query Parameter (?token=xyz123).

    template = templates.env.get_template("email/password_reset.html")      # we dont have a request parameter object for email cause browser is no rendering in a email window but we want it rendered . here it fetches password_reset.html file using jinja2 we load the html file in memory as a  Python object (template), completely free of any HTTP dependencies.
    html_content = template.render(reset_url=reset_url, username=username)  # jinja takes the raw html in password_reset.html and places these parameters in it.

# the fallback plain text
    plain_text = f"""Hi {username},  

You requested to reset your password. Ctokenlick the link below to set a new password:

{reset_url}

This link will expire in 1 hour.

If you didn't request this, you can safely ignore this email.

Best regards,
The FastAPI Blog Team
"""

    await send_email(  # sending all the parameters to our send email function
        to_email=to_email,
        subject="Reset Your Password - FastAPI Blog",
        plain_text=plain_text,
        html_content=html_content,
    )


