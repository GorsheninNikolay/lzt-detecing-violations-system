import subprocess

import boto3

from app.config import Config


subprocess.run(["python", "-m", "alembic", "upgrade", "head"], check=True)
config = Config.from_env()
client = boto3.client("s3", endpoint_url=config.s3_endpoint,
                      aws_access_key_id=config.s3_access_key,
                      aws_secret_access_key=config.s3_secret_key,
                      region_name=config.s3_region)
if config.s3_bucket not in [bucket["Name"] for bucket in client.list_buckets()["Buckets"]]:
    client.create_bucket(Bucket=config.s3_bucket)
