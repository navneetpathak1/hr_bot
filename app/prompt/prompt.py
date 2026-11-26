import anyio

from pathlib import Path
from mcp import Client, StdioServerParameters
from mcp.types import TextContent


PROJECT_ROOT = Path(__file__).resolve().parents[2]

server_params = StdioServerParameters(
    command="uv",
    args=[
        "run",
        "python",
        "-m",
        "MCP_.server"
    ],
    cwd=str(PROJECT_ROOT)
)


async def fetch_mcp_prompt(prompt_name: str) -> str:

    async with Client(server_params) as client:

        result = await client.get_prompt(prompt_name)

        prompt_parts = []

        for message in result.messages:

            if isinstance(message.content, TextContent):
                prompt_parts.append(message.content.text)

        return "\n".join(prompt_parts)



HR_PROMPT: str = ""
REWRITE_PROMPT: str = ""

async def initialize_prompts():

    global HR_PROMPT, REWRITE_PROMPT

    HR_PROMPT = await fetch_mcp_prompt("user_hr_prompt")

    REWRITE_PROMPT = await fetch_mcp_prompt(
        "rewrite_user_query_prompt"
    )


if __name__ == "__main__":
    anyio.run(initialize_prompts)

    print(HR_PROMPT)
    print(REWRITE_PROMPT)