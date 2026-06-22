"""Stockage contrats de prêt employeur."""


from app.core.database import supabase

BUCKET_NAME = "employee_loan_contracts"


class EmployeeLoanStorage:
    def __init__(self, bucket: str = BUCKET_NAME):
        self._bucket = bucket

    def upload(self, path: str, content: bytes, content_type: str = "application/pdf") -> str:
        supabase.storage.from_(self._bucket).upload(
            path,
            content,
            file_options={"content-type": content_type, "upsert": "true"},
        )
        return path

    def create_signed_download_url(self, path: str, expiry_seconds: int = 3600) -> str:
        r = supabase.storage.from_(self._bucket).create_signed_url(
            path, expiry_seconds, options={"download": True}
        )
        return r["signedURL"]


employee_loan_storage = EmployeeLoanStorage()
