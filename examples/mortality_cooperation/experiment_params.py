"""Shared parameter dataclass for all tunable experiment values."""

from dataclasses import dataclass


@dataclass
class ExperimentParams:
    # Agent composition
    num_high: int = 10
    num_medium: int = 10
    num_low: int = 10

    # Economic parameters
    cooperation_cost: float = 15.0
    daily_maintenance: float = 5.0
    cooperation_multiplier: float = 2.5
    death_threshold: float = 20.0
    initial_resources: float = 100.0

    # Shock parameters
    shock_amount: float = 30.0
    shock_day: int = 5
    aid_amount: float = 50.0
    aid_day: int = 10

    # Visibility: whether agents see the community cooperation rate
    show_cooperation_rate: bool = True

    # Simulation length
    num_days: int = 15

    # Run identification
    run_name: str = "baseline"
