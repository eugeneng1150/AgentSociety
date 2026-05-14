"""
Mortality-Cooperation Experiment — single run.

Research question: What factors enable mortal LLM agents to sustain cooperation
in a fragile simulated society?

This file provides build_config() for programmatic use (by run_experiments.py)
and a __main__ block for standalone single runs with default parameters.
"""

import asyncio
import functools
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
from agentsociety.cityagent.memory_config import memory_config_societyagent
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

from agent import MortalSocietyAgent, MortalAgentParams
from experiment_params import ExperimentParams
from profile_generator import generate_profiles, write_profiles
from workflow import (
    mortality_check,
    resource_scarcity_shock,
    resource_abundance_event,
)

# ---------------------------------------------------------------------------
# Environment defaults
# ---------------------------------------------------------------------------
MAP_FILE = os.environ.get("AGENTSOCIETY_MAP_FILE", "<MAP-FILE-PATH>")
LLM_API_KEY = os.environ.get("AGENTSOCIETY_LLM_API_KEY", "<YOUR-API-KEY>")
LLM_API_BASE = os.environ.get("AGENTSOCIETY_LLM_API_BASE", "https://api.openai.com/v1")
LLM_MODEL = os.environ.get("AGENTSOCIETY_LLM_MODEL", "gpt-4o-mini")


# ---------------------------------------------------------------------------
# Workflow builder
# ---------------------------------------------------------------------------
def build_workflow(params: ExperimentParams) -> list[WorkflowStepConfig]:
    steps = []

    for day in range(1, params.num_days + 1):
        steps.append(
            WorkflowStepConfig(
                type=WorkflowType.RUN,
                days=1,
                description=f"Day {day}",
            )
        )

        steps.append(
            WorkflowStepConfig(
                type=WorkflowType.FUNCTION,
                func=functools.partial(
                    mortality_check,
                    multiplier=params.cooperation_multiplier,
                    death_threshold=params.death_threshold,
                    cooperation_cost=params.cooperation_cost,
                    show_cooperation_rate=params.show_cooperation_rate,
                ),
                description=f"Day {day}: mortality check",
            )
        )

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

        if day == params.shock_day:
            steps.append(
                WorkflowStepConfig(
                    type=WorkflowType.FUNCTION,
                    func=functools.partial(
                        resource_scarcity_shock,
                        shock_amount=params.shock_amount,
                    ),
                    description="FAMINE shock",
                )
            )

        if day == params.aid_day:
            steps.append(
                WorkflowStepConfig(
                    type=WorkflowType.FUNCTION,
                    func=functools.partial(
                        resource_abundance_event,
                        aid_amount=params.aid_amount,
                    ),
                    description="AID DROP",
                )
            )

    return steps


# ---------------------------------------------------------------------------
# Config builder
# ---------------------------------------------------------------------------
def build_config(
    params: ExperimentParams,
    profiles_path: str,
    output_dir: str = "./results",
) -> Config:
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
                    memory_from_file=profiles_path,
                    memory_config_func=memory_config_societyagent,
                    agent_params=MortalAgentParams(
                        cooperation_cost=params.cooperation_cost,
                        daily_maintenance=params.daily_maintenance,
                        cooperation_multiplier=params.cooperation_multiplier,
                        death_threshold=params.death_threshold,
                    ),
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
            name=params.run_name,
            workflow=build_workflow(params),
            environment=EnvironmentConfig(
                start_tick=6 * 60 * 60,
            ),
        ),
    )
    return default(config)


# ---------------------------------------------------------------------------
# Standalone run
# ---------------------------------------------------------------------------
async def run_single(params: ExperimentParams, output_dir: str = "./results"):
    total = params.num_high + params.num_medium + params.num_low
    profiles = generate_profiles(
        params.num_high, params.num_medium, params.num_low, params.initial_resources
    )
    profiles_path = os.path.join(output_dir, f"profiles_{params.run_name}.json")
    write_profiles(profiles, profiles_path)

    config = build_config(params, profiles_path, output_dir)
    exp_id = str(config.exp.id)

    print(f"  Agents: {total} ({params.num_high}H/{params.num_medium}M/{params.num_low}L)")
    print(f"  Multiplier: {params.cooperation_multiplier}x | Threshold: {params.death_threshold}")
    print(f"  Shock: -{params.shock_amount} on day {params.shock_day} | Aid: +{params.aid_amount} on day {params.aid_day}")
    print(f"  Visibility: {params.show_cooperation_rate} | Days: {params.num_days}")

    agentsociety = AgentSociety.create(config)
    try:
        await agentsociety.init()
        await agentsociety.run()
    finally:
        await agentsociety.close()

    return exp_id


async def main():
    params = ExperimentParams()
    print("=" * 60)
    print(f"Mortality-Cooperation Experiment: {params.run_name}")
    print("=" * 60)

    exp_id = await run_single(params)

    print("=" * 60)
    print(f"Experiment complete. ID: {exp_id}")
    print("Check the SQLite database for results.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
