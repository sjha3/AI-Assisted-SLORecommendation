from pydantic import BaseModel
from pydantic import BaseModel, ConfigDict
class TaskRequest(BaseModel):
    task: str


class TaskResponse(BaseModel):
    task: str
    result: str