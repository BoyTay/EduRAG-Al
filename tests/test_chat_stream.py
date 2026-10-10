import json
import unittest
from unittest import mock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
from db import Base, ChatHistory, get_db


class _FakeRag:
    def __init__(self, fail=False):
        self.fail = fail

    async def achat(self, question, *_args):
        return "Câu trả lời đầy đủ.", [], 0.5, None

    async def achat_stream(self, question, *_args):
        yield "token", "Câu trả lời "
        if self.fail:
            raise RuntimeError("secret internal path C:/x")
        yield "token", "nháp"
        yield "final", ("Câu trả lời đầy đủ.", [], 0.5, None)


def _parse_sse(text):
    events = []
    for block in text.strip().split("\n\n"):
        lines = block.split("\n")
        events.append((lines[0].removeprefix("event: "), json.loads(lines[1].removeprefix("data: "))))
    return events


class ChatStreamTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(bind=engine)
        self.Session = sessionmaker(bind=engine)

        def override_get_db():
            session = self.Session()
            try:
                yield session
            finally:
                session.close()

        main.app.dependency_overrides[get_db] = override_get_db
        main.app.dependency_overrides[main.get_current_user] = lambda: {
            "user_id": 1, "role": "student", "email": "s@example.com", "name": "s@example.com",
        }
        main.chat_limiter.reset()
        self.client = TestClient(main.app)
        self.patches = [mock.patch.object(main, "SessionLocal", self.Session)]
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in self.patches:
            patch.stop()
        main.app.dependency_overrides.clear()

    def _post(self, rag):
        with mock.patch.object(main, "rag_chain_instance", rag):
            return self.client.post("/chat/stream", json={"question": "Điều kiện tốt nghiệp là gì?"})

    def test_streams_tokens_then_final_and_saves_history(self):
        response = self._post(_FakeRag())
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("text/event-stream"))
        events = _parse_sse(response.text)
        self.assertEqual([name for name, _ in events], ["token", "token", "final"])
        final = events[-1][1]
        self.assertEqual(final["answer"], "Câu trả lời đầy đủ.")
        self.assertIn("message_id", final)
        with self.Session() as db:
            self.assertEqual(db.query(ChatHistory).count(), 1)

    def test_error_after_start_is_reported_without_internal_details(self):
        response = self._post(_FakeRag(fail=True))
        self.assertEqual(response.status_code, 200)
        events = _parse_sse(response.text)
        self.assertEqual(events[-1][0], "error")
        self.assertNotIn("secret", response.text)

    def test_non_streaming_chat_still_works(self):
        with mock.patch.object(main, "rag_chain_instance", _FakeRag()):
            response = self.client.post("/chat", json={"question": "Điều kiện tốt nghiệp là gì?"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], "Câu trả lời đầy đủ.")


if __name__ == "__main__":
    unittest.main()
