"""FastAPI application entry point for Stanford-AI OS."""

from fastapi import FastAPI

from stanford_ai_os.api.task_execution import router as task_execution_router
from stanford_ai_os.api.task_execution_history import router as task_execution_history_router
from stanford_ai_os.api.tasks import router as tasks_router
from stanford_ai_os.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name)

app.include_router(tasks_router)
app.include_router(task_execution_router)
app.include_router(task_execution_history_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Report that the application process is running."""

    return {
        "status": "healthy",
        "app": settings.app_name,
        "environment": settings.environment,
    }
