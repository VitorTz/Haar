from src.schemas.user import User, UserLoginData, UserSession, UserCreate
from src.schemas.pagination import Pagination
from src.schemas.token import Token
from src.schemas.client_info import ClientInfo
from asyncpg import Connection
from uuid import UUID
from typing import Optional, Callable


async def get_user(user_id: str | UUID, conn: Connection) -> Optional[User]:
    r = await conn.fetchrow(
        """
            SELECT
                id,
                email,                
                last_login_at,
                created_at
            FROM
                users
            WHERE
                id = $1
        """,
        user_id
    )

    return User(**dict(r)) if r else None


async def get_users(limit: int, offset: int, conn: Connection) -> Pagination[User]:
    total: int = await conn.fetchval("SELECT COUNT(*) AS total FROM users")
    
    r = await conn.fetch(
        """
            SELECT
                id,
                email,
                last_login_at,
                created_at
            FROM
                users
            LIMIT 
                $1
            OFFSET
                $2
        """,
        limit,
        offset
    )

    return Pagination[User](
        total=total,
        limit=limit,
        offset=offset,
        results=[User(**dict(i)) for i in r]
    )


async def get_user_by_refresh_token(refresh_token: str, conn: Connection) -> Optional[User]:
    r = await conn.fetchrow(
        """
            SELECT 
                u.id,
                u.email,
                u.last_login_at,
                u.created_at
            FROM 
                users u
            JOIN 
                user_session_tokens rt ON rt.user_id = u.id
            WHERE 
                rt.refresh_token = $1;
        """,
        refresh_token
    )
    return User(**dict(r)) if r else None


async def update_user_session_token(
    user_id: UUID,
    refresh_token: Token,   
    conn: Connection
):    
    await conn.execute(
        """
            UPDATE
                user_session_tokens
            SET
                expires_at = $1,
                revoked = $2,
                revoked_at = $3,
                last_used_at = CURRENT_TIMESTAMP
            WHERE
                user_id = $4 AND
                refresh_token = $5
        """,
        refresh_token.expires_at,
        refresh_token.revoked,
        refresh_token.revoked_at,
        user_id,
        refresh_token.token
    )


async def get_user_login_data_from_email(email: str, conn: Connection) -> Optional[UserLoginData]:
    r = await conn.fetchrow(
        """
            SELECT
                u.id,
                u.email,
                u.p_hash,
                u.created_at,
                u.last_login_at,
                ul.attempts as login_attempts,
                ul.last_failed_login,
                ul.locked_until
            FROM
                users u
            JOIN
                user_login_attempts ul ON ul.user_id = u.id
            WHERE
                email = TRIM($1)
        """,
        email
    )

    return UserLoginData(**dict(r)) if r else None


async def create_user(new_user: UserCreate, password_hash_func: Callable[[str], bytes], conn: Connection) -> User:
    r = await conn.fetchrow(
        """
            INSERT INTO users (
                email,
                p_hash
            )
            VALUES  
                (LOWER(TRIM($1)), $2)
            RETURNING
                id,
                email,
                last_login_at,
                created_at
        """,
        new_user.email,
        password_hash_func(new_user.password)
    )

    return User(**dict(r)) if r else None


async def register_failed_login_attempt(user_login_data: UserLoginData, conn: Connection) -> UserLoginData:
    await conn.execute(
        """
            UPDATE 
                user_login_attempts
            SET
                attempts = attempts + 1,
                last_failed_login = CURRENT_TIMESTAMP,
                locked_until = $1
            WHERE
                user_id = $2
        """,
        user_login_data.locked_until,
        user_login_data.id
    )
    user_login_data.login_attempts += 1
    return user_login_data


async def lock_user_login(user_login_data: UserLoginData, conn: Connection):
    await conn.execute(
        """
            UPDATE 
                user_login_attempts
            SET
                locked_until = $1
            WHERE
                user_id = $2
        """,
        user_login_data.locked_until,
        user_login_data.id
    )


async def reset_user_login_attempts(user_login_data: UserLoginData, conn: Connection):
    await conn.execute(
        """
            UPDATE 
                user_login_attempts
            SET
                attempts = 0,
                last_failed_login = NULL,
                locked_until = NULL,
                last_successful_login = CURRENT_TIMESTAMP
            WHERE
                user_id = $1
        """,
        user_login_data.id
    )


