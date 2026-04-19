from dataclasses import dataclass


@dataclass
class Settings:
    app_name: str = "Political Market AI"
    default_region: str = "global"
    default_asset_focus: str = "energy_geopolitics"
    event_db_path: str = "data/processed/events.json"
    market_db_path: str = "data/market_snapshots/"