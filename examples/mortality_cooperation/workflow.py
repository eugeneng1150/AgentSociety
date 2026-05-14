"""
Workflow functions for the mortality-cooperation experiment.

These are passed as `func` to WorkflowStepConfig(type=FUNCTION) and called
by the simulation engine with `async def func(engine)`.

All functions accept keyword-only parameters with defaults matching the
baseline configuration. Use functools.partial to inject different values.
"""

from agentsociety.logger import get_logger
from agentsociety.simulation import SimulationEngine

from .agent import MortalSocietyAgent


async def mortality_check(
    engine: SimulationEngine,
    *,
    multiplier: float = 2.5,
    death_threshold: float = 20.0,
    cooperation_cost: float = 15.0,
    show_cooperation_rate: bool = True,
):
    """
    End-of-day processing:
    1. Gather cooperated_this_round flags from alive agents
    2. Distribute shared pool payout to cooperators
    3. Kill agents whose resource_pool < death_threshold
    4. Broadcast summary (with or without cooperation stats)
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
        total_contribution = num_cooperators * cooperation_cost
        pool_payout = total_contribution * multiplier
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
        aid for aid, resources in resource_map_after.items()
        if resources < death_threshold
    ]

    if dead_ids:
        for aid in dead_ids:
            await engine.update([aid], "is_alive", False)
        await engine.delete_agents(dead_ids)
        logger.info(f"DEATH: {len(dead_ids)} agents died. IDs: {dead_ids}")

    cooperation_rate = (num_cooperators / num_alive * 100) if num_alive > 0 else 0
    survivors = num_alive - len(dead_ids)

    if show_cooperation_rate:
        situation = (
            f"Today: {num_cooperators}/{num_alive} agents cooperated "
            f"({cooperation_rate:.0f}% cooperation rate). "
            f"{len(dead_ids)} agents died from resource depletion. "
            f"{survivors} agents remain alive."
        )
    else:
        situation = (
            f"Today: {len(dead_ids)} agents died from resource depletion. "
            f"{survivors} agents remain alive."
        )

    await engine.update_environment("other_information", situation)
    logger.info(f"Day summary: {situation}")


async def resource_scarcity_shock(
    engine: SimulationEngine,
    *,
    shock_amount: float = 30.0,
):
    """Famine event: drain resources from all alive agents."""
    logger = get_logger()
    alive_ids = await engine.filter(types=(MortalSocietyAgent,))
    if not alive_ids:
        return

    resource_map = await engine.gather(
        "resource_pool", target_agent_ids=alive_ids, flatten=True, keep_id=True
    )
    for aid, current in resource_map.items():
        new_value = max(0.0, current - shock_amount)
        await engine.update([aid], "resource_pool", new_value)

    await engine.update_environment(
        "other_information",
        f"CRISIS: A severe famine has struck the community! "
        f"All citizens lost {shock_amount:.0f} resources. Cooperation is critical for survival.",
    )
    logger.info(
        f"FAMINE SHOCK: {shock_amount:.0f} resources drained from {len(alive_ids)} agents"
    )


async def resource_abundance_event(
    engine: SimulationEngine,
    *,
    aid_amount: float = 50.0,
):
    """Aid drop event: grant resources to all alive agents."""
    logger = get_logger()
    alive_ids = await engine.filter(types=(MortalSocietyAgent,))
    if not alive_ids:
        return

    resource_map = await engine.gather(
        "resource_pool", target_agent_ids=alive_ids, flatten=True, keep_id=True
    )
    for aid, current in resource_map.items():
        new_value = current + aid_amount
        await engine.update([aid], "resource_pool", new_value)

    await engine.update_environment(
        "other_information",
        f"RELIEF: Emergency aid has arrived! "
        f"All citizens received {aid_amount:.0f} resources. The community has a chance to rebuild.",
    )
    logger.info(
        f"AID DROP: {aid_amount:.0f} resources granted to {len(alive_ids)} agents"
    )
