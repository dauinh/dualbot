"""Test login method
curl -X 'POST' \
  'http://127.0.0.1:8000/auth/token' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'grant_type=&username=johndoe&password=secret&scope=&client_id=&client_secret='
"""
from fastapi import FastAPI, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from fastapi_login import LoginManager
from fastapi_login.exceptions import InvalidCredentialsException

SECRET = 'your-secret-key'

app = FastAPI()
manager = LoginManager(SECRET, token_url='/auth/token')
templates = Jinja2Templates(directory="templates")

fake_db = {'johndoe': {'password': 'secret'}}

@manager.user_loader()
def load_user(username: str):  # could also be an asynchronous function
    user = fake_db.get(username)
    return user


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


# the python-multipart package is required to use the OAuth2PasswordRequestForm
@app.post('/auth/token')
def login(data: OAuth2PasswordRequestForm = Depends()):
    # print(vars(data))
    username = data.username
    password = data.password

    user = load_user(username)  # we are using the same function to retrieve the user
    if not user:
        raise InvalidCredentialsException  # you can also use your own HTTPException
    elif password != user['password']:
        raise InvalidCredentialsException
    
    access_token = manager.create_access_token(
        data=dict(sub=username)
    )
    return {'access_token': access_token, 'token_type': 'bearer'}


@app.get("/user")
async def helloworld(user=Depends(manager)):
    """Get all the members of a project."""
    return JSONResponse(content=user)