"""AstrBot 知识库 HTTP 客户端（本地 WebUI OpenAPI /api/v1）。

通过本机 AstrBot 配置中的 dashboard.jwt_secret 签发短期 JWT，调用
本地 WebUI 的知识库接口，避免依赖登录密码。仅用于本机运维脚本。

用法::

    from kb_client import KBClient
    kb = KBClient()
    kb.list_kbs()
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import jwt
import requests

DEFAULT_CONFIG = Path("astrbot/data/cmd_config.json")
BASE_URL = "http://127.0.0.1:6185/api/v1"


def resolve_config_path(config_path: Path | str | None = None) -> Path:
    """Resolve the AstrBot config path from argument, env var or default.

    Args:
        config_path: Explicit path passed by the caller.

    Returns:
        Path to AstrBot's ``cmd_config.json``.
    """
    if config_path:
        return Path(config_path)
    env = os.environ.get("ASTRBOT_CONFIG")
    return Path(env) if env else DEFAULT_CONFIG


class KBClient:
    """Minimal client for the AstrBot dashboard knowledge-base API."""

    def __init__(
        self,
        config_path: Path | str | None = None,
        base_url: str | None = None,
    ) -> None:
        config_path = resolve_config_path(config_path)
        base_url = base_url or os.environ.get("ASTRBOT_BASE_URL", BASE_URL)
        cfg = json.loads(config_path.read_text(encoding="utf-8-sig"))
        secret = cfg["dashboard"]["jwt_secret"]
        token = jwt.encode(
            {
                "username": cfg["dashboard"].get("username", "astrbot"),
                "iat": int(time.time()),
                "exp": int(time.time()) + 3600,
            },
            secret,
            algorithm="HS256",
        )
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    def _request(self, method: str, path: str, **kwargs):
        url = f"{self.base_url}{path}"
        resp = self.session.request(method, url, timeout=kwargs.pop("timeout", 120), **kwargs)
        try:
            payload = resp.json()
        except ValueError as exc:
            raise RuntimeError(f"{method} {path} -> HTTP {resp.status_code}: {resp.text[:500]}") from exc
        if resp.status_code >= 400 or payload.get("status") == "error":
            raise RuntimeError(
                f"{method} {path} -> HTTP {resp.status_code}: {payload.get('message') or payload}"
            )
        return payload.get("data")

    # ---- 知识库 ----
    def list_kbs(self) -> dict:
        return self._request("GET", "/knowledge-bases", params={"page": 1, "page_size": 100})

    def create_kb(
        self,
        kb_name: str,
        description: str,
        embedding_provider_id: str = "openai_embedding",
        emoji: str = "📚",
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        top_k_dense: int = 50,
        top_k_sparse: int = 50,
        top_m_final: int = 5,
    ) -> dict:
        body = {
            "kb_name": kb_name,
            "name": kb_name,  # legacy alias
            "description": description,
            "emoji": emoji,
            "embedding_provider_id": embedding_provider_id,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "top_k_dense": top_k_dense,
            "top_k_sparse": top_k_sparse,
            "top_m_final": top_m_final,
        }
        return self._request("POST", "/knowledge-bases", json=body)

    def get_kb(self, kb_id: str) -> dict:
        return self._request("GET", f"/knowledge-bases/{kb_id}")

    def update_kb(self, kb_id: str, kb_name: str, description: str, emoji: str) -> dict:
        """Update display metadata of an existing knowledge base."""
        body = {
            "kb_name": kb_name,
            "name": kb_name,
            "description": description,
            "emoji": emoji,
        }
        return self._request("PUT", f"/knowledge-bases/{kb_id}", json=body)

    def delete_kb(self, kb_id: str) -> dict:
        return self._request("DELETE", f"/knowledge-bases/{kb_id}")

    def get_stats(self, kb_id: str) -> dict:
        return self._request("GET", f"/knowledge-bases/{kb_id}/stats")

    def list_documents(self, kb_id: str, page: int = 1, page_size: int = 100) -> dict:
        return self._request(
            "GET",
            f"/knowledge-bases/{kb_id}/documents",
            params={"page": page, "page_size": page_size},
        )

    def delete_document(self, kb_id: str, doc_id: str) -> dict:
        return self._request("DELETE", f"/knowledge-bases/{kb_id}/documents/{doc_id}")

    def delete_all_documents(self, kb_id: str) -> int:
        """Delete every document (and its chunks/vectors) in a knowledge base.

        Args:
            kb_id: Target knowledge base id.

        Returns:
            Number of documents deleted.
        """
        deleted = 0
        while True:
            page = self.list_documents(kb_id, page=1, page_size=100)
            items = page.get("items") or []
            if not items:
                return deleted
            for doc in items:
                self.delete_document(kb_id, doc["doc_id"])
                deleted += 1

    def list_chunks(self, kb_id: str, doc_id: str | None = None, page: int = 1, page_size: int = 50) -> dict:
        params = {"page": page, "page_size": page_size}
        if doc_id:
            params["document_id"] = doc_id
        return self._request("GET", f"/knowledge-bases/{kb_id}/chunks", params=params)

    def retrieve(self, kb_id: str, kb_names: list[str], query: str, top_k: int = 5) -> dict:
        """Retrieve chunks across named knowledge bases.

        Args:
            kb_id: Any existing knowledge base id (path parameter, unused by service).
            kb_names: Knowledge base display names (not ids).
            query: Search query.
            top_k: Final top-k after fusion.

        Returns:
            Retrieval payload with ``results``, each with a ``score`` field.
        """
        return self._request(
            "POST",
            f"/knowledge-bases/{kb_id}/retrieve",
            json={"query": query, "kb_names": kb_names, "top_k": top_k},
        )

    # ---- 文档导入（预切块） ----
    def import_documents(
        self,
        kb_id: str,
        documents: list[dict],
        batch_size: int = 32,
        tasks_limit: int = 3,
        max_retries: int = 3,
    ) -> dict:
        """Start a background import task.

        Args:
            kb_id: Target knowledge base id.
            documents: List of ``{"file_name", "file_type", "chunks": [str]}``.
            batch_size: Embedding batch size.
            tasks_limit: Concurrent embedding tasks.
            max_retries: Retry count for embedding calls.

        Returns:
            Task creation payload containing ``task_id``.
        """
        body = {
            "documents": documents,
            "batch_size": batch_size,
            "tasks_limit": tasks_limit,
            "max_retries": max_retries,
        }
        return self._request("POST", f"/knowledge-bases/{kb_id}/documents/import", json=body)

    def wait_task(self, task_id: str, timeout: float = 1800, interval: float = 3) -> dict:
        """Poll an import task until it leaves the processing state."""
        deadline = time.time() + timeout
        last = None
        while time.time() < deadline:
            last = self._request("GET", f"/knowledge-bases/tasks/{task_id}")
            status = last.get("status")
            if status in {"completed", "failed"}:
                return last
            time.sleep(interval)
        raise TimeoutError(f"task {task_id} not finished in {timeout}s, last={last}")

    def upload_chunks(
        self,
        kb_id: str,
        file_name: str,
        chunks: list[str],
        *,
        file_type: str = "txt",
        shard_size: int = 800,
        batch_size: int = 32,
        tasks_limit: int = 3,
        max_retries: int = 3,
        timeout: float = 3600,
    ) -> list[dict]:
        """Import chunk texts as one or more documents, waiting for each task.

        Args:
            kb_id: Target knowledge base id.
            file_name: Base document name shown in the dashboard.
            chunks: Pre-chunked texts.
            file_type: Document type label.
            shard_size: Number of chunks per document record.
            batch_size: Embedding batch size.
            tasks_limit: Concurrent embedding tasks.
            max_retries: Retry count for embedding calls.
            timeout: Per-task wait timeout in seconds.

        Returns:
            List of completed task payloads.
        """
        results = []
        shards = [chunks[i : i + shard_size] for i in range(0, len(chunks), shard_size)]
        for idx, shard in enumerate(shards, start=1):
            name = file_name if len(shards) == 1 else f"{file_name}-part{idx}"
            task = self.import_documents(
                kb_id,
                [{"file_name": name, "file_type": file_type, "chunks": shard}],
                batch_size=batch_size,
                tasks_limit=tasks_limit,
                max_retries=max_retries,
            )
            done = self.wait_task(task["task_id"], timeout=timeout)
            results.append(done)
            print(f"  [{name}] {done.get('status')} result={done.get('result')} err={done.get('error')}", flush=True)
        return results


def main() -> None:
    kb = KBClient()
    print(json.dumps(kb.list_kbs(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
