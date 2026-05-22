import sys
from pathlib import Path
import asyncio

# Ensure the src module can be imported
sys.path.append(str(Path(__file__).parent.absolute()))

from cli.ingest import ingest_vault
from src.config import settings

async def main():
    vault_path = settings.VAULT_PATH
    print(f"Starting programmatic ingestion of vault at: {vault_path}")
    try:
        result = await ingest_vault(vault_path)
        print("Ingestion results:")
        for k, v in result.items():
            print(f"{k}: {v}")
    except Exception as e:
        print(f"Error during ingestion: {e}")

if __name__ == "__main__":
    asyncio.run(main())
