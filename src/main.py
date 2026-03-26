from __future__ import annotations

from agent.config import load_config
from agent.pipeline import AgentPipeline


def main() -> None:
    config = load_config()
    pipeline = AgentPipeline(config)
    pipeline.run()


if __name__ == "__main__":
    main()
