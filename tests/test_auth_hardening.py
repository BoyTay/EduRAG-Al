import unittest
from unittest import mock

from fastapi import HTTPException
from fastapi.testclient import TestClient

from auth import RateLimiter, rate_limit_user


class RateLimiterTests(unittest.TestCase):
    def test_blocks_after_limit_and_reports_retry_after(self):
        limiter = RateLimiter(2, 60)
        self.assertIsNone(limiter.check("k"))
        self.assertIsNone(limiter.check("k"))
        retry = limiter.check("k")
        self.assertIsNotNone(retry)
        self.assertGreaterEqual(retry, 1)
        self.assertIsNone(limiter.check("other"))

    def test_window_expires(self):
        limiter = RateLimiter(1, 10)
        with mock.patch("auth.time.monotonic", return_value=100.0):
            self.assertIsNone(limiter.check("k"))
        with mock.patch("auth.time.monotonic", return_value=111.0):
            self.assertIsNone(limiter.check("k"))

    def test_user_dependency_raises_429(self):
        dep = rate_limit_user(RateLimiter(1, 60), "chat")
        user = {"user_id": 1, "role": "student"}
        dep(user)
        with self.assertRaises(HTTPException) as ctx:
            dep(user)
        self.assertEqual(ctx.exception.status_code, 429)
        self.assertIn("Retry-After", ctx.exception.headers)


class EndpointHardeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import main
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool
        from db import Base, get_db

        # DB trong bộ nhớ để test không đụng chat_history.db thật.
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(bind=engine)
        TestSession = sessionmaker(bind=engine)

        def override_get_db():
            session = TestSession()
            try:
                yield session
            finally:
                session.close()

        main.app.dependency_overrides[get_db] = override_get_db
        cls.main = main
        # Không dùng context manager nên lifespan (nạp model) không chạy.
        cls.client = TestClient(main.app)

    @classmethod
    def tearDownClass(cls):
        cls.main.app.dependency_overrides.clear()

    def setUp(self):
        self.main.auth_limiter.reset()

    def test_documents_list_requires_login(self):
        self.assertEqual(self.client.get("/admin/documents").status_code, 401)

    def test_login_is_rate_limited(self):
        codes = [
            self.client.post("/auth/login", json={"username": "a@b.c", "password": "x"}).status_code
            for _ in range(12)
        ]
        self.assertIn(429, codes)
        self.assertEqual(codes[-1], 429)


if __name__ == "__main__":
    unittest.main()
