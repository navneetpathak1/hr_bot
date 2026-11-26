
import anyio

from mcp import Client, StdioServerParameters
from mcp.types import TextContent


server_params = StdioServerParameters(
    command="uv",
    args=[
        "run",
        "python",
        "-m",
        "MCP_.server"
    ]
)


async def main():

    async with Client(server_params) as client:

        print("\nConnected to HR RAG MCP Server")

        # 1. List available prompts
        prompt_result = await client.list_prompts()

        print("\nAvailable Prompts:")

        for prompt in prompt_result.prompts:
            print(f"- {prompt.name}: {prompt.description}")

        result = await client.get_prompt(
            "user_hr_prompt",
           
        )

        print("\nGenerated MCP Prompt:")

        for message in result.messages:

            if isinstance(message.content, TextContent):
                print(message.content.text)

        print("\nPrompt fetched successfully!")


if __name__ == "__main__":
    anyio.run(main)

# uv run python -m MCP_.client
