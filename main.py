from chainlit.server import app, get_html_template
import mimetypes

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")

from fastapi import Request
from fastapi.responses import (
    HTMLResponse,
    RedirectResponse,
)

import os
import webbrowser
import requests
import chainlit as cl
from chainlit.user_session import user_sessions
import uuid

from dotenv import load_dotenv

load_dotenv()

REDIRECT_URL = os.environ["REDIRECT_URL"]
OIDC_CLIENT_ID = os.environ["OIDC_CLIENT_ID"]
OIDC_CLIENT_SECRET = os.environ["OIDC_CLIENT_SECRET"]
LOGIN_URL = os.environ["LOGIN_URL"]


@app.get("/")
async def serve(request: Request):
    html_template = get_html_template()
    """Serve the UI files."""

    response = HTMLResponse(content=html_template, status_code=200)
    auth_email = request.cookies.get('auth_email')
    print("auth_email", auth_email)

    chainlit_session_id = str(uuid.uuid4())
    response.set_cookie(
        key="chainlit-session", value=chainlit_session_id, httponly=True
    )
    user_sessions[chainlit_session_id] = {"auth_email": auth_email}
    return response


@app.get("/auth")
async def auth(request: Request):
    # print(request._query_params)
    auth_code = request._query_params['code']
    url = 'https://pressingly-account.onrender.com/oauth/token'
    myobj = {
        'grant_type': "authorization_code",
        'client_id': OIDC_CLIENT_ID,
        'client_secret': OIDC_CLIENT_SECRET,
        'redirect_uri': REDIRECT_URL,
        'code': auth_code
    }
    response = requests.post(url, json = myobj).json()
    access_token = 'Bearer ' + response['access_token']
    headers = {'Authorization': access_token}

    userinfo_url = "https://pressingly-account.onrender.com/oauth/userinfo"
    y = requests.get(userinfo_url, headers=headers).json()
    auth_email = y['email']

    response = RedirectResponse("/")
    response.set_cookie(key="auth_email", value=auth_email)
    return response


chainlit_route = app.router.routes
root_route = chainlit_route[-1]
chainlit_route.insert(-4, root_route)
chainlit_route.pop()

hello_route = chainlit_route[-1]
chainlit_route.insert(-4, hello_route)
chainlit_route.pop()

# for route in app.router.routes:
#     print(route)


from setup import search_agent
from utils import create_pdf_agent, process_response


@cl.on_chat_start
async def start():
    # Always default to search mode
    cl.user_session.set("pdf_mode", False)

    # Sending an action button within a chatbot message
    actions = [
        cl.Action(
            name="pdf_mode", value="False", label="PDF reader", description="Click me!"
        ),
        cl.Action(
            name="login", value="False", label="Login", description="Click me!"
        )
    ]
    cl.user_session.set("search_agent", search_agent)

    email = cl.user_session.get('auth_email')
    if not email:
        email = 'Stranger!'
    # print("auth_email", email)
    await cl.Message(
        content=f"Hello {email}"+"\nPress this button to switch to chat mode with PDF reader. Open a new chat to reset mode.\nOtherwise, continue to chat for search mode.",
        actions=actions,
    ).send()


@cl.on_message
async def main(message: str):
    # Retrieve the chain from the user session
    search_agent = cl.user_session.get("search_agent")
    pdf_agent = cl.user_session.get("pdf_agent")

    pdf_mode = cl.user_session.get("pdf_mode")

    if pdf_mode:
        res = await pdf_agent.acall(message, callbacks=[cl.AsyncLangchainCallbackHandler()])
    else:
        res = await cl.make_async(search_agent)(message, callbacks=[cl.LangchainCallbackHandler()])

    # Do any post processing here
    await process_response(res)


@cl.action_callback("login")
async def on_action(action):
    webbrowser.open(LOGIN_URL)


@cl.action_callback("pdf_mode")
async def on_action(action):
    # On button click, change to PDF reader mode
    await cl.Message(content="Entering PDF reader mode...").send()

    # Save user mode choice to session
    cl.user_session.set("pdf_mode", True)
    await action.remove()

    pdf_agent = await create_pdf_agent()
    cl.user_session.set("pdf_agent", pdf_agent)
