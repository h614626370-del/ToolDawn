from typing import Protocol

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from tooldawn.modules.catalog.models import CategoryRecord, ToolRecord
from tooldawn.modules.catalog.schemas import CategorySummary, Tool, ToolPage
from tooldawn.modules.catalog.seed import load_seed


class CatalogRepository(Protocol):
    async def categories(self) -> list[CategorySummary]: ...

    async def list_tools(
        self, q: str, category: str | None, sort: str, cursor: int, limit: int, featured: bool
    ) -> ToolPage: ...

    async def get_tool(self, slug: str) -> Tool | None: ...


class SeedCatalogRepository:
    def __init__(self) -> None:
        self._categories, self._tools = load_seed()

    async def categories(self) -> list[CategorySummary]:
        return [
            CategorySummary(
                **category.model_dump(),
                tool_count=sum(tool.category == category.slug for tool in self._tools),
            )
            for category in self._categories
        ]

    async def list_tools(
        self, q: str, category: str | None, sort: str, cursor: int, limit: int, featured: bool
    ) -> ToolPage:
        query = q.strip().casefold()
        items = [
            tool
            for tool in self._tools
            if (not category or tool.category == category)
            and (not featured or tool.featured)
            and query in " ".join([tool.name, tool.summary, *tool.keywords]).casefold()
        ]
        items.sort(key=lambda tool: (tool.sort_order, tool.slug))
        if sort == "recent":
            items.sort(key=lambda tool: tool.updated_at, reverse=True)
        end = cursor + limit
        return ToolPage(
            items=items[cursor:end],
            total=len(items),
            next_cursor=end if end < len(items) else None,
        )

    async def get_tool(self, slug: str) -> Tool | None:
        return next((tool for tool in self._tools if tool.slug == slug), None)


class PostgresCatalogRepository:
    def __init__(self, sessions: async_sessionmaker) -> None:
        self._sessions = sessions

    async def categories(self) -> list[CategorySummary]:
        query = (
            select(CategoryRecord, func.count(ToolRecord.slug))
            .outerjoin(
                ToolRecord,
                (ToolRecord.category == CategoryRecord.slug) & ToolRecord.published.is_(True),
            )
            .group_by(CategoryRecord.slug)
            .order_by(CategoryRecord.sort_order, CategoryRecord.slug)
        )
        async with self._sessions() as session:
            rows = (await session.execute(query)).all()
        return [
            CategorySummary(
                slug=item.slug, name=item.name, icon=item.icon, color=item.color, tool_count=count
            )
            for item, count in rows
        ]

    async def list_tools(
        self, q: str, category: str | None, sort: str, cursor: int, limit: int, featured: bool
    ) -> ToolPage:
        query = select(ToolRecord).where(ToolRecord.published.is_(True))
        if category:
            query = query.where(ToolRecord.category == category)
        if featured:
            query = query.where(ToolRecord.featured.is_(True))
        if q.strip():
            query = query.where(
                or_(
                    ToolRecord.name.icontains(q.strip(), autoescape=True),
                    ToolRecord.summary.icontains(q.strip(), autoescape=True),
                    cast(ToolRecord.keywords, String).icontains(q.strip(), autoescape=True),
                )
            )
        ordering = [ToolRecord.sort_order, ToolRecord.slug]
        if sort == "recent":
            ordering.insert(0, ToolRecord.updated_at.desc())
        async with self._sessions() as session:
            total = await session.scalar(select(func.count()).select_from(query.subquery()))
            records = (
                await session.scalars(query.order_by(*ordering).offset(cursor).limit(limit))
            ).all()
        end = cursor + limit
        return ToolPage(
            items=[Tool.model_validate(item, from_attributes=True) for item in records],
            total=total or 0,
            next_cursor=end if end < (total or 0) else None,
        )

    async def get_tool(self, slug: str) -> Tool | None:
        async with self._sessions() as session:
            record = await session.get(ToolRecord, slug)
            return (
                Tool.model_validate(record, from_attributes=True)
                if record and record.published
                else None
            )
