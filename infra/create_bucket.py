from app.adapters.artifacts import ArtifactStore
from app.config import Config


store = ArtifactStore(Config.from_env())
try:
    store.client.head_bucket(Bucket=store.bucket)
except Exception:
    store.client.create_bucket(Bucket=store.bucket)
