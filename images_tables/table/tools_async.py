# -*- coding: utf-8 -*-
import os
import json
import base64
import io
import asyncio
from PIL import Image  # 需要安装: pip install Pillow
from openai import AsyncOpenAI
from openai import APIConnectionError, APIError, RateLimitError

def process_and_encode_image(image_path, max_size=800):
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"未找到图片文件: {image_path}")

    # 打开图片
    with Image.open(image_path) as img:
        # 获取原始尺寸
        width, height = img.size

        # 检查是否需要缩放 (只要有一边超过 max_size)
        if width > max_size or height > max_size:
            # thumbnail 方法会保持比例缩放，使长宽都不超过指定值，且修改原对象
            img.thumbnail((max_size, max_size))

        # 将图片保存到内存缓冲区 (BytesIO)，而不是写入硬盘
        buffer = io.BytesIO()
        # 以此保持原格式保存（如PNG或JPEG），如果无法获取格式默认保存为PNG
        img_format = img.format if img.format else 'PNG'
        img.save(buffer, format=img_format)

        # 获取二进制数据并进行 Base64 编码
        return base64.b64encode(buffer.getvalue()).decode("utf-8")


async def analyze_table_content_async(
    image_path,
    table_html,
    config: str,
    api_key,
    base_url,
    model_name,
    semaphore=None,
):
    if semaphore:
        async with semaphore:
            return await _analyze_table_content_impl(
                image_path, table_html, config, api_key, base_url, model_name
            )
    else:
        return await _analyze_table_content_impl(
            image_path, table_html, config, api_key, base_url, model_name
        )


async def _analyze_table_content_impl(
    image_path, table_html, config: str, api_key, base_url, model_name
):
    def safe_json_parse(json_str):
        try:
            if "json" in json_str:
                json_str = json_str.replace("json", "")
            if "'''" in json_str:
                json_str = json_str.replace("'''", "")
            if "\n" in json_str:
                json_str = json_str.replace("\n", "")
            return json.loads(json_str)
        except Exception:
            return json_str

    # 1. 异步客户端
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=base_url,
    )

    # 2. 图片处理
    try:
        base64_image = process_and_encode_image(image_path, max_size=800)
    except Exception as e:
        return {"type": "table", "image_cls": "error", "description": str(e)}

    image_message = {
        "type": "image_url",
        "image_url": {"url": f"data:image/png;base64,{base64_image}"},
    }

    # 3. prompts
    kvalue_prompt = (
        "你是一个数据分析技术员，请仔细分析该表格的内容，并将其转化为键值对（key-value）的形式，最终输出为JSON格式。\n"
        "1. 不要遗漏任何一个单元格。\n"
        "2. 每个key/value必须来自单个单元格。\n"
        "3. 输出必须是可解析的JSON。\n"
        "4. 不要添加任何解释性文字。\n"
    )

    desc_prompt = (
        "你是一个数据分析技术员，请分析该表格并进行描述：\n"
        "1. 说明这是一张什么类型的表格。\n"
        "2. 如果是数据表，分析最大值、最小值等特征。\n"
        "3. 如包含文字信息，请进行概括说明。\n"
    )

    # 4. API calls
    async def kv_api_call():
        try:
            resp = await client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "user", "content": [image_message, {"type": "text", "text": kvalue_prompt}]}
                ],
                temperature=0.1,
            )
            return safe_json_parse(resp.choices[0].message.content)
        except Exception as e:
            return {"error": f"kv 提取失败: {e}"}

    async def desc_api_call():
        try:
            resp = await client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "user", "content": [image_message, {"type": "text", "text": desc_prompt}]}
                ],
            )
            return resp.choices[0].message.content
        except Exception as e:
            return f"描述失败: {e}"

    # 5. config 分支（完全对齐同步版）
    result = {"type": "table"}

    if "kv" in config and "desc" in config and "html" in config:
        result["kv_extract"] = await kv_api_call()
        result["description"] = await desc_api_call()
        result["table_html"] = table_html
        return result

    elif "kv" in config and "desc" in config:
        result["kv_extract"] = await kv_api_call()
        result["description"] = await desc_api_call()
        return result

    elif "desc" in config and "html" in config:
        result["description"] = await desc_api_call()
        result["table_html"] = table_html
        return result

    elif "kv" in config and "html" in config:
        result["kv_extract"] = await kv_api_call()
        result["table_html"] = table_html
        return result

    elif "kv" in config:
        result["kv_extract"] = await kv_api_call()
        return result

    elif "desc" in config:
        result["description"] = await desc_api_call()
        return result

    elif "html" in config:
        result["table_html"] = table_html
        return result

    return result



if __name__ == "__main__":
    asyncio.run(main())