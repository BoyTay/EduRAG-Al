"""
auth.py - Dependency xác thực dùng chung và giới hạn tần suất request.
Đặt riêng khỏi main.py để main.py và admin.py cùng dùng một bản, tránh import vòng.
"""

import threading
import time
from collections import defaultdict, deque
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from db import get_auth_session, get_db


def get_current_user(
    authorization: Optional[str] = Header(None), db: Session = Depends(get_db)
) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Vui lòng đăng nhập để tiếp tục")
    session = get_auth_session(db, authorization.removeprefix("Bearer ").strip())
    if not session:
        raise HTTPException(status_code=401, detail="Phiên đăng nhập đã hết hạn; vui lòng đăng nhập lại")
    # "name" giữ lại cho các endpoint quản trị đang ghi nhật ký theo actor.
    return {
        "user_id": session.user_id,
        "role": session.user_role,
        "email": session.email,
        "name": session.email,
    }


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Chỉ quản trị viên được phép truy cập")
    return current_user


class RateLimiter:
    """Giới hạn số request trong cửa sổ trượt theo khóa (IP, hoặc IP + user).

    Lưu trong bộ nhớ của một tiến trình; đủ cho triển khai một worker như
    docker-compose hiện tại. Nếu chạy nhiều worker cần chuyển sang Redis.
    """

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> Optional[int]:
        """Ghi nhận một request; trả về số giây cần chờ nếu vượt giới hạn, ngược lại None."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] >= self.window_seconds:
                hits.popleft()
            if len(hits) >= self.max_requests:
                return max(1, int(self.window_seconds - (now - hits[0])) + 1)
            hits.append(now)
            # Dọn khóa cũ để dict không phình mãi.
            if len(self._hits) > 10_000:
                for stale in [k for k, v in self._hits.items() if not v or now - v[-1] >= self.window_seconds]:
                    del self._hits[stale]
            return None

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def rate_limit(limiter: RateLimiter, scope: str):
    """Tạo dependency FastAPI trả 429 khi client vượt giới hạn."""

    def dependency(request: Request) -> None:
        retry_after = limiter.check(f"{scope}:{client_ip(request)}")
        if retry_after is not None:
            raise HTTPException(
                status_code=429,
                detail="Quá nhiều yêu cầu; vui lòng thử lại sau ít phút",
                headers={"Retry-After": str(retry_after)},
            )

    return dependency


def rate_limit_user(limiter: RateLimiter, scope: str):
    """Như rate_limit nhưng tính theo tài khoản đã đăng nhập (dùng cho /chat)."""

    def dependency(current_user: dict = Depends(get_current_user)) -> None:
        retry_after = limiter.check(f"{scope}:{current_user['role']}:{current_user['user_id']}")
        if retry_after is not None:
            raise HTTPException(
                status_code=429,
                detail="Bạn đang gửi câu hỏi quá nhanh; vui lòng chờ một chút",
                headers={"Retry-After": str(retry_after)},
            )

    return dependency
