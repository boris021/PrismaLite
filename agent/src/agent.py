import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AgentConfig:
    backend_url: str
    tenant_id: int
    store_id: int

    @classmethod
    def load(cls, path: Path) -> "AgentConfig":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            backend_url=data["backend_url"],
            tenant_id=data["tenant_id"],
            store_id=data["store_id"],
        )


def run_agent(config: AgentConfig) -> None:
    print("Starting POS Agent (stub)...")
    print(f"Sending events to {config.backend_url}")
    try:
        while True:
            print("Stub event sent")
            time.sleep(5)
    except KeyboardInterrupt:
        print("Stopping agent")


def simulate_event(config: AgentConfig, event_type: str) -> None:
    print(f"Simulating event '{event_type}' for store {config.store_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="PrismaLite POS Agent (stub)")
    parser.add_argument("--config", default="config.json", help="Path to config file")
    parser.add_argument("--simulate", help="Simulate single event type")
    args = parser.parse_args()

    config = AgentConfig.load(Path(args.config))

    if args.simulate:
        simulate_event(config, args.simulate)
    else:
        run_agent(config)


if __name__ == "__main__":
    main()

