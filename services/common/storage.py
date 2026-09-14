from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

import boto3
from botocore.client import Config

from .config import get_settings


def _content_disposition(filename: str) -> str:
    """RFC 6266: a bare `filename="..."` is only well-defined for ASCII — putting
    raw UTF-8 (e.g. Korean) in it produces mojibake filenames on save.
    `filename*=UTF-8''<percent-encoded>` is the actual standard for non-ASCII
    names; the ASCII `filename=` stays as a fallback for clients that don't
    understand the extended form."""
    ascii_fallback = filename.encode("ascii", errors="ignore").decode("ascii").strip() or "download"
    encoded = quote(filename, safe="")
    return f'attachment; filename="{ascii_fallback}"; filename*=UTF-8\'\'{encoded}'


@lru_cache
def _client():
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=Config(signature_version="s3v4"),
    )


@lru_cache
def _public_client():
    """Client whose presigned URLs are signed for the endpoint a browser can reach."""
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_public_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=Config(signature_version="s3v4"),
    )


def ensure_bucket() -> None:
    settings = get_settings()
    s3 = _client()
    existing = {b["Name"] for b in s3.list_buckets().get("Buckets", [])}
    if settings.s3_bucket not in existing:
        s3.create_bucket(Bucket=settings.s3_bucket)


def upload_file(local_path: str | Path, key: str, content_type: str | None = None) -> str:
    settings = get_settings()
    extra = {"ContentType": content_type} if content_type else {}
    _client().upload_file(str(local_path), settings.s3_bucket, key, ExtraArgs=extra)
    return key


def download_file(key: str, local_path: str | Path) -> str:
    settings = get_settings()
    Path(local_path).parent.mkdir(parents=True, exist_ok=True)
    _client().download_file(settings.s3_bucket, key, str(local_path))
    return str(local_path)


def delete_object(key: str) -> None:
    settings = get_settings()
    _client().delete_object(Bucket=settings.s3_bucket, Key=key)


def object_exists(key: str) -> bool:
    settings = get_settings()
    try:
        _client().head_object(Bucket=settings.s3_bucket, Key=key)
        return True
    except Exception:
        return False


def presigned_get_url(
    key: str,
    expires: timedelta = timedelta(hours=1),
    download_filename: str | None = None,
) -> str:
    """`download_filename` sets response-content-disposition so the browser saves
    the file instead of opening an inline player — S3 (and MinIO) support this as
    a per-request override on GetObject, so no proxying through our own API is
    needed just to force a download."""
    settings = get_settings()
    params = {"Bucket": settings.s3_bucket, "Key": key}
    if download_filename:
        params["ResponseContentDisposition"] = _content_disposition(download_filename)
    return _public_client().generate_presigned_url(
        "get_object",
        Params=params,
        ExpiresIn=int(expires.total_seconds()),
    )


def get_object_stream(key: str, range_header: str | None = None) -> dict:
    """{body, content_length, content_type, content_range} for server-side
    proxying, with the client's Range header passed straight through to
    S3/MinIO's own byte-range support — needed for <audio> seeking to skip
    ahead without re-downloading everything before that point.

    Presigned URLs (above) need S3/MinIO itself to be reachable from the
    browser — fine when it's on its own public endpoint (S3_PUBLIC_ENDPOINT),
    but this deployment currently only exposes the API's own domain (via
    Caddy) publicly, not MinIO's. Streaming bytes through the API instead
    avoids needing a second public endpoint/DNS entry for object storage.

    `content_range` (e.g. "bytes 1000-1999/9326802") is only set when
    `range_header` was honored — the caller uses its presence to decide
    between a 200 (full body) and 206 (Partial Content) response.
    """
    settings = get_settings()
    kwargs = {"Bucket": settings.s3_bucket, "Key": key}
    if range_header:
        kwargs["Range"] = range_header
    obj = _client().get_object(**kwargs)
    return {
        "body": obj["Body"],
        "content_length": obj["ContentLength"],
        "content_type": obj.get("ContentType"),
        "content_range": obj.get("ContentRange"),
    }
