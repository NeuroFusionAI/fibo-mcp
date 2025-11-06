# fibo-mcp

Give your financial agent access to the Financial Industry Business Ontology (FIBO)

## What is FIBO?

[FIBO](https://spec.edmcouncil.org/fibo/) is the industry-standard financial ontology covering currencies, securities, derivatives, markets, legal entities, and business concepts.

<img src="assets/fibo_graph.png" alt="FIBO Graph Visualization" width="400">

## Quick Start

```bash
# Install dependencies
uv sync

# Connect to Claude Desktop
claude mcp add --transport stdio fibo-mcp uv run /path/to/fibo-mcp/main.py
```

## Example Result

| Claude Code | Claude Code + fibo-mcp |
|------------|------------------------|
| > **"What is a country?"**<br><br>A country is a distinct political entity with several key characteristics:<br><br>**Core Elements:**<br>• Defined territory - A geographical area with recognized borders<br>• Permanent population - People who reside within those borders<br>• Sovereign government - An independent authority that exercises control over the territory and population<br>• Capacity to enter relations with other states - The ability to engage in diplomatic and international relations<br><br>**Additional aspects:**<br>• Countries typically have their own legal system, currency, and institutions<br>• They may be recognized by other countries and international organizations (like the UN)<br>• They exercise sovereignty - the supreme authority within their territory<br><br>**Note:** The terms "country," "nation," "state," and "nation-state" are often used interchangeably but have subtle differences:<br>• Country - A general term for a geographical-political entity<br>• State - Emphasizes the political and governmental structure<br>• Nation - Refers to a group of people sharing common culture, language, or history<br>• Nation-state - When a nation and state align (one dominant cultural group in one political entity) | > **"What is a country according to FIBO?"**<br><br>According to FIBO, a country is represented as a Sovereign State, which is defined as:<br><br>*A non-physical juridical entity that is represented by one centralized government that has sovereignty over a geographic area*<br><br>The ontology provides additional clarification in an explanatory note:<br><br>*A legal entity that is represented by one centralized government, has a permanent population, defined territory, and the capacity to enter into relations with other sovereign states.*<br><br>**Key Characteristics:**<br><br>1. Legal entity status - It's a juridical/legal person<br>2. Centralized government - Represented by one central governing authority<br>3. Sovereignty - Has sovereign power over a defined area<br>4. Geographic territory - Has defined territorial boundaries<br>5. Permanent population - Has a stable population<br>6. International capacity - Can enter into relations with other sovereign states<br><br>In the FIBO ontology hierarchy, a Sovereign State is a specialized type of Polity, which is broadly defined as a legal person representing entities such as states, municipalities, or other civil authorities.<br><br>The concept is located in: BE/GovernmentEntities/GovernmentEntities/SovereignState |

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
- **Cache**: Turtle format at `./data/fibo.db` (auto-downloaded on first run)
- **Updates**: `uv run main.py --force-download` to get latest FIBO