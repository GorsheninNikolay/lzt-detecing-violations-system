import secrets

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
