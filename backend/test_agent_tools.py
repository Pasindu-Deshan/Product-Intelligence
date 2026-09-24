from app.agent.llm import LLMClient
from app.agent.tools import tool_schemas


def main() -> None:
    client = LLMClient()

    response = client.chat(
        messages=[
            {
                "role": "system",
                "content": (
                    "You are testing the Product Intelligence analytics agent. "
                    "When the user asks for total hours, use the "
                    "get_time_summary tool."
                ),
            },
            {
                "role": "user",
                "content": "How many hours were logged?",
            },
        ],
        tools=tool_schemas(),
    )

    print("Content:")
    print(response.content)

    print("\nTool calls:")

    for call in response.tool_calls:
        print(f"Name: {call.name}")
        print(f"Arguments: {call.arguments}")


if __name__ == "__main__":
    main()