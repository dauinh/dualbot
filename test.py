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

@app.post("/helloworld")
async def helloworld(request: Request):
    """Get all the members of a project."""
    return JSONResponse(content={"members": "HELLO WORLD"})

chainlit = app.router.routes
hello_route = chainlit[-1]
chainlit.insert(-2, hello_route)
# chainlit.insert(-2, chainlit[-1])
for route in app.router.routes:
#     if route.name == "serve":
#         print()
#         print('serve')
#         print()
    print(route)

import chainlit as cl

@cl.on_message  # this function will be called every time a user inputs a message in the UI
async def main(message: str):
    # this is an intermediate step
    await cl.Message(author="Tool 1", content=f"Response from tool1", indent=1).send()

    # send back the final answer
    await cl.Message(content=f"This is the final answer").send()