from pydantic import BaseModel, Field


class ClientErrorIn(BaseModel):
    ecran: str = Field(default="", max_length=80)
    action: str = Field(default="", max_length=80)
    message: str = Field(default="", max_length=2000)
    pile: str = Field(default="", max_length=8000)
