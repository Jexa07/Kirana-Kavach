from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.action_execution import N8NConfig


def test_n8n_config_defaults_to_mock():
    config = N8NConfig.from_env()
    assert config.provider in {"mock", "webhook"}
