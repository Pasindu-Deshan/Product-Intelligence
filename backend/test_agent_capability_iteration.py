from app.agent.agent import ProductIntelligenceAgent
from app.database.connection import get_read_session
from app.schemas.agent import ChatRequest


def main() -> None:
    session = next(get_read_session())

    try:
        agent = ProductIntelligenceAgent(session)

        # =========================================================
        # TEST
        # Capability + Iteration filter
        # =========================================================
        request = ChatRequest(
            message=(
                "How much time did we spend on Authentication "
                "in Product\\Sprint 24?"
            )
        )

        response = agent.ask(request)

        print("\n" + "=" * 70)
        print("QUESTION")
        print("=" * 70)
        print(request.message)

        print("\n" + "=" * 70)
        print("ANSWER")
        print("=" * 70)
        print(response.answer)

        print("\n" + "=" * 70)
        print("CONVERSATION ID")
        print("=" * 70)
        print(response.conversation_id)

        print("\n" + "=" * 70)
        print("ANALYTICS")
        print("=" * 70)
        print(response.analytics)

        print("\n" + "=" * 70)
        print("EVIDENCE")
        print("=" * 70)
        print(response.evidence)

        print("\n" + "=" * 70)
        print("CONTEXT")
        print("=" * 70)
        print(response.context)

    finally:
        session.close()


if __name__ == "__main__":
    main()