async def create_user_session_token(
    user_id: str,
    token: Token,
    client_info: ClientInfo,
    conn: Connection
) -> None:
    await conn.execute(
        """
            INSERT INTO user_session_tokens (
                user_id,
                refresh_token,
                expires_at,
                device_name,
                device_ip,
                user_agent
            )
            VALUES 
                ($1, $2, $3, COALESCE($4, 'unknown'), $5, $6)
            ON CONFLICT
                (user_id, device_ip, user_agent)
            DO UPDATE SET
                refresh_token = EXCLUDED.refresh_token,
                expires_at = EXCLUDED.expires_at,
                device_name = EXCLUDED.device_name,
                last_used_at = CURRENT_TIMESTAMP
        """,
        user_id, 
        token.token, 
        token.expires_at,
        client_info.device_name,
        client_info.client_ip,
        client_info.user_agent
    )


async def get_user_sessions(
    user_id: str | UUID, 
    limit: int, 
    offset: int,
    conn: Connection
) -> Pagination[UserSession]:
    total: int = await conn.fetchval(
        "SELECT COUNT(*) AS total FROM user_session_tokens WHERE user_id = $1", 
        user_id
    )

    r = await conn.fetch(
        """
            SELECT
                user_id,
                issued_at,
                expires_at,
                revoked,
                revoked_at,
                device_name,
                device_ip,
                user_agent,
                last_used_at
            FROM
                user_session_tokens
            WHERE
                user_id = $1
            ORDER BY
                issued_at DESC
            LIMIT
                $2
            OFFSET
                $3
        """,
        user_id,
        limit,
        offset
    )

    return Pagination[UserSession](
        total=total,
        limit=limit,
        offset=offset,
        results=[UserSession(**dict(i)) for i in r]
    )


async def delete_user_session_token(refresh_token: str, conn: Connection):
    await conn.execute(
        """
            DELETE FROM 
                user_session_tokens
            WHERE
                refresh_token = $1
        """,        
        refresh_token
    )


async def delete_all_user_session_tokens(user_id: str, conn: Connection):
    await conn.execute(
        """
            DELETE FROM 
                user_session_tokens
            WHERE
                user_id = $1
        """,        
        user_id
    )



async def delete_user(user_id: str | UUID, conn: Connection):
    await conn.execute("DELETE FROM users WHERE id = $1", user_id)


async def delete_all_users(conn: Connection):
    await conn.execute("DELETE FROM users")


async def update_user_last_login_at(user_id: str, conn: Connection):
    await conn.execute(
        """
            UPDATE 
                users
            SET
                last_login_at = NOW()
            WHERE
                id = $1
        """,
        user_id
    )

async def delete_user_url(user_id: str, url_id: int, conn: Connection):
    r = await conn.fetchval(
        """
            SELECT
                url_id
            FROM
                user_urls
            WHERE
                user_id = $1
                AND url_id = $2
        """,
        user_id,
        url_id
    )

    if r is None:
        return
    
    await conn.execute(
        """
            DELETE FROM
                urls
            WHERE
                id = $1
        """,
        r
    )


async def set_user_favorite_url(user_id: str, url_id: int, is_favorite: bool, conn: Connection):
    await conn.execute(
        """
            UPDATE
                user_urls
            SET
                is_favorite = $1
            WHERE
                user_id = $2 AND
                url_id = $3
        """,
        is_favorite,
        user_id,
        url_id
    )


async def get_sessions(limit: int, offset: int, conn: Connection) -> Pagination[UserSession]:
    total: int = await conn.fetchval("SELECT COUNT(*) AS total FROM user_session_tokens")
    rows = await conn.fetch(
        """
            SELECT
                user_id,
                issued_at,
                expires_at,
                revoked,
                revoked_at,
                device_name,
                device_ip,
                user_agent,
                last_used_at
            FROM
                user_session_tokens
            ORDER BY
                issued_at DESC
            LIMIT
                $1
            OFFSET
                $2
        """,
        limit,
        offset
    )

    return Pagination(
        total=total,
        limit=limit,
        offset=offset,
        results=[UserSession(**dict(row)) for row in rows]
    )


async def delete_sessions(conn: Connection):
    await conn.execute("DELETE FROM user_session_tokens")


async def cleanup_expired_sessions(conn: Connection):
    await conn.execute("SELECT cleanup_expired_sessions()")