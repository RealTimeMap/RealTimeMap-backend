from pydantic import BaseModel, RedisDsn


class RedisConfig(BaseModel):
    prefix: str = "realtime-map-cache"
    url: RedisDsn = ""
    max_connections: int = 50
    socket_timeout: int = 5
    socket_connect_timeout: int = 5
    socket_keepalive: bool = True
    health_check_interval: int = 30
    decode_responses: bool = False
    encoding: str = "utf-8"