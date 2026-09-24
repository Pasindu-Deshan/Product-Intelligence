from app.agent.agent import ProductIntelligenceAgent
from app.database.connection import get_read_session
from app.schemas.agent import ChatRequest


def main() -> None:
    session = next(get_read_session())

    try:
        agent = ProductIntelligenceAgent(session)

        # ---------------------------------------------------------
        # Question 1
        # ---------------------------------------------------------
        request1 = ChatRequest(
            message="How many hours were logged?"
        )

        response1 = agent.ask(request1)

        print("\n=== QUESTION 1 ===")
        print(request1.message)

        print("\n=== ANSWER 1 ===")
        print(response1.answer)

        print("\n=== CONVERSATION ID ===")
        print(response1.conversation_id)

        print("\n=== ANALYTICS 1 ===")
        print(response1.analytics)

        # ---------------------------------------------------------
        # Question 2 - follow-up
        # ---------------------------------------------------------
        request2 = ChatRequest(
            message="How much of that was QA?",
            conversation_id=response1.conversation_id,
        )

        response2 = agent.ask(request2)

        print("\n=== QUESTION 2 ===")
        print(request2.message)

        print("\n=== ANSWER 2 ===")
        print(response2.answer)

        print("\n=== ANALYTICS 2 ===")
        print(response2.analytics)

        print("\n=== CONTEXT 2 ===")
        print(response2.context)

        print("\n=== EVIDENCE 2 ===")
        print(response2.evidence)

    finally:
        session.close()


if __name__ == "__main__":
    main()