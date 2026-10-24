from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from tooldawn.modules.catalog.repository import CatalogRepository
from tooldawn.modules.catalog.schemas import CategorySummary, Tool, ToolPage

router = APIRouter(tags=["catalog"])


def get_catalog(request: Request) -> CatalogRepository:
    return request.app.state.catalog


Catalog = Annotated[CatalogRepository, Depends(get_catalog)]


@router.get("/categories", response_model=list[CategorySummary])
async def categories(catalog: Catalog) -> list[CategorySummary]:
    return await catalog.categories()


@router.get("/tools", response_model=ToolPage)
async def tools(
    catalog: Catalog,
    q: Annotated[str, Query(max_length=100)] = "",
    category: Annotated[str | None, Query(max_length=80)] = None,
    sort: Literal["recommended", "recent"] = "recommended",
    cursor: Annotated[int, Query(ge=0, le=10000)] = 0,
    limit: Annotated[int, Query(ge=1, le=48)] = 24,
    featured: bool = False,
) -> ToolPage:
    return await catalog.list_tools(q, category, sort, cursor, limit, featured)


@router.get("/tools/{slug}", response_model=Tool)
async def tool_detail(slug: str, catalog: Catalog) -> Tool:
    tool = await catalog.get_tool(slug)
    if tool is None:
        raise HTTPException(404, "没有找到这个工具。")
    return tool
