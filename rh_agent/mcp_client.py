"""Connect to Robinhood's hosted Trading MCP server (streamable HTTP + OAuth).

No Robinhood password ever touches this code: first run opens a browser to
Robinhood's own authorization page; tokens are cached in ~/.rh_agent/.
"""
import asyncio
import json
import os
import threading
import webbrowser
from contextlib import asynccontextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from mcp import ClientSession
from mcp.client.auth import OAuthClientProvider, TokenStorage
from mcp.client.streamable_http import streamablehttp_client
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, OAuthToken

SERVER_URL = "https://agent.robinhood.com/mcp/trading"
CALLBACK_PORT = 8765
REDIRECT_URI = f"http://127.0.0.1:{CALLBACK_PORT}/callback"
STATE_DIR = Path.home() / ".rh_agent"


class FileTokenStorage(TokenStorage):
    def __init__(self):
        STATE_DIR.mkdir(mode=0o700, exist_ok=True)
        self.path = STATE_DIR / "oauth.json"

    def _load(self) -> dict:
        return json.loads(self.path.read_text()) if self.path.exists() else {}

    def _save(self, data: dict) -> None:
        self.path.write_text(json.dumps(data))
        os.chmod(self.path, 0o600)

    async def get_tokens(self):
        d = self._load().get("tokens")
        return OAuthToken.model_validate(d) if d else None

    async def set_tokens(self, tokens):
        d = self._load(); d["tokens"] = tokens.model_dump(mode="json"); self._save(d)

    async def get_client_info(self):
        d = self._load().get("client")
        return OAuthClientInformationFull.model_validate(d) if d else None

    async def set_client_info(self, info):
        d = self._load(); d["client"] = info.model_dump(mode="json"); self._save(d)


@asynccontextmanager
async def connect():
    loop = asyncio.get_running_loop()
    fut: asyncio.Future = loop.create_future()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            q = parse_qs(urlparse(self.path).query)
            code = q.get("code", [None])[0]
            self.send_response(200); self.end_headers()
            self.wfile.write(b"Authorized. You can close this tab.")
            if code and not fut.done():
                loop.call_soon_threadsafe(fut.set_result, (code, q.get("state", [None])[0]))

        def log_message(self, *a):
            pass

    server = HTTPServer(("127.0.0.1", CALLBACK_PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    async def redirect_handler(url: str) -> None:
        print(f"Opening browser to authorize with Robinhood...\n{url}")
        webbrowser.open(url)

    async def callback_handler():
        return await fut

    provider = OAuthClientProvider(
        server_url=SERVER_URL,
        client_metadata=OAuthClientMetadata(
            client_name="rh-agent",
            redirect_uris=[REDIRECT_URI],
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
        ),
        storage=FileTokenStorage(),
        redirect_handler=redirect_handler,
        callback_handler=callback_handler,
    )
    try:
        async with streamablehttp_client(SERVER_URL, auth=provider) as (r, w, _):
            async with ClientSession(r, w) as session:
                await session.initialize()
                yield session
    finally:
        server.shutdown()
