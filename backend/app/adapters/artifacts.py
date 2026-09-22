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
        try:
            attempted = True
            self.client.put_object(Bucket=self.bucket, Key=key, Body=payload)
            head = self.client.head_object(Bucket=self.bucket, Key=key)
            body = self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
            if head["ContentLength"] != len(payload) or body != payload:
                failed = True
        except Exception:
            failed = True
        finally:
            if attempted:
                try:
                    self.client.delete_object(Bucket=self.bucket, Key=key)
                except Exception:
                    failed = True
                else:
                    try:
                        self.client.head_object(Bucket=self.bucket, Key=key)
                        failed = True
                    except Exception as exc:
                        # S3 reports a deleted object as a 404 ClientError.
                        if getattr(exc, "response", {}).get("ResponseMetadata", {}).get("HTTPStatusCode") != 404:
                            failed = True
        if failed:
            raise ArtifactGateError("artifact_gate_failed")
