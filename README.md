# Basic LangGraph project

This project contains a small deterministic graph that can be run locally
without an API key.

## Run it

```powershell
uv run langgraph dev
```

The graph is exposed as `agent` and is configured in `langgraph.json`.

You can also run the graph directly:

```powershell
uv run python main.py
```

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

