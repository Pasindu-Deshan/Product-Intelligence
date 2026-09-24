from app.agent.agent import ProductIntelligenceAgent
from app.database.connection import get_read_session
from app.schemas.agent import ChatRequest


def main() -> None:
    session = next(get_read_session())

    try:
        agent = ProductIntelligenceAgent(session)

        # =========================================================
        # QUESTION 1
        # =========================================================
        request1 = ChatRequest(
            message="How much time did we spend on Authentication?"
        )

        response1 = agent.ask(request1)

        print("\n" + "=" * 70)
        print("QUESTION 1")
        print("=" * 70)
        print(request1.message)

        print("\n" + "=" * 70)
        print("ANSWER 1")
        print("=" * 70)
        print(response1.answer)

        print("\n" + "=" * 70)
        print("CONVERSATION ID")
        print("=" * 70)
        print(response1.conversation_id)

        print("\n" + "=" * 70)
        print("ANALYTICS 1")
        print("=" * 70)
        print(response1.analytics)

        print("\n" + "=" * 70)
        print("EVIDENCE 1")
        print("=" * 70)
        print(response1.evidence)

        print("\n" + "=" * 70)
        print("CONTEXT 1")
        print("=" * 70)
        print(response1.context)

        # =========================================================
        # QUESTION 2 - FOLLOW-UP
        # =========================================================
        request2 = ChatRequest(
            message="Which tickets contributed to it?",
            conversation_id=response1.conversation_id,
        )

        response2 = agent.ask(request2)

        print("\n" + "=" * 70)
        print("QUESTION 2 - FOLLOW-UP")
        print("=" * 70)
        print(request2.message)

        print("\n" + "=" * 70)
        print("ANSWER 2")
        print("=" * 70)
        print(response2.answer)

        print("\n" + "=" * 70)
        print("ANALYTICS 2")
        print("=" * 70)
        print(response2.analytics)

        print("\n" + "=" * 70)
        print("EVIDENCE 2")
        print("=" * 70)
        print(response2.evidence)

        print("\n" + "=" * 70)
        print("CONTEXT 2")
        print("=" * 70)
        print(response2.context)

    finally:
        session.close()


if __name__ == "__main__":
    main()