# fibo-mcp

Give your financial agent access to the Financial Industry Business Ontology (FIBO)

## What is FIBO?

[FIBO](https://spec.edmcouncil.org/fibo/) is the industry-standard financial ontology covering currencies, securities, derivatives, markets, legal entities, and business concepts.

<img src="assets/fibo_graph.png" alt="FIBO Graph Visualization" width="500">

## Installation

### Claude Code

Just paste this URL into Claude Code and ask it to install:

```
https://github.com/NeuroFusionAI/fibo-mcp
```

Claude will clone the repo, run `uv sync`, and add the MCP server. **Restart Claude Code to activate.**

### Manual Installation

```bash
git clone https://github.com/NeuroFusionAI/fibo-mcp.git
cd fibo-mcp
uv sync
claude mcp add fibo-mcp -s user -- uv run --directory $(pwd) main.py
# Restart Claude Code to activate
```

### Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "fibo-mcp": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/fibo-mcp", "main.py"]
    }
  }
}
```

Restart Claude Desktop to activate.

## Examples

### "What is money?"

<table width="100%">
<tr>
<th width="50%">Claude Code</th>
<th width="50%">Claude Code + fibo-mcp</th>
</tr>
<tr>
<td valign="top">

Money is a medium of exchange, a store of value, and a unit of account that facilitates economic transactions.

**Forms of Money:**
- Commodity money - Physical items with intrinsic value (gold, silver)
- Fiat money - Government-issued currency not backed by commodity (USD, EUR)
- Digital/Electronic money - Bank deposits, digital payments
- Cryptocurrencies - Decentralized digital assets like Bitcoin

Money's value ultimately rests on collective trust and acceptance.

</td>
<td valign="top">

According to FIBO:

**Currency**: *"medium of exchange value, defined by reference to the geographical location of the monetary authorities responsible for it"*

FIBO distinguishes:
- **Currency** - the medium of exchange itself
- **Monetary Amount** - a quantity denominated in a currency
- **Currency Identifier** - ISO 4217 codes (USD, EUR, etc.)

Location: `fibo:FND/Accounting/CurrencyAmount/Currency`

</td>
</tr>
</table>

### "What is a country?"

<table width="100%">
<tr>
<th width="50%">Claude Code</th>
<th width="50%">Claude Code + fibo-mcp</th>
</tr>
<tr>
<td valign="top">

A country is a distinct political entity with:
- Defined territory
- Permanent population
- Sovereign government
- Capacity to enter relations with other states

The terms "country," "nation," "state," and "nation-state" are often used interchangeably but have subtle differences.

</td>
<td valign="top">

According to FIBO:

**Sovereign State**: *"non-physical juridical entity that is represented by one centralized government that has sovereignty over a geographic area"*

Key: A country is a **legal entity** (juridical person), not just a geographic area.

Hierarchy: `SovereignState` → `Polity` → `LegalEntity`

Location: `fibo:BE/GovernmentEntities/GovernmentEntities/SovereignState`

</td>
</tr>
</table>

**Why this matters:** Financial institutions need precise definitions for regulatory compliance, cross-border transactions, sanctions screening, and legal entity identification (LEI). FIBO provides the industry-standard terminology.

## Remote Access with ngrok

```bash
# 1. Start FIBO MCP server
uv run main.py --http --port 8000

# 2. In another terminal, expose via ngrok
ngrok http 8000

# 3. Use the ngrok URL (e.g., https://abc123.ngrok.io)
```

### OpenAI API Integration

```python
from openai import OpenAI

client = OpenAI()

# Configure FIBO MCP as a tool
resp = client.responses.create(
    model="gpt-5",
    tools=[
        {
            "type": "mcp",
            "server_label": "fibo",
            "server_url": "https://your-ngrok-url.ngrok.io/mcp",  # Your ngrok URL
            "require_approval": "never",
        },
    ],
    input="What is a corporate according to FIBO?",
)
```

## Technical Details

- **Data**: 129,990 triples from FIBO ontology (299 RDF/OWL files)
- **Coverage**: 3,371 classes, 16,057 labeled entities, 1,259 properties
- **Cache**: Turtle format at `./data/fibo.ttl` (auto-downloaded on first run)
- **Updates**: `uv run main.py --force-download` to get latest FIBO
