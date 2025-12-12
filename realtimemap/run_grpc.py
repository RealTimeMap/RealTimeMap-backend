import asyncio

from transport.grpc.server import create_grpc_server

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(create_grpc_server())
