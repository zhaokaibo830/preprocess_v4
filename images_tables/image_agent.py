from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pydantic import BaseModel, Field, ConfigDict, field_validator

from images_tables.image.tools import analyze_image_content
from utils.client import create_client


class ImageAnalysisRequest(BaseModel):

    image_path: str = Field(..., description="Local path of the image to analyze.")
    title: str = Field(default="", description="Optional image caption or title.")
    image_class: bool = Field(default=True, description="Return image type.")
    image_desc: bool = Field(default=True, description="Return image description.")
    image_html: bool = Field(default=True, description="Extract chart data as HTML when applicable.")

    @field_validator("image_path")
    @classmethod
    def image_path_must_exist(cls, value: str) -> str:
        path = Path(value).expanduser()
        if not path.exists():
            raise ValueError(f"Image file does not exist: {value}")
        if not path.is_file():
            raise ValueError(f"Image path is not a file: {value}")
        return str(path)


class ImageAnalysisResponse(BaseModel):
    """Stable output contract returned to the main agent."""

    model_config = ConfigDict(extra="allow")

    ok: bool
    image_path: str
    type: Optional[str] = None
    desc: Optional[str] = None
    html: Optional[str] = None
    error: Optional[str] = None


class ImageAnalysisAgent:

    name = "image_analysis_agent"
    description = "Classify an image, describe it, and extract chart data as HTML when possible."

    def __init__(self, client: Any, model_name: str) -> None:
        self.client = client
        self.model_name = model_name

    @classmethod
    def from_config(cls, config_path: str | Path = "config.yaml") -> "ImageAnalysisAgent":
        with open(config_path, "r", encoding="utf-8") as file:
            cfg = yaml.safe_load(file)

        image_cfg = cfg["image_model"]
        client = create_client(
            base_url=image_cfg["BASE_URL"],
            api_key=image_cfg["API_KEY"],
            connect_timeout=image_cfg.get("connection_timeout", 20),
            read_timeout=image_cfg.get("process_timeout", 180),
        )
        return cls(client=client, model_name=image_cfg["MODEL"])

    def invoke(self, payload: Dict[str, Any] | ImageAnalysisRequest) -> Dict[str, Any]:
        try:
            request = payload if isinstance(payload, ImageAnalysisRequest) else ImageAnalysisRequest(**payload)
            result = analyze_image_content(
                image_path=request.image_path,
                img_title=request.title,
                image_class=request.image_class,
                image_desc=request.image_desc,
                image_html=request.image_html,
                client=self.client,
                model_name=self.model_name,
            )
            return ImageAnalysisResponse(ok=True, image_path=request.image_path, **result).model_dump(
                exclude_none=True
            )
        except Exception as exc:
            image_path = payload.image_path if isinstance(payload, ImageAnalysisRequest) else payload.get("image_path", "")
            return ImageAnalysisResponse(ok=False, image_path=image_path, error=str(exc)).model_dump(
                exclude_none=True
            )

    def close(self) -> None:
        close = getattr(self.client, "close", None)
        if callable(close):
            close()

    @staticmethod
    def tool_schema() -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": ImageAnalysisAgent.name,
                "description": ImageAnalysisAgent.description,
                "parameters": ImageAnalysisRequest.model_json_schema(),
            },
        }


def create_image_analysis_agent(config_path: str | Path = "config.yaml") -> ImageAnalysisAgent:
    return ImageAnalysisAgent.from_config(config_path)


def analyze_image_tool(payload: Dict[str, Any], config_path: str | Path = "config.yaml") -> Dict[str, Any]:
    """One-shot function form for frameworks that call plain Python tools."""

    agent = create_image_analysis_agent(config_path)
    try:
        return agent.invoke(payload)
    finally:
        agent.close()

'''调用示例
from images_tables.image_agent import create_image_analysis_agent


def main() -> None:
    agent = create_image_analysis_agent("config.yaml")
    try:
        result = agent.invoke(
            {
                "image_path": r"D:\Learning_Program\preprocess_v4\images_tables\imgs\2.png",
                "title": "",
                "image_class": True,
                "image_desc": True,
                "image_html": True,
            }
        )
        print(result)
    finally:
        agent.close()


if __name__ == "__main__":
    main()

'''