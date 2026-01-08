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

## Example Result

<table width="100%">
<thead>
<tr>
<th width="50%">Claude Code</th>
<th width="50%">Claude Code + fibo-mcp </th>
</tr>
</thead>
<tbody>
<tr>
<td width="50%" valign="top">

> **"What is a country?"**

A country is a distinct political entity with several key characteristics:

Core Elements:
- Defined territory - A geographical area with recognized borders
- Permanent population - People who reside within those borders
- Sovereign government - An independent authority that exercises control over the territory and population
- Capacity to enter relations with other states - The ability to engage in diplomatic and international relations

Additional aspects:
- Countries typically have their own legal system, currency, and institutions
- They may be recognized by other countries and international organizations (like the UN)
- They exercise sovereignty - the supreme authority within their territory

Note: The terms "country," "nation," "state," and "nation-state" are often used interchangeably but have subtle differences:
  - Country - A general term for a geographical-political entity
  - State - Emphasizes the political and governmental structure
  - Nation - Refers to a group of people sharing common culture, language, or history
  - Nation-state - When a nation and state align (one dominant cultural group in one political entity)
</td>
<td width="50%" valign="top">

> **"What is a country?"**

According to FIBO, a country is represented as a
**Sovereign State**, which is defined as:

A non-physical **juridical entity** that is represented by one **centralized government** that has **sovereignty** over a geographic area.

The ontology provides additional clarification in an explanatory note:

A legal entity that is represented by one **centralized government**, has a **permanent population**, **defined territory**, and the **capacity to enter into relations with other sovereign states**.

Key Characteristics:

Legal entity status — It's a **juridical/legal person**

Centralized government — Represented by one central governing authority

Sovereignty — Has sovereign power over a defined area

Geographic territory — Has defined territorial boundaries

Permanent population — Has a stable population

International capacity — Can enter into relations with other sovereign states

In the FIBO ontology hierarchy, a **Sovereign State** is a specialized type of **Polity**, which is broadly defined as a legal person representing entities such as states, municipalities, or other civil authorities.

The concept is located in:
BE/GovernmentEntities/GovernmentEntities/SovereignState
</td>
</tr>
</tbody>
</table>

**Why this matters:** Financial institutions need precise jurisdiction classification for regulatory compliance, cross-border transactions, sanctions screening, and legal entity identification (LEI). FIBO's structured definitions ensure consistent interpretation across systems and jurisdictions.

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
