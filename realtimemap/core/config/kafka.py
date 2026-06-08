from pydantic import BaseModel, Field


class KafkaConfig(BaseModel):
    bootstrap_servers: str = "kafka:9093"
    client_id: str = "realtimemap-auth"
    user_registered_topic: str = "user.registered"
    request_timeout_ms: int = Field(default=10_000, ge=1_000)
    retry_backoff_ms: int = Field(default=100, ge=10)
    enabled: bool = True
