import grpc.aio

from core.config import conf
from database.redis.helper import redis_helper
from integrations.kafka import kafka_producer
from transport.grpc.generated import user_admin_service_pb2_grpc, user_service_pb2_grpc
from transport.grpc.service.user_admin_service import UserAdminService
from transport.grpc.service.user_service import UserService


async def create_grpc_server():
    # Redis и Kafka нужны RBAC: кэш прав и оповещение об изменении каталога.
    # Оба опциональны — без них сервер работает, просто без кэша и событий.
    await redis_helper.connect()
    await kafka_producer.start()

    server = grpc.aio.server()
    user_service_pb2_grpc.add_UserServiceServicer_to_server(UserService(), server)
    user_admin_service_pb2_grpc.add_UserAdminServiceServicer_to_server(
        UserAdminService(), server
    )
    server.add_insecure_port(conf.grpc.port)
    await server.start()
    await server.wait_for_termination()
