from pydantic import BaseModel


class GRPCConfig(BaseModel):
    port:str = "[::]:50052"