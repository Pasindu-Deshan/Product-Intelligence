from app.agent.llm import LLMClient


def main() -> None:
    client = LLMClient()

    response = client.chat(
        messages=[
            {
                "role": "system",
                "content": (
                    "You are testing the Product Intelligence "
                    "LLM connection."
                ),
            },
            {
                "role": "user",
                "content": "Respond with exactly: Agent LLM connection successful.",
            },
        ]
    )

    print("Content:")
    print(response.content)

    print("\nTool calls:")
    print(response.tool_calls)


if __name__ == "__main__":
    main()