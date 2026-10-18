"""Hands claims to the agent pipeline through Cloud Tasks.

The task calls back into this Cloud Run service (/internal/run-pipeline), so the pipeline runs
inside a request: CPU is billed only while a claim is processing, the service can scale to zero,
and Cloud Tasks retries failed runs. Without TASKS_QUEUE configured (local dev), it falls back to
running in-process.
"""

import asyncio
import json
import logging

from fastapi.concurrency import run_in_threadpool
from google.auth.transport import requests as google_requests
from google.cloud import tasks_v2
from google.oauth2 import id_token
from google.protobuf import duration_pb2

from .config import get_settings
from .pipeline import run_pipeline

log = logging.getLogger(__name__)
_client: tasks_v2.CloudTasksAsyncClient | None = None
_local: set[asyncio.Task] = set()


def _tasks() -> tasks_v2.CloudTasksAsyncClient:
    global _client
    if _client is None:
        _client = tasks_v2.CloudTasksAsyncClient()
    return _client


async def dispatch(claim_id: str) -> None:
    s = get_settings()
    if not s.tasks_queue:
        t = asyncio.create_task(run_pipeline(claim_id))  # local dev only
        _local.add(t)
        t.add_done_callback(_local.discard)
        return
    parent = _tasks().queue_path(s.google_cloud_project, s.google_cloud_location, s.tasks_queue)
    task = tasks_v2.Task(
        http_request=tasks_v2.HttpRequest(
            http_method=tasks_v2.HttpMethod.POST,
            url=f"{s.service_url}/internal/run-pipeline",
            headers={"Content-Type": "application/json"},
            body=json.dumps({"claimId": claim_id}).encode(),
            oidc_token=tasks_v2.OidcToken(service_account_email=s.tasks_invoker_sa, audience=s.service_url),
        ),
        dispatch_deadline=duration_pb2.Duration(seconds=600),
    )
    await _tasks().create_task(parent=parent, task=task)


async def verify_task_caller(authorization: str) -> None:
    """Only Cloud Tasks (signing as our service account) may trigger a pipeline run."""
    s = get_settings()
    if not authorization.startswith("Bearer "):
        raise PermissionError("missing token")
    claims = await run_in_threadpool(
        id_token.verify_oauth2_token, authorization[7:], google_requests.Request(), s.service_url
    )
    if claims.get("email") != s.tasks_invoker_sa or not claims.get("email_verified"):
        raise PermissionError("unexpected caller")
