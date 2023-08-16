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
import base64
import json
from dotenv import load_dotenv

load_dotenv()

REDIRECT_URL = os.environ.get("REDIRECT_URL")
OIDC_CLIENT_ID = os.environ.get("OIDC_CLIENT_ID")
OIDC_CLIENT_SECRET = os.environ.get("OIDC_CLIENT_SECRET")
LOGIN_URL = os.environ.get("LOGIN_URL")

PRESSINGLY_CREDIT_TOKEN_URL = os.environ.get("PRESSINGLY_CREDIT_TOKEN_URL")
PRESSINGLY_ORG_ID = os.environ.get("PRESSINGLY_ORG_ID")
PRESSINGLY_RETURN_URL = os.environ.get("PRESSINGLY_RETURN_URL")
PRESSINGLY_CANCEL_URL = os.environ.get("PRESSINGLY_CANCEL_URL")

credit_token_payload = json.dumps({
    "organization_id": PRESSINGLY_ORG_ID,
    "return_url": PRESSINGLY_RETURN_URL,
    "cancel_url": PRESSINGLY_CANCEL_URL,
})

encrypted_params = base64.b64encode(credit_token_payload.encode('utf-8')).decode('utf-8')

credit_token_issue_url = PRESSINGLY_CREDIT_TOKEN_URL + \
    "?encrypted_params=" + encrypted_params \
    + "&organization_id=" + PRESSINGLY_ORG_ID

print("credit_token_issue_url", credit_token_issue_url)


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

    chainlit_session_id = request.cookies.get("chainlit-session", str(uuid.uuid4()))
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
    payload = {
        "grant_type": "authorization_code",
        "client_id": OIDC_CLIENT_ID,
        "client_secret": OIDC_CLIENT_SECRET,
        "redirect_uri": REDIRECT_URL,
        "code": auth_code,
    }
    
    # Send POST request to Pressingly Auth server
    response = requests.post(url, json=payload)
    response = response.json()
    # print(response)

    # Receives access token
    access_token = "Bearer " + response["access_token"]

    # Request user info
    userinfo_url = "https://pressingly-account.onrender.com/oauth/userinfo"
    headers = {"Authorization": access_token}
    user_info_response = requests.get(userinfo_url, headers=headers)
    auth_email = user_info_response.json()["email"]

    response = RedirectResponse("/")
    response.set_cookie(key="auth_email", value=auth_email)
    return response


# Example link: https://dualbot-image-7tzprwbq4a-df.a.run.app/credit_token?encrypted_credit_token=103ef4a520d6cb4be7a3547924f4f2daf9c79166fee9c185820597c57ab5747db45cc243ae87023bacc1155cd230829cc3893f58c9650bb8a28a27878eacf885
@app.get("/credit_token")
async def credit_token(request: Request):
    chainlit_session_id = request.cookies.get("chainlit-session")
    credit_token = request.query_params.get("encrypted_credit_token")
    user_sessions[chainlit_session_id]["credit_token"] = credit_token

    print("Success to get credit: ", credit_token)
    print("user_sessions", user_sessions[chainlit_session_id])

    return RedirectResponse("/")


chainlit_routes.append(wildcard_route)


import chainlit as cl
from chainlit.input_widget import Select

from datetime import datetime
from setup import search_agent
from utils import create_pdf_agent, process_response
from exceptions import *


# charge("af72ec69e8743f53d96a202f2a453048d715a58aad2d12dc4df71ec6a8613c3afbc7456ee366c0bf046b91c1f5b388c231e0b97ba560a26b175a8a354f414aee", 0.1, "USD")
def charge_credit_token(credit_token, amount, currency):
    """Send transaction to Pressingly Server"""
    print("Charge: $", amount)

    charge_url = "https://pressingly-account.onrender.com/credit_tokens/charge"

    data = {
        'credit_token': credit_token,
        'amount': amount,
        'currency': currency
    }

    response = requests.post(charge_url, data=data)
    transaction = response.json()
    print("transaction", transaction)

    return True


@cl.on_chat_start
async def start():
    # charge_credit_token("af72ec69e8743f53d96a202f2a453048d715a58aad2d12dc4df71ec6a8613c3afbc7456ee366c0bf046b91c1f5b388c231e0b97ba560a26b175a8a354f414aee", 0.1, "USD")
    try:
        charge_credit_token(cl.user_session.get("credit_token"), 0.1, "USD")
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
