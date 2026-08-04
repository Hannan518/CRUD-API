from fastapi import Request
from fastapi.responses import JSONResponse


class TaskError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message


def task_error_handler(request: Request, exc: TaskError):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.message})
