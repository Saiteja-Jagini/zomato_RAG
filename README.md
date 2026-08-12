# Zomato analytics and plotting agent

This project contains LangGraph agents that answer questions from a local
SQLite restaurant database and generate PNG charts. It requires an OpenAI API
key.

## Run it

Create `.env` from `.env.example`, add your API key, and initialize the
database schema:

```powershell
Copy-Item .env.example .env
uv run python tables.py
```

```powershell
uv run langgraph dev
```

The SQL graph is exposed as `agent`; the visualization graph is exposed as
`plotting_agent` and `analytics_agent` in `langgraph.json`.

You can also run the graph directly:

```powershell
uv run python main.py
```

## Database-backed plotting skill

The reusable `plotting-design` skill is stored in the `skills` table with its
prompt, configuration, input/output schemas, scope, status, and autonomy
requirements. The `skill_executions` table records each plotting success or
failure.

On first initialization, `skills/plotting-design/SKILL.md` seeds the database
record. The existing database row is never overwritten on later starts, so it
becomes the runtime source of truth. Restart the LangGraph server after changing
the stored prompt because the active prompt is loaded when the agent starts.

For every chart request, the application:

1. Loads the active skill prompt and metadata from SQLite.
2. Combines the prompt with the user's request.
3. Queries restaurant data using the read-only SQL tools.
4. Validates the generated plotting input against the stored schema.
5. Executes the plot in an isolated process using the stored configuration.
6. Validates and saves the result, then records success or failure.
7. Recalculates the skill's autonomy level from its stored requirements and
   execution history.

## Test the plotting agent with Agent Chat UI

Start this project's LangGraph server:

```powershell
uv run langgraph dev
```

In a second terminal, clone and start the Agent Chat UI:

```powershell
git clone https://github.com/langchain-ai/agent-chat-ui.git
cd agent-chat-ui
pnpm install
Copy-Item .env.example .env
```

Make these minor changes in `agent-chat-ui/.env` so the UI connects to the
local plotting agent:

```env
NEXT_PUBLIC_API_URL=http://localhost:2024
NEXT_PUBLIC_ASSISTANT_ID=plotting_agent
NEXT_PUBLIC_AUTH_SCHEME=
```

Then start the UI:

```powershell
pnpm dev
```

Open `http://localhost:3000` and try a request such as:

> Create a bar chart of the top 10 restaurants by rating.

The `plotting_agent` will query the local database and return a generated PNG
from the `outputs/` directory.
