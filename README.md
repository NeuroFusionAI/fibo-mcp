# fibo-mcp

Give your financial agent access to the Financial Industry Business Ontology (FIBO)

## what is FIBO?

[FIBO](https://spec.edmcouncil.org/fibo/) is the industry-standard financial ontology covering currencies, securities, derivatives, markets, legal entities, and business concepts.

## Quick Start with Claude Code

```bash
# install
uv sync

# connect to claude code
claude mcp add --transport stdio fibo-mcp uv run main.py
```

Restart Claude Code. First run auto-downloads FIBO, then cached instantly.


## Example Result

<table>
<tr>
<th>Claude Code</th>
<th>Claude Code + fibo-mcp </th>
</tr>
<tr>
<td valign="top">

> **"What is a country?"**

A country is a distinct political entity with several key characteristics:

**Core Elements:**
- Defined territory - A geographical area with recognized borders
- Permanent population - People who reside within those borders
- Sovereign government - An independent authority that exercises control over the territory and population
- Capacity to enter relations with other states - The ability to engage in diplomatic and international relations

**Additional aspects:**
- Countries typically have their own legal system, currency, and institutions
- They may be recognized by other countries and international organizations (like the UN)
- They exercise sovereignty - the supreme authority within their territory

**Note:** The terms "country," "nation," "state," and "nation-state" are often used interchangeably but have subtle differences...
</td>
<td valign="top">

> **"What is a country according to FIBO?"**

According to FIBO, a "country" is formally defined as a **sovereign state**:

**Definition:** A non-physical juridical entity that is represented by one centralized government that has sovereignty over a geographic area.

**Key characteristics:**
- A legal entity represented by one centralized government
- Has a permanent population
- Has defined territory
- Has the capacity to enter into relations with other sovereign states

**Hierarchy:**

A sovereign state in FIBO is:
- A type of **polity** (a legal person representing a supranational entity, crown, state, or civil authority)
- A **government body**
- A **legal person**
- A **formal organization**

**FIBO also recognizes:**
- **Federated sovereignty** as a subclass of sovereign state, which represents a polity characterized by a union of partially self-governing states or regions under a central (federal) government

**Precision:** Instead of using the informal term "country," FIBO uses the more precise legal/financial term "sovereign state" to refer to what we commonly call countries, emphasizing their status as legal entities with sovereignty over territory and the ability to enter into international relations.

</td>
</tr>
</table>

**Why this matters:** Financial institutions need precise jurisdiction classification for regulatory compliance, cross-border transactions, sanctions screening, and legal entity identification (LEI). FIBO's structured definitions ensure consistent interpretation across systems and jurisdictions.

## Remote Access

```bash
# run http server
uv run main.py --http --port 8001

# connect from anywhere
claude mcp add --transport http fibo-mcp http://localhost:8001/mcp
```

## Technical Details

- **Data**: 129,990 triples from FIBO ontology (299 RDF/OWL files)
- **Coverage**: 3,371 classes, 16,057 labeled entities, 1,259 properties
- **Cache**: Turtle format at `./data/fibo.db` (auto-created on first run)
- **Updates**: Optional `uv run main.py --force-update`
## Source

FIBO: https://github.com/edmcouncil/fibo
EDM Council: https://spec.edmcouncil.org/fibo/
