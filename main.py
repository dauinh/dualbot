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
    package = request.cookies.get("package")
    print("auth_email", auth_email)
    print("package", package)

    chainlit_session_id = str(uuid.uuid4())
    response.set_cookie(
        key="chainlit-session", value=chainlit_session_id, httponly=True
    )
    user_sessions[chainlit_session_id] = {
        "auth_email": auth_email,
        "total_tokens": 0,
        "package": package,
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
    # print("query params", myobj)
    x = requests.post(url, json=myobj)
    response = x.json()
    # print(x.json())
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
from exceptions import *

import fontstyle
import tiktoken

encoding = tiktoken.get_encoding("cl100k_base")
encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")


@cl.on_chat_start
async def start():
    try:
        ### SIGN IN
        email = cl.user_session.get("auth_email")
        # if not email:
        #     raise AuthenticationError
        await cl.Message(
            content=f"**Welcome to Cactusdemocracy!** \
                    \nHi {email}! 👋 We're excited to have you on board. Whether you're seeking insights, seeking solutions, or simply engaging in thought-provoking conversations, Cactusdemocracy is here to help you."
        ).send()

        ### PAYWALL
        package = cl.user_session.get("package")
        if not package:
            raise SubscriptionError

        ### MAIN CHAT
        # Always default to search mode
        cl.user_session.set("pdf_mode", False)

        actions = [
            cl.Action(
                name="pdf_mode",
                value="False",
                label="PDF reader",
            ),
        ]
        cl.user_session.set("search_agent", search_agent)

        await cl.Message(
            content=f"Press this button to switch to chat mode with PDF reader. Open a new chat to reset mode.\
                    \nOtherwise, continue to chat for search mode.",
            actions=actions,
        ).send()
    except AuthenticationError:
        await cl.Message(
            content=f"**Welcome to Cactusdemocracy!** \
                    \nHi there! 👋 We're excited to have you on board. Whether you're seeking insights, seeking solutions, or simply engaging in thought-provoking conversations, Cactusdemocracy is here to help you. \
                    \n[Sign in to continue]({LOGIN_URL})"
        ).send()
    except SubscriptionError:
        actions = [
            cl.Action(
                name="package_month",
                value="False",
                label="Monthly - $20",
                description="Click me!",
            ),
            cl.Action(
                name="package_day",
                value="False",
                label="1 day - $1",
                description="Click me!",
            ),
            cl.Action(
                name="package_min",
                value="False",
                label="15 mins - $0.10",
                description="Click me!",
            ),
            cl.Action(
                name="package_prompt",
                value="False",
                label="10 prompts - $0.50",
                description="Click me!",
            ),
        ]
        cl.user_session.set("search_agent", search_agent)

        await cl.Message(
            content="**Please choose the package that’s right for you**",
            actions=actions,
        ).send()


# NOTE:
# MODEL1
# After message, print amount charge + explanation + transaction ID
# ==> user exp, flexible pricing model
# MODEL2
# 15-min pass ~ $1 --> "will be charge for next 15 mins"
def charge(credit_token, amount, currency):
    """Send to Pressingly Payment"""
    pass


def issue_credit_token(org_id, return_url, cancel_url):
    """
    Successful payment --> return_url (current implementation)
    Unsuccessful payment --> cancel_url (coming soon)

    return_url - session/user ID ()
    """
    pass


# NOTE: implement paywall for each invalid credit token
# User clicks on paywall --> redirect to Pressingly to issue credit token
# --> save credit token to user session
# On each message, check for credit token, if not show paywall
@cl.on_message
async def main(message: str):
    try:
        # Retrieve the chain from the user session
        search_agent = cl.user_session.get("search_agent")
        pdf_agent = cl.user_session.get("pdf_agent")
        pdf_mode = cl.user_session.get("pdf_mode")

        # Embedding model: $0.0001 / 1K tokens
        total_tokens = cl.user_session.get("total_tokens")
        if not total_tokens:
            total_tokens = 0

        # Input $0.0015 / 1K tokens
        total_tokens += len(encoding.encode(message))

        # $0.002 / 1K tokens
        if pdf_mode:
            res = await pdf_agent.acall(
                message, callbacks=[cl.AsyncLangchainCallbackHandler()]
            )
            total_tokens += len(encoding.encode(res["answer"]))
        else:
            res = await cl.make_async(search_agent)(
                message, callbacks=[cl.LangchainCallbackHandler()]
            )
            total_tokens += len(encoding.encode(res["output"]))

        # Use Pressing Payment API
        # charge(credit_token, amount, currency)

        # Calculate token usage
        print("after message:", cl.user_session.get("total_tokens"), "tokens")
        cl.user_session.set("total_tokens", total_tokens)

        # User runs out of token credits
        if total_tokens > 10000:
            cl.user_session.set("pdf_agent", None)
            cl.user_session.set("search_agent", None)

        # Do any post processing here
        await process_response(res, total_tokens)
    except AttributeError:
        await cl.Message(
            content="You have run out of credits for current session \
                    \nOpen new chat for another session"
        ).send()
    except TypeError:
        await start()


### Handling buttons logic
@cl.action_callback("pdf_mode")
async def on_action(action):
    # On button click, change to PDF reader mode
    await cl.Message(content="Entering PDF reader mode...").send()

    # Save user mode choice to session
    cl.user_session.set("pdf_mode", True)
    await action.remove()

    pdf_agent, tokens = await create_pdf_agent()
    cl.user_session.set("total_tokens", tokens)
    cl.user_session.set("pdf_agent", pdf_agent)


@cl.action_callback("package_month")
async def on_action(action):
    await cl.Message(content="One month package selected!").send()
    cl.user_session.set("package", "month")
    await start()


@cl.action_callback("package_day")
async def on_action(action):
    await cl.Message(content="One day package selected!").send()
    cl.user_session.set("package", "day")
    await start()


@cl.action_callback("package_min")
async def on_action(action):
    await cl.Message(content="15-min package selected!").send()
    cl.user_session.set("package", "min")
    await start()


@cl.action_callback("package_prompt")
async def on_action(action):
    await cl.Message(content="10-prompt package selected!").send()
    cl.user_session.set("package", "prompt")
    await start()