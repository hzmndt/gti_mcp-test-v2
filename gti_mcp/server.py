# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# Add lifespan support for startup/shutdown with strong typing
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass

import logging
import os
import vt
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, Response
from starlette.routing import Route, Mount
from starlette.requests import Request
from mcp.server.sse import SseServerTransport
from mcp.server.fastmcp import FastMCP, Context

logging.basicConfig(level=logging.ERROR)

# If True, creates a completely fresh transport for each request
# with no session tracking or state persistence between requests.
stateless = False
if os.getenv("STATELESS") == "1":
  stateless = True


def _vt_client_factory(ctx: Context, api_key: str = None) -> vt.Client:
    # Prioritize the passed argument
    if not api_key:
        api_key = os.getenv("VT_APIKEY")
    
    # Try to get from context if not in env (placeholder for future ctx inspection)
    # if not api_key and ctx and hasattr(ctx, 'init_options'):
    #     api_key = ctx.init_options.get('vtApiKey')
    
    if not api_key:
        raise ValueError("VT API Key is required. Please provide it as an argument 'api_key' or set VT_APIKEY environment variable.")
    return vt.Client(api_key)

vt_client_factory = _vt_client_factory


@asynccontextmanager
async def vt_client(ctx: Context, api_key: str = None) -> AsyncIterator[vt.Client]:
  """Provides a vt.Client instance for the current request."""
  client = vt_client_factory(ctx, api_key)

  try:
    yield client
  finally:
    await client.close_async()

# Create a named server and specify dependencies for deployment and development
server = FastMCP(
    "Google Threat Intelligence MCP server",
    dependencies=["vt-py"],
    stateless_http=stateless)

# Load tools.
from gti_mcp.tools import *

# --- SSE and Auth Implementation ---



sse = SseServerTransport("/mcp")

class ASGIResponse(Response):
    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app

    async def __call__(self, scope, receive, send):
        await self.app(scope, receive, send)

async def handle_sse(request: Request):
    # Access the underlying Server object from FastMCP
    mcp_server = getattr(server, "_mcp_server", None)
    if not mcp_server:
         raise RuntimeError("Could not find underlying MCP Server in FastMCP instance")

    async def asgi_handler(scope, receive, send):
        async with sse.connect_sse(scope, receive, send) as streams:
            await mcp_server.run(
                streams[0], streams[1], mcp_server.create_initialization_options()
            )
    return ASGIResponse(asgi_handler)
    
async def handle_mcp(request: Request):
    if request.method == "POST":
        return ASGIResponse(sse.handle_post_message)
    else:
        return await handle_sse(request)

# Create Starlette App


routes = [
    Route("/mcp", handle_mcp, methods=["GET", "POST"])
]

app = Starlette(debug=True, routes=routes)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Run the server (Local stdio support kept for back-compat/debugging)
def main():
  server.run(transport='stdio')


if __name__ == '__main__':
  main()
