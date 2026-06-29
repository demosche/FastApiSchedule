from datetime import datetime

from pydantic import BaseModel, PositiveInt


class Event(BaseModel):  model_config = ConfigDict(strict=True)