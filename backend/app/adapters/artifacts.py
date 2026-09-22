import secrets
import hashlib
import uuid

import boto3
from botocore.config import Config as BotoConfig

from app.config import Config


class ArtifactGateError(RuntimeError):
    pass


class ArtifactStore:
    def __init__(self, config: Config):
        self.bucket = config.s3_bucket
        self.client = boto3.client(
            "s3", endpoint_url=config.s3_endpoint, aws_access_key_id=config.s3_access_key,
            aws_secret_access_key=config.s3_secret_key, region_name=config.s3_region,
            config=BotoConfig(s3={"addressing_style": "path"}, retries={"max_attempts": 1}),
        )

    def _verify(self, key: str, expected_digest: str, expected_size: int) -> None:
        try:
            head = self.client.head_object(Bucket=self.bucket, Key=key)
            body = self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
            if head["ContentLength"] != expected_size or len(body) != expected_size or hashlib.sha256(body).hexdigest() != expected_digest:
                raise ArtifactGateError("artifact_integrity_failed")
        except ArtifactGateError:
            raise
        except Exception:
            raise ArtifactGateError("artifact_integrity_failed") from None

    def upload_temporary(self, intent_id: uuid.UUID, payload: bytes, media_type: str) -> tuple[str, str, int]:
        digest = hashlib.sha256(payload).hexdigest()
        size = len(payload)
        temporary_key = f"tmp/{intent_id}"
        try:
            self.client.put_object(Bucket=self.bucket, Key=temporary_key, Body=payload,
                ContentType=media_type, Metadata={"publication_intent_id": str(intent_id)})
            self._verify(temporary_key, digest, size)
            return temporary_key, digest, size
        except ArtifactGateError:
            raise
        except Exception:
            raise ArtifactGateError("artifact_publication_failed") from None

    def publish_final(self, intent_id: uuid.UUID, payload: bytes, media_type: str, digest: str, size: int) -> str:
        final_key = f"sha256/{digest}"
        try:
            self._verify(f"tmp/{intent_id}", digest, size)
            try:
                self.client.put_object(Bucket=self.bucket, Key=final_key, Body=payload,
                    ContentType=media_type, Metadata={"publication_intent_id": str(intent_id)}, IfNoneMatch="*")
            except Exception as exc:
                status = getattr(exc, "response", {}).get("ResponseMetadata", {}).get("HTTPStatusCode")
                if status not in (409, 412):
                    raise
            self._verify(final_key, digest, size)
            return final_key
        except ArtifactGateError:
            raise
        except Exception:
            raise ArtifactGateError("artifact_publication_failed") from None

    def read_verified(self, key: str, digest: str, size: int) -> bytes:
        if key != f"sha256/{digest}":
            raise ArtifactGateError("artifact_integrity_failed")
        try:
            head = self.client.head_object(Bucket=self.bucket, Key=key)
            body = self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
            if head["ContentLength"] != size or len(body) != size or hashlib.sha256(body).hexdigest() != digest:
                raise ArtifactGateError("artifact_integrity_failed")
            return body
        except ArtifactGateError:
            raise
        except Exception:
            raise ArtifactGateError("artifact_integrity_failed") from None

    def probe(self) -> None:
        key = f"health/{secrets.token_hex(24)}"
        payload = secrets.token_bytes(32)
        attempted = False
        failed = False
        version_id = None
        put_completed = False
        try:
            attempted = True
            version_id = self.client.put_object(Bucket=self.bucket, Key=key, Body=payload).get("VersionId")
            put_completed = True
            head = self.client.head_object(Bucket=self.bucket, Key=key)
            body = self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
            if head["ContentLength"] != len(payload) or body != payload:
                failed = True
        except Exception:
            failed = True
        finally:
            if attempted:
                try:
                    self._clean_health_key(key, version_id, put_completed)
                except Exception:
                    failed = True
        if failed:
            raise ArtifactGateError("artifact_gate_failed")

    def _health_versions(self, key: str) -> list[dict]:
        return [
            item
            for page in self.client.get_paginator("list_object_versions").paginate(Bucket=self.bucket, Prefix=key)
            for kind in ("Versions", "DeleteMarkers")
            for item in page.get(kind, [])
            if item["Key"] == key
        ]

    def _clean_health_key(self, key: str, version_id: str | None, put_completed: bool) -> None:
        if not version_id or version_id == "null":
            self.client.delete_object(Bucket=self.bucket, Key=key)
        if version_id or not put_completed:
            for item in self._health_versions(key):
                if item["VersionId"] != "null":
                    self.client.delete_object(Bucket=self.bucket, Key=key, VersionId=item["VersionId"])
            if self._health_versions(key):
                raise ArtifactGateError("artifact_cleanup_failed")
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
        except Exception as exc:
            if getattr(exc, "response", {}).get("ResponseMetadata", {}).get("HTTPStatusCode") == 404:
                return
            raise
        raise ArtifactGateError("artifact_cleanup_failed")
