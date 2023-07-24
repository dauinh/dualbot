from typing import Annotated

from fastapi import FastAPI, Form
from fastapi_login import LoginManager

from fastapi import Depends
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_login.exceptions import InvalidCredentialsException
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    FileResponse,
    PlainTextResponse,
)

SECRET = 'your-secret-key'

app = FastAPI()
manager = LoginManager(SECRET, token_url='/auth/token')

fake_db = {'johndoe@e.mail': {'password': 'hunter2'}}

@manager.user_loader()
def load_user(email: str):  # could also be an asynchronous function
    user = fake_db.get(email)
    return user


@app.get("/")
def home():
    user = load_user('johndoe@e.mail')
    return JSONResponse(content=user)


# the python-multipart package is required to use the OAuth2PasswordRequestForm
@app.post('/auth/token')
def login(data: OAuth2PasswordRequestForm = Depends()):
    print(data)
    email = fake_db.get(data.username)
    password = data.password

    user = load_user(email)  # we are using the same function to retrieve the user
    if not user:
        raise InvalidCredentialsException  # you can also use your own HTTPException
    elif password != user['password']:
        raise InvalidCredentialsException
    
    access_token = manager.create_access_token(
        data=dict(sub=email)
    )
    return {'access_token': access_token, 'token_type': 'bearer'}


@app.get("/user")
async def helloworld(user=Depends(manager)):
    """Get all the members of a project."""
    return JSONResponse(content=user)