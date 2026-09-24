from app.llm.client import get_llm_client


def main() -> None:
    client = get_llm_client()

    response = client.generate(
        "You are testing the Product Intelligence application. "
        "Respond with exactly: LLM connection successful."
    )

    print(response)


if __name__ == "__main__":
    main()