from chainlit.server import app, get_html_template
import mimetypes

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")

from fastapi import Request
from fastapi.responses import (
    HTMLResponse,
    RedirectResponse,
)

import webbrowser
import requests
import jwt
import chainlit as cl
from chainlit.user_session import user_sessions
import uuid

REDIRECT_URL = "https://067e-1-52-67-163.ngrok-free.app/helloworld"
OIDC_CLIENT_ID = "BQtrzwLnZ-TxmH4RvENaF8jkGUln14CdZJrl729kE_U"
OIDC_CLIENT_SECRET = "2DgU7u1YGIGy5IuP_dbkO2DroPWe3y9hvdMB92SAih8"
login="https://pressingly-account.onrender.com/oauth/authorize?client_id=BQtrzwLnZ-TxmH4RvENaF8jkGUln14CdZJrl729kE_U&redirect_uri=https%3A%2F%2F067e-1-52-67-163.ngrok-free.app%2Fhelloworld&response_type=code&scope=openid+email"

chainlit_route = app.router.routes


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

@app.get("/helloworld")
async def helloworld(request: Request):
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
    public_key = "v5Ins_85RHfOXvMMJ1Peqdjyv-o98CmONMhAtoV0ctI"
    print("query params", myobj)
    x = requests.post(url, json = myobj)
    response = x.json()
    print(x.json())
    id_token = response['id_token']
    access_token = 'Bearer ' + response['access_token']
    # print(access_token)
    userinfo_url = "https://pressingly-account.onrender.com/oauth/userinfo"
    headers = {'Authorization': access_token}
    y = requests.get(userinfo_url, headers=headers)
    auth_email = y.json()['email']
    header, payload, signature = id_token.split('.')
    decoded_payload = jwt.utils.base64url_decode(payload)
    decoded_payload = decoded_payload.decode('utf8').replace("'", '"')

    response = RedirectResponse("/")
    # response = JSONResponse(content={"hello": response, "payload": decoded_payload, "userinfo": y.json()})
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
    webbrowser.open(login)


@cl.action_callback("pdf_mode")
async def on_action(action):
    # On button click, change to PDF reader mode
    await cl.Message(content="Entering PDF reader mode...").send()

    # Save user mode choice to session
    cl.user_session.set("pdf_mode", True)
    await action.remove()

    pdf_agent = await create_pdf_agent()
    cl.user_session.set("pdf_agent", pdf_agent)
