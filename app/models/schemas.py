from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class EventScores:
    surprise: float = 0.0
    credibility: float = 0.0
    persistence: float = 0.0
    transmission: float = 0.0
    conflict: float = 0.0
    fragility: float = 0.0


@dataclass
class AssetImpact:
    asset: str
    bias: str
    confidence: str


@dataclass
class PoliticalEvent:
    event_id: str
    event_summary: str
    event_type: str
    subtype: str
    actors: List[str] = field(default_factory=list)
    location: str = ""
    targets: List[str] = field(default_factory=list)
    implementation_status: str = ""
    scores: EventScores = field(default_factory=EventScores)
    affected_assets: List[AssetImpact] = field(default_factory=list)
    time_horizon_view: Dict[str, str] = field(default_factory=dict)
    historical_analog_logic: str = ""
    reversal_risk: str = ""
    action_state: str = ""
    confidence: str = ""
    notes: str = ""