from pydantic import BaseModel, Field


class KafkaConfig(BaseModel):
    # Внутри docker-сети брокер слушает INTERNAL-листенер на 9092; 9093
    # анонсирован как localhost:9093 и доступен только с хоста (IDE, тесты).
    bootstrap_servers: str = "kafka:9092"
    client_id: str = "realtimemap-auth"

    # Топик называется по владельцу-издателю, а не по событию: в него едут все
    # события пользователя, а потребитель разбирает знакомые типы.
    # Согласован с pkg/transport/kafka/topic.UserEvents в Go-сервисах.
    user_events_topic: str = "user-service"

    # Топик social-service: оттуда приезжает profile.updated.
    # Согласован с pkg/transport/kafka/topic.SocialEvents.
    social_events_topic: str = "social-service.events"

    # Группа консьюмера. Своя на сервис: смещения не должны делиться с
    # другими потребителями того же топика.
    consumer_group_id: str = "auth-service"

    request_timeout_ms: int = Field(default=10_000, ge=1_000)
    retry_backoff_ms: int = Field(default=100, ge=10)
    enabled: bool = True

    # Консьюмер выключен по умолчанию: он нужен только там, где поднят
    # social-service. Продюсер от флага не зависит — письма и заведение
    # профиля ломать нельзя.
    consumer_enabled: bool = False
