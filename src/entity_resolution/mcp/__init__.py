"""
Entity Resolution MCP Server

Exposes entity resolution operations as MCP tools and resources so that
any MCP-compatible AI agent (Claude, Gemini, GPT-4, Cursor …) can perform
entity resolution directly through natural language.

Usage (stdio — works with Claude Desktop / Cursor):
    arango-er-mcp

Usage (SSE — for remote / HTTP clients):
    arango-er-mcp --transport sse --port 8080
"""
