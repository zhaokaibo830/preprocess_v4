from openai import OpenAI
import httpx


def create_client(
    base_url: str,
    api_key: str = "dummy",
    model_name: str = "gpt-3.5-turbo",
    connect_timeout: float = 5.0,
    read_timeout: float = 300.0,
) -> OpenAI:
    """
    创建 OpenAI client

    参数：
        base_url:
            本地模型地址
            例如 http://127.0.0.1:8000/v1

        connect_timeout:
            TCP连接超时

        read_timeout:
            推理等待时间（重要）

        write_timeout:
            发送请求超时

        pool_timeout:
            等待连接池超时

        max_connections:
            最大连接数

    返回：
        OpenAI client
    """


    client = OpenAI(
        base_url=base_url,
        api_key=api_key,
        timeout=(connect_timeout, read_timeout)
    )

    return client

from openai import OpenAI
from typing import Iterator


def stream_text(
    client: OpenAI,
    prompt: str,
    model: str = "qwen"
) -> Iterator[str]:
    """
    流式文本生成

    返回token流
    """

    stream = client.responses.create(
        model=model,
        input=prompt,
        stream=True
    )

    for event in stream:

        if event.type == "response.output_text.delta":
            yield event.delta



def stream_image_description(
    client: OpenAI,
    image_url: str,
    prompt: str = "描述这张图片",
    model: str = "qwen-vl"
) -> Iterator[str]:
    """
    流式图片推理

    Parameters
    ----------
    client : OpenAI
        已初始化的 OpenAI client

    image_url : str
        图片路径或URL
        例如:
            file:///path/image.jpg
            http://xxx/image.jpg

    prompt : str
        文本提示词

    model : str
        模型名称

    Yields
    ------
    str
        流式输出文本片段
    """

    stream = client.responses.create(
        model=model,
        stream=True,
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_url}"}
                    }
                ]
            }
        ]
    )

    for event in stream:

        if event.type == "response.output_text.delta":
            yield event.delta


if __name__ == "__main__":

    client = OpenAI(
        base_url="http://localhost:8000/v1",
        api_key="EMPTY"
    )

    print("=== 文本测试 ===")

    for t in stream_text(client, "介绍一下量子计算"):
        print(t, end="", flush=True)

    print("\n\n=== 图片测试 ===")

    img = "file:///home/user/test.jpg"

    for t in stream_image_description(client, img):
        print(t, end="", flush=True)