import os
import boto3
from botocore.client import Config

class ArtifactStorage:
    def __init__(self):
        self.endpoint = os.environ.get("MINIO_ENDPOINT", "http://localhost:9000")
        self.access_key = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
        self.secret_key = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
        self.bucket_name = "atlas-artifacts"
        self._s3 = None
        self._bucket_checked = False

    @property
    def s3(self):
        if self._s3 is None:
            self._s3 = boto3.client(
                "s3",
                endpoint_url=self.endpoint,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                config=Config(
                    signature_version="s3v4",
                    connect_timeout=2,
                    read_timeout=2,
                    retries={"max_attempts": 1}
                )
            )
        return self._s3

    def _ensure_bucket(self):
        if self._bucket_checked:
            return
        try:
            self.s3.head_bucket(Bucket=self.bucket_name)
            self._bucket_checked = True
        except Exception:
            try:
                self.s3.create_bucket(Bucket=self.bucket_name)
                self._bucket_checked = True
            except Exception:
                pass

    def save_artifact(self, artifact_id: str, file_path: str):
        self._ensure_bucket()
        self.s3.upload_file(file_path, self.bucket_name, f"{artifact_id}.pkl")
        
    def load_artifact(self, artifact_id: str, download_path: str):
        self._ensure_bucket()
        self.s3.download_file(self.bucket_name, f"{artifact_id}.pkl", download_path)

_storage = ArtifactStorage()
