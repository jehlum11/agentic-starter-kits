from os import getenv
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from register_tools import register_tools_from_config

load_dotenv()

# Host from env so FastMCP doesn't auto-enable localhost-only DNS rebinding (which rejects Route host).
_host = getenv("HOST", "0.0.0.0")
# Disable DNS rebinding check so any Host (e.g. OpenShift Route) is accepted.
_transport_security = TransportSecuritySettings(enable_dns_rebinding_protection=False)

# Create an MCP server
mcp = FastMCP(
    "MCP AutoML Server",
    log_level="DEBUG",
    host=_host,
    transport_security=_transport_security,
)


# Simple example tools
@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b


@mcp.tool()
def sub(a: int, b: int) -> int:
    """Subtract two numbers"""
    return a - b


# Register tools from YAML config (name, description, schema_path → Pydantic model + MCP tool)
config_path = Path(__file__).parent / "tools_config.yaml"
register_tools_from_config(mcp, config_path)


if __name__ == "__main__":
    import uvicorn

    app = None
    for attr in ("sse_app", "get_sse_app"):
        fn = getattr(mcp, attr, None)
        if callable(fn):
            app = fn()
            break
    port = int(getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, forwarded_allow_ips="*")
