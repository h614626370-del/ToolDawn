from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tooldawn.modules.ai_tools.schemas import Run


class ImageInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    request_key: UUID
    prompt: str = Field(min_length=2, max_length=4000)
    size: Literal["1024x1024", "1536x1024", "1024x1536"] = "1024x1024"
    mode: Literal["generate", "edit"] = "generate"
    reference_id: UUID | None = None
    background: Literal["auto", "transparent"] = "auto"
    quality: Literal["low", "medium", "high"] = "low"

    @model_validator(mode="after")
    def reference_for_mode(self):
        if (self.mode == "edit") != (self.reference_id is not None):
            raise ValueError("图生图需要参考图片")
        return self


class ImageRun(Run):
    mode: str = "generate"
    size: str = ""
    background: str = "auto"
    quality: str = "low"


def run_view(run, job):
    return ImageRun(**Run.model_validate(run).model_dump(), **(job.options if job else {}))
