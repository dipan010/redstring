"""Shared Google Cloud clients (created lazily, reused across requests)."""

from functools import lru_cache

import firebase_admin
from google import genai
from google.cloud import firestore, storage

from .config import get_settings


@lru_cache
def db() -> firestore.AsyncClient:
    return firestore.AsyncClient(project=get_settings().google_cloud_project)


@lru_cache
def gemini() -> genai.Client:
    s = get_settings()
    return genai.Client(vertexai=True, project=s.google_cloud_project, location=s.gemini_location)


@lru_cache
def firebase_app() -> firebase_admin.App:
    return firebase_admin.initialize_app(options={"projectId": get_settings().google_cloud_project})


@lru_cache
def bucket() -> storage.Bucket:
    s = get_settings()
    return storage.Client(project=s.google_cloud_project).bucket(s.storage_bucket)
