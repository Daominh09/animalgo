import boto3

from app.config import settings

# Owner: Person A (upload flow) / Person D (bucket provisioning)
# R2 is S3-compatible — no special SDK or proxy needed, just point boto3 at the R2 endpoint.

s3 = boto3.client(
    "s3",
    endpoint_url=settings.r2_endpoint_url,
    aws_access_key_id=settings.r2_access_key_id,
    aws_secret_access_key=settings.r2_secret_access_key,
    region_name="auto",
)


def generate_presigned_upload_url(object_key: str, content_type: str = "image/jpeg") -> str:
    return s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.r2_bucket_name, "Key": object_key, "ContentType": content_type},
        ExpiresIn=300,
    )


def public_object_url(object_key: str) -> str:
    return f"{settings.r2_endpoint_url}/{settings.r2_bucket_name}/{object_key}"


def upload_bytes(
    object_key: str, data: bytes, content_type: str = "image/jpeg"
) -> str:
    """Upload raw bytes straight from the backend (not via a presigned URL)."""
    s3.put_object(
        Bucket=settings.r2_bucket_name,
        Key=object_key,
        Body=data,
        ContentType=content_type,
    )
    return public_object_url(object_key)
