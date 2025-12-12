from src.constants import Constants
from src.globals import Globals
from src.schemas.domain import DomainCreate, DomainDelete, Domain, DomainUpdate
from src.schemas.time_perf import TimePerfCreate
from src.tables import domains as domains_table
from src.tables import time_perf as time_perf_table
from src.tables import urls as urls_table
from src.services import logs as log_service
from asyncpg import Connection
from asyncpg.exceptions import CheckViolationError
from fastapi import Request, status
from fastapi.exceptions import HTTPException
import time
import httpx


async def create_domain(domain_create: DomainCreate, conn: Connection) -> Domain:
    try:
        domain: Domain = await domains_table.create_domain(domain_create, conn)
    except CheckViolationError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Url inválida")
    if not domain_create.is_secure:
        await urls_table.delete_urls_by_domain(domain, conn)
    return domain


async def delete_domain(domain: DomainDelete, conn: Connection):
    await domains_table.delete_domain_by_id(domain.id, conn)


async def is_safe_domain(request: Request, domain: Domain, conn: Connection) -> bool:
    body = {
        "client": {
            "clientId": "yanille-api", 
            "clientVersion": "1.0"
        },
        "threatInfo": {
            "threatTypes": [
                "MALWARE",
                "SOCIAL_ENGINEERING",
                "UNWANTED_SOFTWARE",
                "POTENTIALLY_HARMFUL_APPLICATION",
            ],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": domain.url}],
        },
    }

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            t1: float = time.perf_counter()
            resp = await client.post(Constants.SAFE_BROWSING_URL, json=body)
            resp.raise_for_status()
            data = resp.json()
            t2: float = time.perf_counter()

            if not Constants.IS_PRODUCTION:
                await time_perf_table.create_time_perf(
                    TimePerfCreate(
                        perf_type='api_request',
                        execution_time=t2 - t1,
                        perf_subtype='safe_browsing_api'
                    ),
                    conn
                )

            if data.get("matches"):                
                await domains_table.upsert_domain(domain.id, False, conn)
                return False
            
            return True
    except httpx.RequestError as e:
        await log_service.log_error(
            request,
            e,
            'ERROR',
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            str(e)
        )
        return False
    

async def update_domain(domain: DomainUpdate, conn: Connection) -> None:
    await domains_table.update_domain(domain, conn)
    if not domain.is_secure:
        await urls_table.delete_urls_by_domain(domain, conn)
    return await domains_table.get_domain_by_id(domain.id, conn)