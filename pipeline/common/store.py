"""Blob store: local cache dir by default, S3 when SMOULDER_BUCKET is set.

Keys mirror the S3 layout: raw/firms/<source>/<city>/<date>.csv, raw/wind/..., etc.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from pipeline.common.config import CACHE_DIR


def _bucket() -> str | None:
    return os.environ.get("SMOULDER_BUCKET")


def get(key: str) -> bytes | None:
    b = _bucket()
    if b:
        import boto3
        from botocore.exceptions import ClientError

        try:
            return boto3.client("s3").get_object(Bucket=b, Key=key)["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                return None
            raise
    p = CACHE_DIR / key
    return p.read_bytes() if p.exists() else None


def put(key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    b = _bucket()
    if b:
        import boto3

        boto3.client("s3").put_object(Bucket=b, Key=key, Body=data, ContentType=content_type)
        return
    p = CACHE_DIR / key
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)


def local_path(key: str) -> Path:
    return CACHE_DIR / key


def get_json(key: str, default=None):
    raw = get(key)
    return json.loads(raw) if raw is not None else default


def put_json(key: str, obj, indent: int | None = None) -> None:
    put(key, json.dumps(obj, indent=indent, ensure_ascii=False).encode("utf-8"), "application/json")
