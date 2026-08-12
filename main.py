import json
import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model

from skill_store import PLOTTING_SKILL_ID, load_skill
from tools.graph_generator_tool import execute_plot_script
from tools.sql_tool import sql_db_list_tables, sql_db_query, sql_db_schema


load_dotenv()

PLOTTING_SKILL = load_skill(PLOTTING_SKILL_ID)

model = init_chat_model(
    os.getenv("PLOTTING_AGENT_MODEL")
    or os.getenv("ANALYTICS_AGENT_MODEL")
    or PLOTTING_SKILL.configuration.get(
        "model", "openai:gpt-5.4-mini-2026-03-17"
    )
)

ANALYTICS_PROMPT = f"""
You are a database analytics and visualization agent.

ACTIVE DATABASE-BACKED SKILL:
- Name: {PLOTTING_SKILL.name}
- Version: {PLOTTING_SKILL.version}
- Scope: {PLOTTING_SKILL.scope}
- Status: {PLOTTING_SKILL.status}
- Current autonomy level: {PLOTTING_SKILL.autonomy_level}

Combine the following stored skill prompt with the user's request:

{PLOTTING_SKILL.prompt_template}

Stored configuration:
{json.dumps(PLOTTING_SKILL.configuration, indent=2)}

Stored input schema:
{json.dumps(PLOTTING_SKILL.input_schema, indent=2)}

Stored output schema:
{json.dumps(PLOTTING_SKILL.output_schema, indent=2)}

Stored autonomy requirements:
{json.dumps(PLOTTING_SKILL.autonomy_requirements, indent=2)}

MANDATORY VISUALIZATION ROUTING:
- Treat every request containing chart, graph, plot, visualize, visualisation,
  bar, line, scatter, histogram, heatmap, or pie as an image request.
- For every image request, you MUST call execute_plot_script after querying the
  database. Never answer with ASCII/Unicode bars, a Markdown text chart, or a
  Python code block. Never merely offer to create a Matplotlib chart.
- The final response must include the image tool result and its PNG path. Do
  not expose generated Python unless the user explicitly asks for the code.

For database questions, inspect tables and schemas before writing SQLite SQL.
Only issue read-only SELECT queries. For a textual answer, query only the rows
needed and explain the result.

For visualization requests, always follow this tool sequence:
1. Inspect the relevant tables with sql_db_list_tables and sql_db_schema.
2. Call sql_db_query with a read-only query that returns the categories,
   measures, and ordering required by the chart.
3. Check that the structured result has columns and non-empty rows.
4. Write concise Matplotlib or Seaborn code and pass it to
   execute_plot_script together with the exact sql_db_query result.
5. The script must not import modules, read files, call show/savefig, or access
   the network. It receives data, plt, sns, and np. Convert rows by column
   position or create dictionaries with zip(data["columns"], row).
6. Common pyplot operations such as figure, bar, title, xlabel, ylabel, text,
   xticks, and tight_layout are supported. Do not call plt.show(); the tool
   saves and returns the current figure automatically.
7. If execution fails validation, correct the code and retry once.
8. Return the verified PNG image and briefly describe what the chart shows.
9. The plotting tool validates the stored input/output contracts and records
   every success or failure. Do not claim an execution status that the tool did
   not return.

Never claim an image exists unless execute_plot_script returns success=true.
"""

analytics_agent = create_agent(
    model=model,
    tools=[
        sql_db_list_tables,
        sql_db_schema,
        sql_db_query,
        execute_plot_script,
    ],
    system_prompt=ANALYTICS_PROMPT,
)
