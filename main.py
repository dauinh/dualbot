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
        "total_cost": 0,
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
@app.get("/charge")
async def charge(request: Request):
    """Send transaction to Pressingly Server

    1. send user info to Pressingly
    2. receives credit token -> save to user session
    """
    chainlit_session_id = request.cookies.get("chainlit-session")
    total_cost = user_sessions[chainlit_session_id]["total_cost"]
    print("send to Pressingly: $", total_cost)
    return


chainlit_routes.append(wildcard_route)


import chainlit as cl

from setup import search_agent
from utils import create_pdf_agent, process_response
from exceptions import *


@cl.on_chat_start
async def start():
    try:
        ### SIGN IN
        email = cl.user_session.get("auth_email")
        if not email:
            raise AuthenticationError
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
                name="package_word",
                value="False",
                label="Word usage - $0.002/word",
                description="Include words from questions and answers",
            ),
            cl.Action(
                name="package_min",
                value="False",
                label="15 mins - $0.10",
                description="Auto expire after 15 mins",
            ),
        ]

        await cl.Message(
            content="**Please choose the package that’s right for you**",
            actions=actions,
        ).send()


def charge(credit_token, amount, currency):
    """Send to Pressingly Payment"""
    pass


def issue_credit_token(org_id, return_url, cancel_url):
    """
    Successful payment --> return_url (current implementation)
    Unsuccessful payment --> cancel_url (coming soon)

    return_url -- session/user ID
    """
    pass


# NOTE: implement paywall for each invalid credit token
# User clicks on paywall --> redirect to Pressingly to issue credit token
# --> save credit token to user session
# On each message, check for credit token, if not show paywall
@cl.on_message
async def main(message: str):
    try:
        pdf_mode = cl.user_session.get("pdf_mode")

        # Embedding model: $0.0001 / 1K tokens
        total_cost = cl.user_session.get("total_cost")

        # Input $0.0015 / 1K tokens
        mess_len = len(message)

        # $0.002 / 1K tokens
        if pdf_mode:
            pdf_agent = cl.user_session.get("pdf_agent")
            res = await pdf_agent.acall(
                message, callbacks=[cl.AsyncLangchainCallbackHandler()]
            )
            mess_len += len(res["answer"].split(" "))
        else:
            search_agent = cl.user_session.get("search_agent")
            res = await cl.make_async(search_agent)(
                message, callbacks=[cl.LangchainCallbackHandler()]
            )
            mess_len += len(res["output"].split(" "))

        # Calculate usage
        mess_cost = 0.002 * (mess_len / 1000)
        total_cost += mess_cost
        cl.user_session.set("total_cost", total_cost)
        print("each message", mess_len, mess_cost)
        print("total cost", total_cost)
        # amount = mess_cost

        # Pressing Payment API
        # charge(credit_token, amount, currency)

        # User reaches limit of subscription package
        if total_cost > 0.6:
            cl.user_session.set("pdf_agent", None)
            cl.user_session.set("search_agent", None)

        # Do any post processing here
        await process_response(res, total_cost, mess_len)
    except AttributeError:
        await cl.Message(
            content="You have run out of credits for current session \
                    \nOpen new chat for another session"
        ).send()
    except TypeError:
        await start()


"""Handle buttons
"""


@cl.action_callback("pdf_mode")
async def on_action(action):
    # On button click, change to PDF reader mode
    await cl.Message(content="Entering PDF reader mode...").send()

    # Save user mode choice to session
    cl.user_session.set("pdf_mode", True)
    await action.remove()

    pdf_agent, tokens = await create_pdf_agent()
    cl.user_session.set("pdf_agent", pdf_agent)


@cl.action_callback("package_min")
async def on_action(action):
    await cl.Message(content="15-min package selected!").send()
    cl.user_session.set("package", "min")
    await start()


@cl.action_callback("package_word")
async def on_action(action):
    await cl.Message(content="Word usage package selected!").send()
    cl.user_session.set("package", "word")
    cl.user_session.set("total_cost", 0.5)
    await start()
