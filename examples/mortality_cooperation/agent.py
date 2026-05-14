"""
MortalSocietyAgent — extends SocietyAgent with mortality and cooperation mechanics.

Adds resource tracking, cooperation scoring, and mortality to the standard
SocietyAgent's economic/social/cognitive simulation.
"""

from typing import Optional

from agentsociety.agent import Block, AgentToolbox, MemoryAttribute
from agentsociety.cityagent.societyagent import SocietyAgent
from agentsociety.cityagent.sharing_params import SocietyAgentConfig
from agentsociety.memory import Memory
from agentsociety.logger import get_logger

from .cooperation_block import CooperationBlock


class MortalSocietyAgent(SocietyAgent):
    StatusAttributes = SocietyAgent.StatusAttributes + [
        MemoryAttribute(
            name="is_alive",
            type=bool,
            default_or_value=True,
            description="whether the agent is still alive",
        ),
        MemoryAttribute(
            name="cooperation_score",
            type=float,
            default_or_value=0.0,
            description="cumulative cooperation score",
        ),
        MemoryAttribute(
            name="survival_rounds",
            type=int,
            default_or_value=0,
            description="number of days survived",
        ),
        MemoryAttribute(
            name="resource_pool",
            type=float,
            default_or_value=100.0,
            description="agent's resource pool (dies below 20)",
        ),
        MemoryAttribute(
            name="cooperation_tendency",
            type=str,
            default_or_value="medium",
            description="cooperation tendency: low/medium/high",
        ),
        MemoryAttribute(
            name="cooperated_this_round",
            type=bool,
            default_or_value=False,
            description="whether agent cooperated in the current round",
        ),
    ]

    def __init__(
        self,
        id: int,
        name: str,
        toolbox: AgentToolbox,
        memory: Memory,
        agent_params: Optional[SocietyAgentConfig] = None,
        blocks: Optional[list[Block]] = None,
    ) -> None:
        super().__init__(
            id=id,
            name=name,
            toolbox=toolbox,
            memory=memory,
            agent_params=agent_params,
            blocks=blocks,
        )
        self.cooperation_block = CooperationBlock(
            toolbox=self._toolbox,
            agent_memory=self.memory,
        )
        self._last_cooperation_day = -1

    async def forward(self):
        is_alive = await self.memory.status.get("is_alive", True)
        if not is_alive:
            return

        day, _ = self.environment.get_datetime()
        if day != self._last_cooperation_day:
            self._last_cooperation_day = day
            survival_rounds = await self.memory.status.get("survival_rounds", 0)
            await self.memory.status.update("survival_rounds", survival_rounds + 1)
            await self.cooperation_block.forward_daily()
            get_logger().info(
                f"[Agent {self.id}] Cooperation dilemma completed for day {day}"
            )

        return await super().forward()

    async def reset(self):
        await super().reset()

    async def react_to_intervention(self, intervention_message: str):
        await super().react_to_intervention(intervention_message)
