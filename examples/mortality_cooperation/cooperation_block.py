"""
CooperationBlock — daily Public Goods Game dilemma.

Each simulated day, the agent faces a cooperation dilemma:
  - COOPERATE: pay cooperation_cost resources into the shared pool
  - DEFECT: keep your resources
  - Either way: pay daily_maintenance resources
"""

from typing import Optional

import json_repair

from agentsociety.agent import Block, AgentToolbox
from agentsociety.agent.block import BlockParams
from agentsociety.memory import Memory
from agentsociety.logger import get_logger

COOPERATION_PROMPT = """You are {name}, age {age}.
Personality: {personality}
Your cooperation tendency: {cooperation_tendency}
Your current resources: {resource_pool:.1f} (you die if resources fall below {death_threshold:.1f})
Your cumulative cooperation score: {cooperation_score:.1f}
Days survived: {survival_rounds}

COMMUNITY SITUATION:
{society_situation}

TODAY'S COOPERATION DILEMMA:
The community maintains a shared survival fund.
- COOPERATE: Contribute {cooperation_cost:.0f} resources. The total contributions are multiplied by {cooperation_multiplier:.1f} and split equally among all cooperators tomorrow.
- DEFECT: Contribute nothing. You keep your resources but receive no payout from the shared fund.
- Either way, you lose {daily_maintenance:.0f} resources per day for basic survival costs.

Think about your personality, your resources, the community situation, and whether cooperation will help you survive.

Respond in JSON:
{{"decision": "cooperate" or "defect", "reasoning": "one sentence explaining your choice"}}"""


class CooperationBlock(Block):
    ParamsType = BlockParams
    name = "CooperationBlock"
    description = "Daily cooperation dilemma for community survival"

    def __init__(
        self,
        toolbox: AgentToolbox,
        agent_memory: Optional[Memory] = None,
        block_params: Optional[BlockParams] = None,
        cooperation_cost: float = 15.0,
        daily_maintenance: float = 5.0,
        cooperation_multiplier: float = 2.5,
        death_threshold: float = 20.0,
    ):
        super().__init__(
            toolbox=toolbox,
            agent_memory=agent_memory,
            block_params=block_params,
        )
        self.cooperation_cost = cooperation_cost
        self.daily_maintenance = daily_maintenance
        self.cooperation_multiplier = cooperation_multiplier
        self.death_threshold = death_threshold

    async def forward_daily(self):
        """Called once per simulated day from MortalSocietyAgent.forward()."""
        logger = get_logger()
        try:
            name = await self.memory.status.get("name")
            age = await self.memory.status.get("age", 30)
            personality = await self.memory.status.get("personality", "pragmatic")
            cooperation_tendency = await self.memory.status.get(
                "cooperation_tendency", "medium"
            )
            resource_pool = await self.memory.status.get("resource_pool", 100.0)
            cooperation_score = await self.memory.status.get("cooperation_score", 0.0)
            survival_rounds = await self.memory.status.get("survival_rounds", 0)

            other_info = ""
            try:
                other_info = self.environment.sense("other_information") or ""
            except Exception:
                pass

            prompt = COOPERATION_PROMPT.format(
                name=name,
                age=age,
                personality=personality,
                cooperation_tendency=cooperation_tendency,
                resource_pool=resource_pool,
                cooperation_score=cooperation_score,
                survival_rounds=survival_rounds,
                society_situation=other_info or "The community is stable for now.",
                cooperation_cost=self.cooperation_cost,
                cooperation_multiplier=self.cooperation_multiplier,
                daily_maintenance=self.daily_maintenance,
                death_threshold=self.death_threshold,
            )

            response = await self.llm.atext_request(
                dialog=[
                    {
                        "role": "system",
                        "content": "You are roleplaying as a citizen making a daily survival decision. Respond only with the requested JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )

            parsed = json_repair.loads(response)
            decision = str(parsed.get("decision", "defect")).lower().strip()
            reasoning = str(parsed.get("reasoning", ""))

            if decision == "cooperate":
                resource_pool = max(0.0, resource_pool - self.cooperation_cost)
                cooperation_score += 1.0
                await self.memory.status.update("cooperation_score", cooperation_score)
                await self.memory.status.update("cooperated_this_round", True)
            else:
                decision = "defect"
                await self.memory.status.update("cooperated_this_round", False)

            resource_pool = max(0.0, resource_pool - self.daily_maintenance)
            await self.memory.status.update("resource_pool", resource_pool)

            await self.memory.stream.add(
                topic="cooperation",
                description=(
                    f"Day {survival_rounds + 1} cooperation decision: {decision}. "
                    f"Reasoning: {reasoning}. "
                    f"Resources remaining: {resource_pool:.1f}"
                ),
            )

            logger.info(
                f"[{name}] Decision: {decision} | Resources: {resource_pool:.1f} | "
                f"Score: {cooperation_score:.1f} | Reason: {reasoning[:80]}"
            )

        except Exception as e:
            logger.warning(f"CooperationBlock error: {e}")
            resource_pool = await self.memory.status.get("resource_pool", 100.0)
            resource_pool = max(0.0, resource_pool - self.daily_maintenance)
            await self.memory.status.update("resource_pool", resource_pool)
            await self.memory.status.update("cooperated_this_round", False)

    async def forward(self, agent_context):
        """Required by Block ABC. Not called via dispatcher."""
        from agentsociety.cityagent.sharing_params import SocietyAgentBlockOutput

        return SocietyAgentBlockOutput(
            success=True,
            evaluation="Cooperation block — use forward_daily() instead",
            consumed_time=0,
            node_id=None,
        )
