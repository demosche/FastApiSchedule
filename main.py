from datetime import datetime

from pydantic import BaseModel


class Event(BaseModel):  model_config = ConfigDict(strict=True)

class Req(BaseModel):
    model_config = ConfigDict(strict=True)
    type: int = 2
    id: int
    week: int = 0