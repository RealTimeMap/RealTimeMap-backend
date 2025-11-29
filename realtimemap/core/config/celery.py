from pydantic import BaseModel, Field


class CeleryConfig(BaseModel):
    broker: str
    backend: str

    # Connection retry settings
    broker_connection_retry: bool = True
    broker_connection_retry_on_startup: bool = True
    broker_connection_max_retries: int = Field(default=10, ge=1)

    # Pool settings
    broker_pool_limit: int = Field(default=50, ge=1)

    # Timeouts
    broker_connection_timeout: int = Field(default=5, ge=1)
    result_expires: int = Field(default=3600, ge=60)
