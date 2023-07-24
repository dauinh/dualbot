from chainlit.server import app
import mimetypes

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")

import os
import webbrowser
from pathlib import Path


from contextlib import asynccontextmanager
from watchfiles import awatch

from fastapi import FastAPI, Request
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    FileResponse,
    PlainTextResponse,
)
from fastapi_socketio import SocketManager
from starlette.middleware.cors import CORSMiddleware
import asyncio

from chainlit.config import config, load_module, reload_config, DEFAULT_HOST
from chainlit.client.utils import (
    get_auth_client_from_request,
    get_db_client_from_request,
)
from chainlit.markdown import get_markdown_str
from chainlit.telemetry import trace_event
from chainlit.logger import logger
from chainlit.types import (
    CompletionRequest,
    UpdateFeedbackRequest,
    GetConversationsRequest,
    DeleteConversationRequest,
)

@app.get("/oidc_oauth")
async def oidc_oauth(request: Request):
    return JSONResponse(content={request})

chainlit = app.router.routes
hello_route = chainlit[-1]
chainlit.insert(-2, hello_route)
chainlit.pop()

import chainlit as cl

from setup import search_agent
from utils import create_pdf_agent, process_response


# The search tool has no async implementation, we fall back to sync
# Agent is loaded before rendering
@cl.langchain_factory(use_async=False)
def factory():
    return search_agent


@cl.on_chat_start
async def start():
    # Always default to search mode
    cl.user_session.set("pdf_mode", False)

    # Sending an action button within a chatbot message
    actions = [
        cl.Action(
            name="pdf_mode", value="False", label="PDF reader", description="Click me!"
        )
    ]

    await cl.Message(
        content="Press this button to switch to chat mode with PDF reader. Open a new chat to reset mode.\nOtherwise, continue to chat for search mode.",
        actions=actions,
    ).send()


@cl.action_callback("pdf_mode")
async def on_action(action):
    # On button click, change to PDF reader mode
    await cl.Message(content="Entering PDF reader mode...").send()

    # Save user mode choice to session
    cl.user_session.set("pdf_mode", True)

    # Save PDF reader agent to session
    agent = await create_pdf_agent()
    cl.user_session.set("pdf_agent", agent)
    await action.remove()


@cl.langchain_run
async def run(agent, input):
    pdf_mode = cl.user_session.get("pdf_mode")

    if pdf_mode:
        # PDF reader mode
        agent = cl.user_session.get("pdf_agent")
        res = await agent.acall(input, callbacks=[cl.AsyncLangchainCallbackHandler()])
        await process_response(res)
        return

    # Search mode
    res = await cl.make_async(agent)(input, callbacks=[cl.LangchainCallbackHandler()])
    await cl.Message(content=res["output"]).send()
