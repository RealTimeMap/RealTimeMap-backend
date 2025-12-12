import grpc.aio

from core.config import conf
from transport.grpc.generated import user_service_pb2_grpc
from transport.grpc.service.user_service import UserService


async def create_grpc_server():
    server = grpc.aio.server()
    user_service_pb2_grpc.add_UserServiceServicer_to_server(UserService(), server)
    server.add_insecure_port(conf.grpc.port)
    await server.start()
    await server.wait_for_termination()
