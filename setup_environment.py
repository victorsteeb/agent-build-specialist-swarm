"""
Create the cloud Environment that the Deal Desk session runs in.

Safe to run multiple times — if `.environment_id` already exists, it's reused.

Usage:
    python setup_environment.py
"""

from pathlib import Path

from _common import get_client


def main() -> None:
    env_path = Path(".environment_id")
    if env_path.exists():
        existing = env_path.read_text().strip()
        print(f"Environment already exists: {existing}")
        print("(remove .environment_id if you want to provision a new one)")
        return

    client = get_client()

    # Environment names are unique per workspace — a second create with the
    # same name returns 409. On a shared team workspace (or after deleting
    # .environment_id), reuse the existing environment instead of erroring.
    env_name = "specialist-swarm-env"
    environment = next(
        (e for e in client.beta.environments.list() if e.name == env_name), None
    )
    if environment is not None:
        print(f"Reusing existing environment '{env_name}': {environment.id}")
    else:
        environment = client.beta.environments.create(
            name=env_name,
            config={
                "type": "cloud",
                "networking": {"type": "unrestricted"},
            },
        )
        print(f"Environment created: {environment.id}")
    env_path.write_text(environment.id)


if __name__ == "__main__":
    main()
