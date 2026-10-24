import json
from importlib.resources import files

from tooldawn.modules.ai_tools.registry import TOOLS
from tooldawn.modules.catalog.schemas import Category, Tool


def load_seed() -> tuple[list[Category], list[Tool]]:
    source = files("tooldawn.modules.catalog").joinpath("seed.json").read_text(encoding="utf-8")
    data = json.loads(source)
    categories = [Category.model_validate(item) for item in data["categories"]]
    raw_tools = {item["slug"]: item for item in data["tools"]}
    for index, spec in enumerate(TOOLS.values()):
        original = raw_tools.get(spec.slug, {})
        raw_tools[spec.slug] = {
            **original,
            "slug": spec.slug,
            "name": spec.name,
            "summary": spec.summary,
            "description": "填写内容和偏好，生成后可复制或下载结果。支持多种输出语言。",
            "category": spec.category,
            "icon": spec.icon,
            "color": spec.color,
            "kind": "internal",
            "status": "available",
            "featured": True,
            "keywords": list(
                dict.fromkeys(
                    [
                        *original.get("keywords", []),
                        spec.name,
                        *spec.slug.split("-"),
                        "AI",
                    ]
                )
            ),
            "features": ["多种输出语言", "自选表达风格", "复制与下载", "最近生成记录"],
            "updated_at": "2026-10-24",
            "sort_order": original.get("sort_order", 13 + index),
        }
    tools = [Tool.model_validate(item) for item in raw_tools.values()]
    category_slugs = {item.slug for item in categories}
    if len({item.slug for item in tools}) != len(tools):
        raise ValueError("Duplicate tool slugs in seed catalog")
    if any(item.category not in category_slugs for item in tools):
        raise ValueError("Unknown category in seed catalog")
    return categories, tools
