import asyncio
import json

from fastmcp import Client

from main import mcp


def test_mcp_search_to_inspect_round_trip():
    async def run():
        async with Client(mcp) as client:
            tools = {tool.name for tool in await client.list_tools()}
            assert {"search", "inspect", "sparql"} <= tools
            found = await client.call_tool("search", {"term": "stock"})
            candidates = json.loads(found.content[0].text)
            share = next(row for row in candidates["results"]
                         if row["uri"] == "fibo-sec-eq-eq:Share")
            inspected = await client.call_tool("inspect", {"identifier": share["uri"]})
            record = json.loads(inspected.content[0].text)
            assert record["uri"] == share["uri"]
            assert "share" in record["label"]
            assert any(row["label"] == "equity instrument" for row in record["parents"])

    asyncio.run(run())
