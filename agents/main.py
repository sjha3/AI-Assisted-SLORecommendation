import asyncio
import argparse
import logging
import os
from typing import Sequence
from DataAgent import data_agent, model_client
from AnalysisAgent import analysis_agent
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.teams import SelectorGroupChat
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
from autogen_agentchat.messages import AgentEvent, ChatMessage
from autogen_agentchat.ui import Console

if not logging.getLogger().handlers:
    configured_level = os.getenv("AGENT_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, configured_level, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

logger = logging.getLogger("agents.main")

agent_team = RoundRobinGroupChat([
    data_agent,
    analysis_agent,
])

planning_agent = AssistantAgent(
            "PlanningAgent",
            model_client=model_client,
            description="""
                An agent that plans tasks based on user requests.
                It should break down tasks and delegate them to appropriate agents.
                """,
            system_message=
                """
                    You are a planning agent. 
                    Your task is to break down user requests into smaller tasks and delegate them to appropriate agents.
                    Your team members are
                    - DataAgent: Gets SLIs/SLOs/Incident/Dependenygraph data of service APIs
                    - AnalysisAgent: Performs analysis on data provided by Data Agents and operations like impact analysis, recommend SLO etc.                   
                    - ResponseAgent: Responsible for responding to the user with the final response.
                    
                    You only plan and delegate tasks, you do not execute them.
                    
                    When assignning tasks to agents, use the following format:
                    1. <agent>: <task>
                    
                    Once a task is completed by another agent, delegate the response to the **ResponseAgent**
                    to format and send the final response to the user.
                """,
        )

response_agent = AssistantAgent(
            name="ResponseAgent",
            description="An agent that formats and sends the final response to the user.",
            model_client=model_client,
            system_message="""You are a response agent. 
            Your task is to format and send the final response to the user.
            Always end the conversation with 'TERMINATE'.
            
            Always end your response with 'TERMINATE' to indicate the conversation is complete.
            """,
        )

def selector_func(messages: Sequence[AgentEvent | ChatMessage]) -> str | None:
            if messages[-1].source != planning_agent.name:
                return planning_agent.name
            return None
        
text_mention_termination = TextMentionTermination("TERMINATE")
max_messages_termination = MaxMessageTermination(25)
termination = text_mention_termination | max_messages_termination
team_agents = SelectorGroupChat([planning_agent, data_agent,
                                  analysis_agent,
                                  response_agent],
                                 model_client=model_client, 
                                 selector_func=selector_func,
                                 termination_condition=termination,
                                 allow_repeated_speaker=True)

async def run_single_query(task: str) -> None:
    logger.info("conversation.start task=%s", task)
    while True:
        try:
            task = input("Please enter a task: ")
            print("Running task:", task)
            await Console(team_agents.run_stream(task = task))
            
        except Exception as e:
            print(f"Error occurred: {e}")
            task = input("Please enter a new task: ")



async def main():

    while True:
        task = input("Enter your query: ")
        if task.strip().lower() in {"exit", "quit"}:
            print("Exiting.")
            break

        await run_single_query(task)

if __name__ == "__main__":
    asyncio.run(main())