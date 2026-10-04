"""Optional S3 upload (only runs if TS_S3_BUCKET is set)."""
from __future__ import annotations

from pathlib import Path

from ..config import settings
from . import logging as log


def upload_dir(local_dir: Path) -> str | None:
    """Upload the report folder to s3://<bucket>/<prefix><foldername>/. Returns s3 URI."""
    if not settings.s3_bucket:
        return None
    try:
        import boto3
        from botocore.config import Config
    except ImportError:
        log.warn("boto3 not installed — skipping S3 upload (pip install 'tendem-scraper[cloud]')")
        return None

    s3 = boto3.client("s3", region_name=settings.aws_region,
                      config=Config(retries={"max_attempts": 5, "mode": "standard"}))
    prefix = settings.s3_prefix.rstrip("/") + "/" + local_dir.name + "/"

    uploaded = 0
    for f in local_dir.rglob("*"):
        if not f.is_file():
            continue
        key = prefix + str(f.relative_to(local_dir)).replace("\\", "/")
        s3.upload_file(str(f), settings.s3_bucket, key)
        uploaded += 1

    uri = f"s3://{settings.s3_bucket}/{prefix}"
    log.info(f"Uploaded {uploaded} files → {uri}")
    return uri