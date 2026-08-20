"""The HTTP surface, driven through the real app with stubbed collaborators."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import main
from app.models import KnowledgeAnswer, ReindexSummary
from app.slack import SlackAction

ADMIN_TOKEN = "s3cret-admin-token"
FORM = {"content-type": "application/x-www-form-urlencoded"}


class Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []


class StubAgent:
    def __init__(self, recorder: Recorder) -> None:
        self.recorder = recorder

    def answer(self, question: str, *, conversation_id: str | None = None) -> KnowledgeAnswer:
        self.recorder.calls.append(("answer", question, conversation_id))
        return KnowledgeAnswer(answer=f"Use the cluster [S1] guide. {question}")


class ExplodingAgent:
    def answer(self, question: str, *, conversation_id: str | None = None) -> KnowledgeAnswer:
        raise RuntimeError("internal detail that must not leak")


class StubSlack:
    def __init__(self, recorder: Recorder) -> None:
        self.recorder = recorder
        self.valid = True
        self.seen: set[str] = set()
        self.feedback_store = self

    def verify(self, body: bytes, timestamp: str | None, signature: str | None) -> bool:
        return self.valid

    def accept(self, event_id: str) -> bool:
        if event_id in self.seen:
            return False
        self.seen.add(event_id)
        return True

    def process(self, channel: str, thread_ts: str, text: str) -> None:
        self.recorder.calls.append(("process", channel, thread_ts, text))

    def process_slash(self, question: str, response_url: str, conversation_id: str) -> None:
        self.recorder.calls.append(("slash", question, response_url, conversation_id))

    def record(self, action: SlackAction) -> None:
        self.recorder.calls.append(("feedback", action.rating))

    def parse_action(self, payload: dict[str, object]) -> SlackAction | None:
        actions = payload.get("actions")
        if not isinstance(actions, list) or not actions:
            return None
        first = actions[0]
        assert isinstance(first, dict)
        action_id = str(first.get("action_id", ""))
        if action_id.startswith("knowledge_followup_"):
            return SlackAction(
                kind="followup", channel="C1", thread_ts="1.0", question=str(first.get("value"))
            )
        if action_id.startswith("knowledge_feedback_"):
            return SlackAction(
                kind="feedback", answer_id="a", response_type="general", rating="helpful"
            )
        return None


class StubIngestion:
    def __init__(self) -> None:
        self.github = None
        self.vectors = self

    def close(self) -> None:
        return None

    def run(self) -> ReindexSummary:
        return ReindexSummary(documents=3, chunks=9, vectors=9, skipped=1)


class StubSettings:
    class _Secret:
        def __init__(self, value: str) -> None:
            self.value = value

        def get_secret_value(self) -> str:
            return self.value

    admin_token = _Secret(ADMIN_TOKEN)


@pytest.fixture
def recorder() -> Recorder:
    return Recorder()


@pytest.fixture
def slack(recorder: Recorder) -> StubSlack:
    return StubSlack(recorder)


@pytest.fixture
def client(recorder: Recorder, slack: StubSlack) -> Iterator[TestClient]:
    main.app.state.application = main.Application(
        settings=StubSettings(),  # type: ignore[arg-type]
        agent=StubAgent(recorder),  # type: ignore[arg-type]
        search=type("S", (), {"cached_chunk_count": 42})(),  # type: ignore[arg-type]
        ingestion=StubIngestion(),  # type: ignore[arg-type]
        vector_store_reachable=True,
        slack=slack,  # type: ignore[arg-type]
        reindex_lock=threading.Lock(),
    )
    yield TestClient(main.app)
    main.app.state.application = None


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "healthy"}


def test_ready_reports_index_state(client: TestClient) -> None:
    body = client.get("/ready").json()
    assert body["status"] == "ready"
    assert body["cached_chunks"] == 42


def test_query_returns_only_the_answer(client: TestClient) -> None:
    body = client.post("/knowledge/query", json={"prompt": "What is EKS?"}).json()
    assert set(body) == {"answer"}


def test_query_strips_internal_source_markers(client: TestClient) -> None:
    body = client.post("/knowledge/query", json={"prompt": "What is EKS?"}).json()
    assert "[S1]" not in body["answer"]


def test_query_rejects_a_too_short_prompt(client: TestClient) -> None:
    assert client.post("/knowledge/query", json={"prompt": "a"}).status_code == 422


def test_query_rejects_unknown_fields(client: TestClient) -> None:
    response = client.post("/knowledge/query", json={"prompt": "hello there", "extra": 1})
    assert response.status_code == 422


def test_conversation_id_is_forwarded(client: TestClient, recorder: Recorder) -> None:
    client.post("/knowledge/query", json={"prompt": "follow up", "conversation_id": "abc"})
    assert recorder.calls[-1] == ("answer", "follow up", "abc")


@pytest.mark.parametrize(
    ("headers", "expected"),
    [({}, 401), ({"X-Admin-Token": "wrong"}, 401), ({"X-Admin-Token": ADMIN_TOKEN}, 200)],
)
def test_reindex_requires_the_admin_token(
    client: TestClient, headers: dict[str, str], expected: int
) -> None:
    assert client.post("/admin/reindex", headers=headers).status_code == expected


def test_slack_rejects_a_bad_signature(client: TestClient, slack: StubSlack) -> None:
    slack.valid = False
    assert client.post("/slack/events", content=b"{}").status_code == 401


def test_slack_url_verification_echoes_the_challenge(client: TestClient) -> None:
    response = client.post("/slack/events", json={"type": "url_verification", "challenge": "abc"})
    assert response.json() == {"challenge": "abc"}


def test_app_mention_is_dispatched(client: TestClient, recorder: Recorder) -> None:
    event = {"type": "app_mention", "channel": "C9", "text": "hi", "ts": "111.1"}
    client.post("/slack/events", json={"event_id": "E1", "event": event})
    assert ("process", "C9", "111.1", "hi") in recorder.calls


def test_duplicate_events_are_ignored(client: TestClient, recorder: Recorder) -> None:
    event = {"type": "app_mention", "channel": "C9", "text": "hi", "ts": "111.1"}
    client.post("/slack/events", json={"event_id": "E2", "event": event})
    recorder.calls.clear()
    client.post("/slack/events", json={"event_id": "E2", "event": event})
    assert recorder.calls == []


def test_bot_messages_are_ignored(client: TestClient, recorder: Recorder) -> None:
    event = {"type": "app_mention", "channel": "C9", "text": "hi", "ts": "1.1", "bot_id": "B1"}
    client.post("/slack/events", json={"event_id": "E3", "event": event})
    assert recorder.calls == []


def test_malformed_event_payload_is_rejected(client: TestClient) -> None:
    assert client.post("/slack/events", content=b"{oops").status_code == 400


def test_slash_command_acknowledges_in_channel(client: TestClient, recorder: Recorder) -> None:
    body = "command=/ask-tme&text=What is TME&response_url=https://hooks.slack.com/x"
    response = client.post("/slack/events", headers=FORM, content=body)
    assert response.json()["response_type"] == "in_channel"
    assert any(call[0] == "slash" for call in recorder.calls)


def test_unsupported_slash_command_is_ephemeral(client: TestClient) -> None:
    body = "command=/other&text=hi&response_url=https://hooks.slack.com/x"
    assert client.post("/slack/events", headers=FORM, content=body).json()["response_type"] == (
        "ephemeral"
    )


def test_empty_slash_text_prompts_the_user(client: TestClient) -> None:
    body = "command=/ask-tme&text=&response_url=https://hooks.slack.com/x"
    assert "What would you like" in client.post("/slack/events", headers=FORM, content=body).json()[
        "text"
    ]


def test_response_url_must_belong_to_slack(client: TestClient) -> None:
    body = "command=/ask-tme&text=hi&response_url=https://evil.example.com/x"
    assert client.post("/slack/events", headers=FORM, content=body).status_code == 400


def test_followup_button_continues_the_thread(client: TestClient, recorder: Recorder) -> None:
    payload = json.dumps({"actions": [{"action_id": "knowledge_followup_1", "value": "Next?"}]})
    client.post("/slack/events", headers=FORM, content=f"payload={payload}")
    assert any(call[0] == "process" for call in recorder.calls)


def test_feedback_button_is_recorded(client: TestClient, recorder: Recorder) -> None:
    payload = json.dumps({"actions": [{"action_id": "knowledge_feedback_1", "value": "a:g:h"}]})
    client.post("/slack/events", headers=FORM, content=f"payload={payload}")
    assert ("feedback", "helpful") in recorder.calls


def test_unknown_interaction_is_ignored(client: TestClient, recorder: Recorder) -> None:
    payload = json.dumps({"actions": [{"action_id": "unknown", "value": "x"}]})
    response = client.post("/slack/events", headers=FORM, content=f"payload={payload}")
    assert response.json() == {"ok": True}
    assert recorder.calls == []


def test_unhandled_errors_return_a_safe_message(recorder: Recorder, slack: StubSlack) -> None:
    main.app.state.application = main.Application(
        settings=StubSettings(),  # type: ignore[arg-type]
        agent=ExplodingAgent(),  # type: ignore[arg-type]
        search=type("S", (), {"cached_chunk_count": 0})(),  # type: ignore[arg-type]
        ingestion=StubIngestion(),  # type: ignore[arg-type]
        vector_store_reachable=True,
        slack=slack,  # type: ignore[arg-type]
        reindex_lock=threading.Lock(),
    )
    safe = TestClient(main.app, raise_server_exceptions=False)
    response = safe.post("/knowledge/query", json={"prompt": "trigger failure"})
    assert response.status_code == 500
    assert response.json() == {"message": "The request could not be completed."}
    assert "internal detail" not in response.text
    assert "X-Correlation-ID" in response.headers
    main.app.state.application = None
