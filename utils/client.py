from openai import OpenAI
import httpx


def create_client(
    base_url: str,
    api_key: str = "dummy",
    model_name: str = "gpt-3.5-turbo",
    connect_timeout: float = 5.0,
    read_timeout: float = 300.0,
) -> OpenAI:


    client = OpenAI(
        base_url=base_url,
        api_key=api_key,
        timeout=(connect_timeout, read_timeout)
    )

    return client

from openai import OpenAI
from typing import Iterator
import base64

def stream_text(
    client: OpenAI,
    prompt: str,
    model: str = "qwen3-14b"
) -> Iterator[str]:
    """
    千问兼容模式流式文本生成
    """
    stream = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        stream=True
    )

    for chunk in stream:
        # 修正：delta 是对象，不是字典，用属性访问
        delta = chunk.choices[0].delta
        content = delta.content if hasattr(delta, 'content') else None
        if content:
            yield content


from openai import OpenAI
from typing import Iterator


def stream_image_description(
    client: OpenAI,
    base64_image: str,
    prompt: str = "描述这张图片",
    model: str = "qwen3-14b-vl"
) -> Iterator[str]:
    """
    千问兼容模式流式图片推理
    参数:
        base64_image: 图片的 base64 编码字符串（不含 data:image 前缀）
        prompt: 对图片的提问/描述要求
        model: 模型名称
    """
    # 构造 data URI 格式
    image_input = f"data:image/jpeg;base64,{base64_image}"

    stream = client.chat.completions.create(
        model=model,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_input}}
            ]
        }],
        stream=True
    )

    for chunk in stream:
        delta = chunk.choices[0].delta
        content = delta.content if hasattr(delta, 'content') and delta.content else None
        if content:
            yield content