import asyncio
import logging
import os
from typing import Sequence
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from Orchestration import team_agents
from model.task_model import TaskRequest, TaskResponse

if not logging.getLogger().handlers:
    configured_level = os.getenv("AGENT_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, configured_level, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

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
            content = getattr(item, "content", None)
            if isinstance(content, str) and content.strip():
                final_result = content

    if not final_result:
        return "No result returned."

    return final_result.replace("TERMINATE", "").strip()


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

