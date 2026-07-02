from openai import OpenAI, AsyncOpenAI
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

def create_async_client(
    base_url: str,
    api_key: str = "dummy",
    model_name: str = "gpt-3.5-turbo",
    connect_timeout: float = 5.0,
    read_timeout: float = 300.0,
    max_connections: int = 100,
    max_keepalive_connections: int = 20,
) -> AsyncOpenAI:
    # 异步场景下建议显式给一个连接池上限，避免并发打爆
    limits = httpx.Limits(
        max_connections=max_connections,
        max_keepalive_connections=max_keepalive_connections,
    )
    http_client = httpx.AsyncClient(
        limits=limits,
        timeout=httpx.Timeout(read_timeout, connect=connect_timeout),
    )
    return AsyncOpenAI(
        base_url=base_url,
        api_key=api_key,
        http_client=http_client,
    )

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
        stream=True,
        extra_body={
            "chat_template_kwargs": {
                "enable_thinking": False  # 关键：将参数放在这里
            }
        }
    )

    for chunk in stream:
        # 防止 choices 为空
        if not hasattr(chunk, "choices"):
            continue
        if not chunk.choices:
            continue
        choice = chunk.choices[0]
        # 防止 delta 不存在
        if not hasattr(choice, "delta"):
            continue
        delta = choice.delta
        # 防止 content 不存在
        content = getattr(delta, "content", None)
        if content:
            yield content

from openai import AsyncOpenAI
from typing import AsyncIterator

async def stream_image_description_async(
    client: AsyncOpenAI,
    base64_image: str,
    prompt: str = "描述这张图片",
    model: str = "qwen3-14b-vl",
) -> AsyncIterator[str]:
    """
    千问兼容模式流式图片推理（异步版）
    参数:
        client: AsyncOpenAI 实例
        base64_image: 图片的 base64 编码字符串（不含 data:image 前缀）
        prompt: 对图片的提问/描述要求
        model: 模型名称
    """
    image_input = f"data:image/jpeg;base64,{base64_image}"

    stream = await client.chat.completions.create(
        model=model,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_input}},
            ],
        }],
        stream=True,
        extra_body={
            "chat_template_kwargs": {
                "enable_thinking": False
            }
        },
    )

    async for chunk in stream:
        if not getattr(chunk, "choices", None):
            continue
        choice = chunk.choices[0]
        delta = getattr(choice, "delta", None)
        if delta is None:
            continue
        content = getattr(delta, "content", None)
        if content:
            yield content


async def _collect_stream_async(
    client: AsyncOpenAI,
    base64_image: str,
    prompt: str,
    model_name: str,
) -> str:
    """把 async generator 收集成完整字符串。并发场景下不再逐 chunk 打印，避免交错乱码。"""
    parts = []
    async for chunk in stream_image_description_async(client, base64_image, prompt, model_name):
        parts.append(chunk)
    return "".join(parts)