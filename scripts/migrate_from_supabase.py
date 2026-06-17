import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from src.db.models import Client, Project, Hypothesis, Finding
from sqlalchemy import text

# Assuming SUPABASE_URL and SUPABASE_KEY are env vars, we could use the Supabase python client
# but the prompt says: "move existing data from Supabase to Azure PostgreSQL for active Project-centric models"
# I will simulate the structure using the supabase library.

from supabase import create_client, Client as SupabaseClient

async def main():
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        print("Set SUPABASE_URL and SUPABASE_KEY to run this migration script.")
        return

    supabase: SupabaseClient = create_client(supabase_url, supabase_key)
    
    AZURE_DB_URL = os.environ.get("ASYNC_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not AZURE_DB_URL:
        print("DATABASE_URL or ASYNC_DATABASE_URL is not set.")
        return
        
    if AZURE_DB_URL.startswith("postgresql://"):
        AZURE_DB_URL = AZURE_DB_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
        
    print(f"Connecting to database (sanitized): {AZURE_DB_URL.split('@')[-1]}")
    engine = create_async_engine(AZURE_DB_URL, echo=False)
    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with AsyncSessionLocal() as session:
        # 1. Clients
        print("Migrating clients...")
        response = supabase.table("clients").select("*").execute()
        for row in response.data:
            client = Client(**row)
            session.add(client)
        
        # 2. Projects
        print("Migrating projects...")
        response = supabase.table("projects").select("*").execute()
        for row in response.data:
            project = Project(**row)
            session.add(project)

        # 3. Hypotheses
        print("Migrating hypotheses...")
        response = supabase.table("hypotheses").select("*").execute()
        for row in response.data:
            hypothesis = Hypothesis(**row)
            session.add(hypothesis)

        # 4. Findings
        print("Migrating findings...")
        response = supabase.table("findings").select("*").execute()
        for row in response.data:
            finding = Finding(**row)
            session.add(finding)

        await session.commit()
        print("Migration complete!")

if __name__ == "__main__":
    asyncio.run(main())
