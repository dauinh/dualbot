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
import requests
from chainlit.user_session import user_sessions
import uuid
from dotenv import load_dotenv

load_dotenv()

REDIRECT_URL = os.environ.get("REDIRECT_URL")
OIDC_CLIENT_ID = os.environ.get("OIDC_CLIENT_ID")
OIDC_CLIENT_SECRET = os.environ.get("OIDC_CLIENT_SECRET")
LOGIN_URL = os.environ.get("LOGIN_URL")

chainlit_routes = app.router.routes
wildcard_route = chainlit_routes.pop()


@app.get("/")
async def serve(request: Request):
    """Serve the UI files."""
    html_template = get_html_template()

    response = HTMLResponse(content=html_template, status_code=200)
    auth_email = request.cookies.get("auth_email")
    print("auth_email", auth_email)

    chainlit_session_id = str(uuid.uuid4())
    response.set_cookie(
        key="chainlit-session", value=chainlit_session_id, httponly=True
    )
    user_sessions[chainlit_session_id] = {
        "auth_email": auth_email,
        "total_tokens": 10**4,
    }
    return response


@app.get("/helloworld")
async def helloworld(request: Request):
    # print(request._query_params)
    auth_code = request._query_params["code"]
    url = "https://pressingly-account.onrender.com/oauth/token"
    myobj = {
        "grant_type": "authorization_code",
        "client_id": OIDC_CLIENT_ID,
        "client_secret": OIDC_CLIENT_SECRET,
        "redirect_uri": REDIRECT_URL,
        "code": auth_code,
    }
    print("query params", myobj)
    x = requests.post(url, json=myobj)
    response = x.json()
    print(x.json())
    # id_token = response['id_token']
    access_token = "Bearer " + response["access_token"]
    # print(access_token)
    userinfo_url = "https://pressingly-account.onrender.com/oauth/userinfo"
    headers = {"Authorization": access_token}
    y = requests.get(userinfo_url, headers=headers)
    auth_email = y.json()["email"]

    response = RedirectResponse("/")
    response.set_cookie(key="auth_email", value=auth_email)
    return response


# NOTE: pay per session (chat window) and tokens
@app.post("/charge")
async def charge():
    """Send transaction to Pressingly Server

    1. send user info to Pressingly
    2. receives credit token -> save to user session
    """
    pass


@app.get("/testing")
async def testing(request: Request):
    chainlit_session_id = request.cookies.get("chainlit-session")
    total_tokens = user_sessions[chainlit_session_id]["total_tokens"]
    print("send to Pressingly:", total_tokens, "tokens")
    return


@app.get("/payment")
async def payment(request: Request):
    """Receives payment complete status from Pressingly Server"""
    # print(request._query_params)
    auth_code = request._query_params["code"]
    url = "https://pressingly-account.onrender.com/oauth/token"
    payload = {
        "grant_type": "authorization_code",
        "client_id": OIDC_CLIENT_ID,
        "client_secret": OIDC_CLIENT_SECRET,
        "redirect_uri": REDIRECT_URL,
        "code": auth_code,
    }
    # print("query params", payload)
    x = requests.post(url, json=payload)
    response = x.json()
    # print(x.json())

    #

    response = RedirectResponse("/")
    return response


chainlit_routes.append(wildcard_route)


import chainlit as cl

from setup import search_agent
from utils import create_pdf_agent, process_response

from pprint import pprint

import tiktoken

encoding = tiktoken.get_encoding("cl100k_base")
encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")


@cl.on_chat_start
async def start():
    # Always default to search mode
    cl.user_session.set("pdf_mode", False)

    # Sending an action button within a chatbot message
    actions = [
        cl.Action(
            name="pdf_mode", value="False", label="PDF reader", description="Click me!"
        ),
    ]
    cl.user_session.set("search_agent", search_agent)

    email = cl.user_session.get("auth_email")
    if email:
        login_msg = f"Hello {email}"
    else:
        login_msg = f"[Sign in with Pressingly]({LOGIN_URL}) \
                    \nHello New User!"

    await cl.Message(
        content=f"{login_msg} \
                    \nPress this button to switch to chat mode with PDF reader. Open a new chat to reset mode.\
                    \nOtherwise, continue to chat for search mode.",
        actions=actions,
    ).send()


@cl.on_message
async def main(message: str):
    try:
        # Retrieve the chain from the user session
        search_agent = cl.user_session.get("search_agent")
        pdf_agent = cl.user_session.get("pdf_agent")
        pdf_mode = cl.user_session.get("pdf_mode")

        # Embedding model: $0.0001 / 1K tokens
        cur_tokens = cl.user_session.get("cur_tokens")
        if not cur_tokens:
            cur_tokens = 0

        # Input $0.0015 / 1K tokens
        cur_tokens += len(encoding.encode(message))

        # $0.002 / 1K tokens
        if pdf_mode:
            res = await pdf_agent.acall(
                message, callbacks=[cl.AsyncLangchainCallbackHandler()]
            )
            cur_tokens += len(encoding.encode(res["answer"]))
        else:
            res = await cl.make_async(search_agent)(
                message, callbacks=[cl.LangchainCallbackHandler()]
            )
            cur_tokens += len(encoding.encode(res["output"]))

        # Do any post processing here
        await process_response(res)

        # Calculate token usage
        cl.user_session.set("cur_tokens", cur_tokens)
        if not cl.user_session.get("total_tokens"):
            cl.user_session.set("total_tokens", 10**4)

        total_tokens = cl.user_session.get("total_tokens")
        print("DEBUG", total_tokens, cur_tokens)
        print("after message:", cl.user_session.get("cur_tokens"), "tokens")
        total_tokens -= cur_tokens
        cl.user_session.set("total_tokens", total_tokens)
        print("remaining tokens:", total_tokens)

        # User runs out of token credits
        if total_tokens < 5000:
            cl.user_session.set("pdf_agent", None)
            cl.user_session.set("search_agent", None)
    except AttributeError:
        await cl.Message(
            content="You have run out of credits for current session \
                    \nOpen new chat for another session"
        ).send()


@cl.action_callback("pdf_mode")
async def on_action(action):
    # On button click, change to PDF reader mode
    await cl.Message(content="Entering PDF reader mode...").send()

    # Save user mode choice to session
    cl.user_session.set("pdf_mode", True)
    await action.remove()

    pdf_agent, tokens = await create_pdf_agent()
    cl.user_session.set("cur_tokens", tokens)
    cl.user_session.set("pdf_agent", pdf_agent)
