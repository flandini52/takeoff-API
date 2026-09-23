"""ETL entry point.

Flow (see README): gestionale API -> extract -> transform -> load -> PostgreSQL.

Runs once per invocation, not a daemon — trigger it via
`docker compose run --rm etl` (or `up etl`), cron, or an external
scheduler, independently of the streamlit/postgres services.

For now this only proves the pipeline is wired up end-to-end using mock
data (clearly marked as such in api/client.py) — no real gestionale API
exists yet.
"""

import logging

from api.client import GestionaleClient
from load.postgres import load_records

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("etl")


def run() -> None:
    logger.info("Starting ETL run")
    client = GestionaleClient()
    try:
        records = client.get_mock_records()
        logger.info("Extracted %d record(s)", len(records))
        # transform step goes here once the real API response shape is known
        load_records(records)
        logger.info("ETL run completed")
    except Exception:
        logger.exception("ETL run failed")
        raise


if __name__ == "__main__":
    run()
