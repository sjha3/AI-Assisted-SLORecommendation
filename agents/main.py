import asyncio
import logging
import os
from typing import Sequence
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from model.task_model import TaskRequest, TaskResponse

def _configure_agent_logging() -> None:
    configured_level = os.getenv("AGENT_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, configured_level, logging.INFO)

    agents_logger = logging.getLogger("agents")
    if not agents_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
        )
        agents_logger.addHandler(handler)

    agents_logger.setLevel(level)
    agents_logger.propagate = False


_configure_agent_logging()

from Orchestration import team_agents

logger = logging.getLogger("agents.main")
app = FastAPI(title="SLO Agents API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

team_run_lock = asyncio.Lock()

async def run_single_query(task: str) -> str:
    logger.info("conversation.start task=%s", task)
    final_result = ""
    async with team_run_lock:
        async for item in team_agents.run_stream(task=task):
            source = getattr(item, "source", type(item).__name__)
            content = getattr(item, "content", None)
            if isinstance(content, str) and content.strip():
                compact_content = " ".join(content.split())[:240]
                logger.info("agent.event source=%s content=%s", source, compact_content)
                final_result = content
            else:
                logger.debug("agent.event source=%s type=%s", source, type(item).__name__)

    if not final_result:
        return "No result returned."

    cleaned_result = final_result.replace("TERMINATE", "").strip()
    logger.info("conversation.end")
    return cleaned_result


@app.post("/task/run", response_model=TaskResponse)
async def run_task(request: TaskRequest) -> TaskResponse:
    task = request.task.strip()
    if not task:
        raise HTTPException(status_code=400, detail="task must not be empty")

    try:
        result = await run_single_query(task)
        return TaskResponse(task=task, result=result)
    except Exception as ex:
        logger.exception("task.run.error task=%s error=%s", task, ex)
        raise HTTPException(status_code=500, detail="failed to run task") from ex

