from knowledge_intelligence.application.container import build_github_knowledge_service
from knowledge_intelligence.config import get_settings


def main() -> None:
    """Run an interactive read-only GitHub Knowledge Agent session."""
    service = build_github_knowledge_service(get_settings())
    while True:
        question = input("\nGitHub question, or 'exit': ").strip()
        if question.casefold() == "exit":
            return
        result = service.answer(question)
        print(f"\n{result.answer}")


if __name__ == "__main__":
    main()
