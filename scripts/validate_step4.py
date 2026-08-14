from knowledge_intelligence.application.container import build_application
from knowledge_intelligence.config import get_settings


def main() -> None:
    settings = get_settings()
    application = build_application(settings)

    print("Platform Knowledge Agent is ready.")
    print("Type 'exit' to finish.")

    while True:
        question = input("\nQuestion: ").strip()

        if question.lower() == "exit":
            break

        if not question:
            continue

        result = application.platform_knowledge_service.answer(question)

        print()
        print(result.answer)


if __name__ == "__main__":
    main()
