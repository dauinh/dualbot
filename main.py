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
from chainlit.input_widget import Select

from datetime import datetime
from setup import search_agent
from utils import create_pdf_agent, process_response
from exceptions import *



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
        settings = await cl.ChatSettings(
            [
                Select(
                    id="Model",
                    label="OpenAI - Model",
                    values=["gpt-3.5-turbo", "gpt-3.5-turbo-16k", "gpt-4", "gpt-4-32k"],
                    initial_index=0,
                )
            ]
        ).send()
        value = settings["Model"]
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
                label="Pay per word - $0.002/word",
                description="Include words from questions and answers",
            ),
            cl.Action(
                name="package_min",
                value="False",
                label="Pay per 15-min - $0.10",
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
        package = cl.user_session.get("package")

        # 15-min package: check time
        start = cl.user_session.get("package_start_time")
        cur = datetime.now()
        # Convert to mins
        start_min = start.hour * 60 + start.minute
        cur_min = cur.hour * 60 + cur.minute
        print('start time', start)
        print('current time', cur)
        usage_time = cur_min - start_min
        
        # Word usage package: keep word count
        total_cost = cl.user_session.get("total_cost")
        message_length = len(message)

        if pdf_mode:
            pdf_agent = cl.user_session.get("pdf_agent")
            res = await pdf_agent.acall(
                message, callbacks=[cl.AsyncLangchainCallbackHandler()]
            )
            total_cost += 0.5
            message_length += len(res["answer"].split(" "))
        else:
            search_agent = cl.user_session.get("search_agent")
            res = await cl.make_async(search_agent)(
                message, callbacks=[cl.LangchainCallbackHandler()]
            )
            message_length += len(res["output"].split(" "))

        # Calculate cost
        mess_cost = 0.002 * (message_length / 1000)
        total_cost += mess_cost
        cl.user_session.set("total_cost", total_cost)
        print("each message", message_length, mess_cost)
        print("total cost", total_cost)
        # amount = mess_cost

        # User reaches limit of subscription package
        if (package == "word" and total_cost > 0.6) or \
            (package == "min" and usage_time > 15):
            cl.user_session.set("pdf_agent", None)
            cl.user_session.set("search_agent", None)

        package_info = {
            "package": package,
            "total_cost": total_cost,
            "message_length": message_length,
            "usage_time": usage_time,
        }

        # Do any post processing here
        await process_response(res, package_info)

        # Pressing Payment API
        # charge(credit_token, amount, currency)
        
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
    cl.user_session.set("package_start_time", datetime.now())
    cl.user_session.set("total_cost", 0)
    await start()


@cl.action_callback("package_word")
async def on_action(action):
    await cl.Message(content="Word usage package selected!").send()
    cl.user_session.set("package", "word")
    cl.user_session.set("package_start_time", datetime.now())
    cl.user_session.set("total_cost", 0)
    await start()
