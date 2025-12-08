"""Storage services for object and relational data."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import boto3
from botocore.client import BaseClient
from botocore.exceptions import ClientError, NoCredentialsError

from app.core.config import get_settings
from app.core.database import init_db
from app.repositories import AuditRepository, LLMResponseRepository


class ObjectStoreClient:
    """Client for object storage (S3-compatible or local file system)."""

    def __init__(self) -> None:
        settings = get_settings().storage
        self._use_s3 = settings.use_s3
        self._root = Path(settings.local_root)
        self._root.mkdir(parents=True, exist_ok=True)
        
        self._s3_client: BaseClient | None = None
        if self._use_s3:
            try:
                self._s3_client = self._create_s3_client(settings)
                # Ensure bucket exists
                self._ensure_bucket_exists(settings.s3_bucket)
            except Exception as e:
                import structlog
                logger = structlog.get_logger(__name__)
                logger.warning(
                    "s3_init_failed",
                    error=str(e),
                    message="S3 initialization failed, falling back to local filesystem"
                )
                self._use_s3 = False
                self._s3_client = None

    def _create_s3_client(self, settings) -> BaseClient:
        """Create and configure S3 client."""
        config = {
            "endpoint_url": settings.s3_endpoint,
        }
        
        # Add credentials if provided
        if settings.s3_access_key_id and settings.s3_secret_access_key:
            config["aws_access_key_id"] = settings.s3_access_key_id
            config["aws_secret_access_key"] = settings.s3_secret_access_key
        
        # Add region if provided (required for AWS S3, optional for MinIO)
        if settings.s3_region:
            config["region_name"] = settings.s3_region
        
        # For MinIO and other S3-compatible services, we need to disable SSL verification
        # if using HTTP (localhost)
        if settings.s3_endpoint.startswith("http://"):
            from botocore.config import Config
            config["config"] = Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"}
            )
        
        return boto3.client("s3", **config)

    def _ensure_bucket_exists(self, bucket_name: str) -> None:
        """Ensure the S3 bucket exists, create it if it doesn't."""
        if not self._s3_client:
            return
        
        try:
            self._s3_client.head_bucket(Bucket=bucket_name)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "404":
                # Bucket doesn't exist, create it
                try:
                    if self._s3_client._client_config.region_name:
                        # AWS S3 requires region
                        self._s3_client.create_bucket(
                            Bucket=bucket_name,
                            CreateBucketConfiguration={
                                "LocationConstraint": self._s3_client._client_config.region_name
                            }
                        )
                    else:
                        # MinIO and other S3-compatible services
                        self._s3_client.create_bucket(Bucket=bucket_name)
                except ClientError as create_error:
                    import structlog
                    logger = structlog.get_logger(__name__)
                    logger.error(
                        "s3_bucket_creation_failed",
                        error=str(create_error),
                        bucket=bucket_name
                    )
                    raise

    def persist(self, key: str, payload: Dict[str, Any]) -> str:
        """Persist a JSON payload to object storage.

        Args:
            key: Storage key/identifier
            payload: Data to persist

        Returns:
            Path or S3 key to the stored file
        """
        if self._use_s3 and self._s3_client:
            return self._persist_to_s3(key, payload)
        else:
            return self._persist_to_local(key, payload)

    def _persist_to_s3(self, key: str, payload: Dict[str, Any]) -> str:
        """Persist data to S3-compatible storage."""
        settings = get_settings().storage
        s3_key = f"{key}.json"
        
        try:
            self._s3_client.put_object(
                Bucket=settings.s3_bucket,
                Key=s3_key,
                Body=json.dumps(payload, indent=2).encode("utf-8"),
                ContentType="application/json"
            )
            return f"s3://{settings.s3_bucket}/{s3_key}"
        except (ClientError, NoCredentialsError) as e:
            import structlog
            logger = structlog.get_logger(__name__)
            logger.error(
                "s3_persist_failed",
                error=str(e),
                key=s3_key,
                message="Falling back to local filesystem"
            )
            # Fallback to local storage
            return self._persist_to_local(key, payload)

    def _persist_to_local(self, key: str, payload: Dict[str, Any]) -> str:
        """Persist data to local filesystem."""
        target = self._root / f"{key}.json"
        target.write_text(json.dumps(payload, indent=2))
        return str(target)


class RelationalStore:
    """Relational database store using repository pattern."""

    def __init__(self) -> None:
        # Initialize database tables on first use
        # Handle connection errors gracefully - database may not be available at startup
        try:
            init_db()
        except Exception as e:
            import structlog
            logger = structlog.get_logger(__name__)
            logger.warning("database.init_failed", error=str(e), message="Database initialization failed, will retry on first use")
        self._audit_repo = AuditRepository()
        self._llm_response_repo = LLMResponseRepository()

    def persist_event(self, job_id: str, payload: Dict[str, Any]) -> None:
        """Persist an audit event using repository.

        Args:
            job_id: Job identifier
            payload: Event payload data
        """
        try:
            self._audit_repo.create(job_id=job_id, payload=payload)
        finally:
            self._audit_repo.close()

    def get_event(self, job_id: str) -> Dict[str, Any] | None:
        """Retrieve an audit event by job_id.

        Args:
            job_id: Job identifier

        Returns:
            Event dictionary if found, None otherwise
        """
        try:
            event = self._audit_repo.get_by_job_id(job_id)
            if event:
                return event.to_dict()
            return None
        finally:
            self._audit_repo.close()

    def get_events(
        self, limit: int = 100, offset: int = 0
    ) -> list[Dict[str, Any]]:
        """Retrieve multiple audit events.

        Args:
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of audit event dictionaries
        """
        try:
            return self._audit_repo.get_all(limit=limit, offset=offset)
        finally:
            self._audit_repo.close()

    def persist_llm_response(
        self,
        request_id: str,
        provider: str,
        prompt: str,
        raw_response: str,
        latency_ms: int,
        total_tokens: int,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        raw_metadata: Dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """Persist an LLM response to the database.

        Args:
            request_id: Request ID to group responses from the same request
            provider: LLM provider/adapter ID (e.g., 'openai', 'gemini')
            prompt: The prompt sent to the LLM
            raw_response: Raw response text from the LLM
            latency_ms: Response latency in milliseconds
            total_tokens: Total tokens used
            prompt_tokens: Number of tokens in the prompt (optional)
            completion_tokens: Number of tokens in the completion (optional)
            raw_metadata: Additional raw metadata from the API response (optional)
            error: Error message if the request failed (optional)
        """
        try:
            self._llm_response_repo.create(
                request_id=request_id,
                provider=provider,
                prompt=prompt,
                raw_response=raw_response,
                latency_ms=latency_ms,
                total_tokens=total_tokens,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                raw_metadata=raw_metadata,
                error=error,
            )
        finally:
            self._llm_response_repo.close()

    def get_llm_responses(
        self,
        request_id: str | None = None,
        provider: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Dict[str, Any]]:
        """Retrieve LLM responses from the database.

        Args:
            request_id: Optional filter by request ID
            provider: Optional filter by provider
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            List of LLM response dictionaries
        """
        try:
            return self._llm_response_repo.get_all(
                request_id=request_id, provider=provider, limit=limit, offset=offset
            )
        finally:
            self._llm_response_repo.close()
