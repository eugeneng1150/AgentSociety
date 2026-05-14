"""
Workflow functions for the mortality-cooperation experiment.

These are passed as `func` to WorkflowStepConfig(type=FUNCTION) and called
by the simulation engine with `async def func(engine)`.
"""

from agentsociety.logger import get_logger
from agentsociety.simulation import SimulationEngine

from .agent import MortalSocietyAgent


async def mortality_check(engine: SimulationEngine):
    """
    End-of-day processing:
    1. Gather cooperated_this_round flags from alive agents
    2. Distribute shared pool payout to cooperators
    3. Kill agents whose resource_pool < 20
    4. Broadcast death count and cooperation rate
    """
    logger = get_logger()

    alive_ids = await engine.filter(types=(MortalSocietyAgent,))
    if not alive_ids:
        logger.warning("No alive agents remain!")
        return

    cooperated_map = await engine.gather(
        "cooperated_this_round", target_agent_ids=alive_ids, flatten=True, keep_id=True
    )
    resource_map = await engine.gather(
        "resource_pool", target_agent_ids=alive_ids, flatten=True, keep_id=True
    )

    cooperator_ids = [
        aid for aid, cooperated in cooperated_map.items() if cooperated
    ]
    num_cooperators = len(cooperator_ids)
    num_alive = len(alive_ids)

    if num_cooperators > 0:
        total_contribution = num_cooperators * 15.0
        pool_payout = total_contribution * 2.5
        per_cooperator = pool_payout / num_cooperators

        for aid in cooperator_ids:
            current = resource_map.get(aid, 0.0)
            new_value = current + per_cooperator
            await engine.update([aid], "resource_pool", new_value)

        logger.info(
            f"Payout: {num_cooperators} cooperators each receive {per_cooperator:.1f} "
            f"(pool={pool_payout:.1f})"
        )

    resource_map_after = await engine.gather(
        "resource_pool", target_agent_ids=alive_ids, flatten=True, keep_id=True
    )
    dead_ids = [
        aid for aid, resources in resource_map_after.items() if resources < 20.0
    ]

    if dead_ids:
        for aid in dead_ids:
            await engine.update([aid], "is_alive", False)
        await engine.delete_agents(dead_ids)
        logger.info(f"DEATH: {len(dead_ids)} agents died. IDs: {dead_ids}")

    cooperation_rate = (num_cooperators / num_alive * 100) if num_alive > 0 else 0
    survivors = num_alive - len(dead_ids)

    situation = (
        f"Today: {num_cooperators}/{num_alive} agents cooperated "
        f"({cooperation_rate:.0f}% cooperation rate). "
        f"{len(dead_ids)} agents died from resource depletion. "
        f"{survivors} agents remain alive."
    )
    await engine.update_environment("other_information", situation)
    logger.info(f"Day summary: {situation}")


async def resource_scarcity_shock(engine: SimulationEngine):
    """Famine event: drain 30 resources from all alive agents."""
    logger = get_logger()
    alive_ids = await engine.filter(types=(MortalSocietyAgent,))
    if not alive_ids:
        return

    resource_map = await engine.gather(
        "resource_pool", target_agent_ids=alive_ids, flatten=True, keep_id=True
    )
    for aid, current in resource_map.items():
        new_value = max(0.0, current - 30.0)
        await engine.update([aid], "resource_pool", new_value)

    await engine.update_environment(
        "other_information",
        "CRISIS: A severe famine has struck the community! "
        "All citizens lost 30 resources. Cooperation is critical for survival.",
    )
    logger.info(f"FAMINE SHOCK: 30 resources drained from {len(alive_ids)} agents")


async def resource_abundance_event(engine: SimulationEngine):
    """Aid drop event: grant 50 resources to all alive agents."""
    logger = get_logger()
    alive_ids = await engine.filter(types=(MortalSocietyAgent,))
    if not alive_ids:
        return

    resource_map = await engine.gather(
        "resource_pool", target_agent_ids=alive_ids, flatten=True, keep_id=True
    )
    for aid, current in resource_map.items():
        new_value = current + 50.0
        await engine.update([aid], "resource_pool", new_value)

    await engine.update_environment(
        "other_information",
        "RELIEF: Emergency aid has arrived! "
        "All citizens received 50 resources. The community has a chance to rebuild.",
    )
    logger.info(f"AID DROP: 50 resources granted to {len(alive_ids)} agents")
