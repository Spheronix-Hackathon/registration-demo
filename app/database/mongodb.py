import logging

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import OperationFailure

from config.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

MONGO_URI = settings.effective_mongodb_uri
DB_NAME = settings.effective_database_name
# Fix L-05 / DB-04: Use configurable global DB name from settings (GLOBAL_DB_NAME env var)
GLOBAL_DB_NAME = settings.global_db_name

# Fix P-03: Remove sync MongoClient created at import time — it was unused (only async is used)
# All DB operations use the async motor client below.
async_client = AsyncIOMotorClient(MONGO_URI)
async_db = async_client[DB_NAME]
global_async_db = async_client[GLOBAL_DB_NAME]

# Primary collections
users_async_collection = async_db["users"]
registrations_async_collection = async_db["registrations"]
teams_async_collection = async_db["teams"]
hackathon_challenges_async_collection = async_db["hackathon_challenges"]

# Global (shared) collections
colleges_async_collection = global_async_db["colleges"]
# The collection name must be "global data" (with a space) to maintain compatibility
# with the other project that updates the task details in this database.
global_data_async_collection = global_async_db["global data"]
branches_async_collection = global_async_db["branches"]
contacts_async_collection = global_async_db["contacts"]


async def initialize_async_collections() -> None:
    # --- Cleanup legacy indexes ---
    # Drop old participant_id unique index if it exists (prevents multiple nulls pre-assignment)
    try:
        await registrations_async_collection.drop_index("participant_id_1")
        logger.info("Dropped legacy index 'participant_id_1' from registrations collection")
    except OperationFailure:
        pass  # Index doesn't exist, which is fine

    # Helper to recreate index if options have changed (e.g. adding sparse=True)
    async def create_index_safe(collection, key, **kwargs):
        try:
            await collection.create_index(key, **kwargs)
        except OperationFailure as e:
            if "IndexKeySpecsConflict" in e._message or e.code == 86:
                logger.info(f"Recreating conflicting index for {key} on {collection.name}")
                # Drop the conflicting index (typically named key_1)
                await collection.drop_index(f"{key}_1")
                await collection.create_index(key, **kwargs)
            else:
                raise

    # --- Users ---
    await create_index_safe(users_async_collection, "email", unique=True)

    # --- Registrations (primary) ---
    await create_index_safe(registrations_async_collection, "email", unique=True, sparse=True)
    await create_index_safe(registrations_async_collection, "mobile", unique=True, sparse=True)
    await create_index_safe(registrations_async_collection, "rollNumber", unique=True, sparse=True)
    await create_index_safe(registrations_async_collection, "rzp_order_id", unique=True, sparse=True)
    await create_index_safe(registrations_async_collection, "registrationCompleted")

    # Fix DB-02: Add missing indexes on nested email/rollNumber/mobile paths
    # These are needed for the duplicate-check $or queries to avoid full-collection scans
    await registrations_async_collection.create_index("leader.email")
    await registrations_async_collection.create_index("leader.rollNumber")
    await registrations_async_collection.create_index("team_members.email")
    await registrations_async_collection.create_index("team_members.rollNumber")
    await registrations_async_collection.create_index("team_members.mobile")

    # --- Teams ---
    await teams_async_collection.create_index("teamId", unique=True)

    # --- Colleges (global) ---
    await colleges_async_collection.create_index("name_lc")
    await colleges_async_collection.create_index("sort_order")

    # --- Contacts (global) ---
    await contacts_async_collection.create_index("email")
    await contacts_async_collection.create_index("timestamp")

    # --- Hackathon challenges ---
    await hackathon_challenges_async_collection.create_index(
        [("category", 1), ("title", 1)], unique=True
    )
    await hackathon_challenges_async_collection.create_index("category")
    await hackathon_challenges_async_collection.create_index("difficulty")

    logger.info("All MongoDB indexes initialized successfully.")