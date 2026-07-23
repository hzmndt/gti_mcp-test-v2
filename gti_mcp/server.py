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
import ipaddress
import urllib.request
import json
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, Response
from starlette.routing import Route, Mount
from starlette.requests import Request
from mcp.server.sse import SseServerTransport
from mcp.server.fastmcp import FastMCP, Context
from mcp.server.transport_security import TransportSecuritySettings

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
    stateless_http=stateless,
    host="0.0.0.0",
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))

# Load tools.
from gti_mcp.tools import *

# --- SSE and Auth Implementation ---

class IPWhitelistMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, allowed_ips: list[str], whitelist_google: bool = True):
        super().__init__(app)
        self.allowed_networks = []
        for ip in allowed_ips:
            try:
                self.allowed_networks.append(ipaddress.ip_network(ip.strip()))
            except ValueError:
                pass
        
        self.google_networks = []
        if whitelist_google:
            try:
                # Fetch Google public IP ranges
                for url in ['https://www.gstatic.com/ipranges/goog.json', 'https://www.gstatic.com/ipranges/cloud.json']:
                    with urllib.request.urlopen(url, timeout=5) as response:
                        data = json.loads(response.read().decode())
                        for prefix in data.get('prefixes', []):
                            if 'ipv4Prefix' in prefix:
                                self.google_networks.append(ipaddress.ip_network(prefix['ipv4Prefix']))
                            elif 'ipv6Prefix' in prefix:
                                self.google_networks.append(ipaddress.ip_network(prefix['ipv6Prefix']))
            except Exception as e:
                print(f"Warning: Failed to fetch Google IP ranges: {e}")

    async def dispatch(self, request: Request, call_next):
        x_forwarded_for = request.headers.get("x-forwarded-for")
        if x_forwarded_for:
            client_ip_str = x_forwarded_for.split(",")[0].strip()
        else:
            client_ip_str = request.client.host
            
        try:
            client_ip = ipaddress.ip_address(client_ip_str)
        except ValueError:
            return JSONResponse({"error": "Forbidden - Invalid client IP"}, status_code=403)

        # Check explicit whitelist
        for network in self.allowed_networks:
            if client_ip in network:
                return await call_next(request)

        # Check Google public ranges
        for network in self.google_networks:
            if client_ip in network:
                return await call_next(request)

        return JSONResponse({"error": f"Forbidden - Client IP {client_ip_str} not authorized"}, status_code=403)

# Create Starlette App using FastMCP streamable http app
app = server.streamable_http_app()

# Configure allowed IPs
allowed_ips_env = os.getenv("ALLOWED_IPS", "")
if ";" in allowed_ips_env:
    allowed_ips = [ip for ip in allowed_ips_env.split(";") if ip.strip()]
else:
    allowed_ips = [ip for ip in allowed_ips_env.split(",") if ip.strip()]
# Always allow localhost
allowed_ips.extend(["127.0.0.1", "::1"])

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.add_middleware(IPWhitelistMiddleware, allowed_ips=allowed_ips, whitelist_google=True)

# Run the server (Local stdio support kept for back-compat/debugging)
def main():
  server.run(transport='stdio')


if __name__ == '__main__':
  main()
