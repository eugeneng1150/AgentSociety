"""
Mortality-Cooperation Experiment

Research question: What factors enable mortal LLM agents to sustain cooperation
in a fragile simulated society?

15-day simulation with:
- 30 agents (10 high / 10 medium / 10 low cooperation tendency)
- Daily cooperation dilemma (Public Goods Game)
- Day 5: famine shock (-30 resources)
- Day 10: aid drop (+50 resources)
- Mortality: agents die when resources < 20
"""

import asyncio
import os

from agentsociety.cityagent import (
    MobilityBlock,
    MobilityBlockParams,
    SocialBlock,
    SocialBlockParams,
    EconomyBlock,
    EconomyBlockParams,
    OtherBlock,
    OtherBlockParams,
    default,
)
from agentsociety.cityagent.memory_config import (
    memory_config_societyagent,
)
from agentsociety.configs import (
    AgentsConfig,
    Config,
    EnvConfig,
    ExpConfig,
    LLMConfig,
    MapConfig,
)
from agentsociety.configs.agent import AgentConfig
from agentsociety.configs.exp import (
    AgentFilterConfig,
    WorkflowStepConfig,
    WorkflowType,
)
from agentsociety.environment import EnvironmentConfig
from agentsociety.llm import LLMProviderType
from agentsociety.simulation import AgentSociety
from agentsociety.storage import DatabaseConfig

from agent import MortalSocietyAgent
from workflow import (
    mortality_check,
    resource_scarcity_shock,
    resource_abundance_event,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MAP_FILE = os.environ.get(
    "AGENTSOCIETY_MAP_FILE",
    "<MAP-FILE-PATH>",
)
LLM_API_KEY = os.environ.get("AGENTSOCIETY_LLM_API_KEY", "<YOUR-API-KEY>")
LLM_API_BASE = os.environ.get("AGENTSOCIETY_LLM_API_BASE", "https://api.openai.com/v1")
LLM_MODEL = os.environ.get("AGENTSOCIETY_LLM_MODEL", "gpt-4o-mini")

PROFILES_FILE = os.path.join(os.path.dirname(__file__), "profiles.json")

# ---------------------------------------------------------------------------
# Build the 15-day workflow
# ---------------------------------------------------------------------------


def build_workflow() -> list[WorkflowStepConfig]:
    steps = []

    for day in range(1, 16):
        # Simulate one day
        steps.append(
            WorkflowStepConfig(
                type=WorkflowType.RUN,
                days=1,
                description=f"Day {day}: agents live, work, socialize, and face cooperation dilemma",
            )
        )

        # End-of-day: distribute payout and kill agents below threshold
        steps.append(
            WorkflowStepConfig(
                type=WorkflowType.FUNCTION,
                func=mortality_check,
                description=f"Day {day}: mortality check and cooperation payout",
            )
        )

        # Save cooperation scores for analysis
        steps.append(
            WorkflowStepConfig(
                type=WorkflowType.SAVE_CONTEXT,
                target_agent=AgentFilterConfig(
                    agent_class=(MortalSocietyAgent,),
                ),
                key="cooperation_score",
                save_as=f"cooperation_score_day{day}",
            )
        )
        steps.append(
            WorkflowStepConfig(
                type=WorkflowType.SAVE_CONTEXT,
                target_agent=AgentFilterConfig(
                    agent_class=(MortalSocietyAgent,),
                ),
                key="resource_pool",
                save_as=f"resource_pool_day{day}",
            )
        )

        # Day 5: famine shock
        if day == 5:
            steps.append(
                WorkflowStepConfig(
                    type=WorkflowType.FUNCTION,
                    func=resource_scarcity_shock,
                    description="FAMINE: severe resource scarcity hits the community",
                )
            )

        # Day 10: aid drop
        if day == 10:
            steps.append(
                WorkflowStepConfig(
                    type=WorkflowType.FUNCTION,
                    func=resource_abundance_event,
                    description="AID DROP: emergency resources distributed",
                )
            )

    return steps


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

config = Config(
    llm=[
        LLMConfig(
            provider=LLMProviderType.OpenAI,
            base_url=LLM_API_BASE,
            api_key=LLM_API_KEY,
            model=LLM_MODEL,
            concurrency=50,
            timeout=120,
        )
    ],
    env=EnvConfig(
        db=DatabaseConfig(
            enabled=True,
            db_type="sqlite",
            pg_dsn=None,
        ),
    ),
    map=MapConfig(
        file_path=MAP_FILE,
    ),
    agents=AgentsConfig(
        citizens=[
            AgentConfig(
                agent_class=MortalSocietyAgent,
                memory_from_file=PROFILES_FILE,
                memory_config_func=memory_config_societyagent,
                blocks={
                    MobilityBlock: MobilityBlockParams(),
                    SocialBlock: SocialBlockParams(),
                    EconomyBlock: EconomyBlockParams(),
                    OtherBlock: OtherBlockParams(),
                },
            ),
        ],
    ),  # type: ignore
    exp=ExpConfig(
        name="mortality_cooperation",
        workflow=build_workflow(),
        environment=EnvironmentConfig(
            start_tick=6 * 60 * 60,
        ),
    ),
)
config = default(config)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main():
    print("=" * 60)
    print("Mortality-Cooperation Experiment")
    print("30 agents | 15 days | Famine day 5 | Aid drop day 10")
    print("=" * 60)

    agentsociety = AgentSociety.create(config)
    try:
        await agentsociety.init()
        await agentsociety.run()
    finally:
        await agentsociety.close()

    print("=" * 60)
    print("Experiment complete. Check the SQLite database for results.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
