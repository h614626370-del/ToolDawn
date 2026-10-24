import hmac
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from tooldawn.modules.auth.models import EmailChallenge, SessionRecord, UserRecord


class AuthRepository:
    def __init__(self, sessions: async_sessionmaker):
        self.sessions = sessions

    async def save_challenge(self, challenge: EmailChallenge) -> None:
        async with self.sessions.begin() as db:
            db.add(challenge)

    async def remove_challenge(self, challenge_id: UUID) -> None:
        async with self.sessions.begin() as db:
            await db.execute(delete(EmailChallenge).where(EmailChallenge.id == challenge_id))

    async def verify(
        self,
        challenge_id: UUID,
        email: str,
        digest: str,
        token_digest: str,
        session_days: int,
        allow_create: bool = True,
    ) -> UserRecord | None:
        now = datetime.now(UTC)
        async with self.sessions.begin() as db:
            challenge = await db.scalar(
                select(EmailChallenge).where(EmailChallenge.id == challenge_id).with_for_update()
            )
            if (
                challenge is None
                or challenge.email != email
                or challenge.consumed
                or challenge.expires_at <= now
                or challenge.attempts >= 5
            ):
                return None
            # Failed attempts must commit as well; don't raise inside this transaction.
            challenge.attempts += 1
            if not hmac.compare_digest(challenge.code_digest, digest):
                return None
            challenge.consumed = True
            existing = await db.scalar(select(UserRecord).where(UserRecord.email == email))
            if (existing is None and not allow_create) or (existing and existing.is_superadmin):
                return None
            await db.execute(
                insert(UserRecord)
                .values(id=uuid4(), email=email, role="user", disabled=False, created_at=now)
                .on_conflict_do_nothing(index_elements=["email"])
            )
            user = await db.scalar(
                select(UserRecord).where(UserRecord.email == email).with_for_update()
            )
            if user.disabled:
                return None
            db.add(
                SessionRecord(
                    token_digest=token_digest,
                    user_id=user.id,
                    created_at=now,
                    expires_at=now + timedelta(days=session_days),
                )
            )
            return user

    async def current_user(self, digest: str) -> UserRecord | None:
        async with self.sessions() as db:
            return await db.scalar(
                select(UserRecord)
                .join(SessionRecord, SessionRecord.user_id == UserRecord.id)
                .where(
                    SessionRecord.token_digest == digest,
                    SessionRecord.expires_at > datetime.now(UTC),
                    UserRecord.disabled.is_(False),
                )
            )

    async def revoke(self, digest: str) -> None:
        async with self.sessions.begin() as db:
            await db.execute(delete(SessionRecord).where(SessionRecord.token_digest == digest))

    async def create_admin(self, email: str) -> None:
        async with self.sessions.begin() as db:
            await db.execute(
                insert(UserRecord)
                .values(
                    id=uuid4(),
                    email=email,
                    role="admin",
                    disabled=False,
                    created_at=datetime.now(UTC),
                )
                .on_conflict_do_update(index_elements=["email"], set_={"role": "admin"})
            )

    async def cleanup(self) -> None:
        now = datetime.now(UTC)
        async with self.sessions.begin() as db:
            await db.execute(delete(EmailChallenge).where(EmailChallenge.expires_at <= now))
            await db.execute(delete(SessionRecord).where(SessionRecord.expires_at <= now))
