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


async def analyze_table_content_async(image_path, table_html, config: str, api_key, base_url, model_name, semaphore=None):
    """
    异步分析表格内容
    
    Args:
        image_path: 图片路径
        table_html: 表格的HTML内容
        config: 配置参数
        api_key: API密钥
        base_url: API基础URL
        model_name: 模型名称
        semaphore: asyncio.Semaphore 对象，用于控制并发数
    """
    # 使用信号量控制并发
    if semaphore:
        async with semaphore:
            return await _analyze_table_content_impl(image_path, table_html, config, api_key, base_url, model_name)
    else:
        return await _analyze_table_content_impl(image_path, table_html, config, api_key, base_url, model_name)


async def _analyze_table_content_impl(image_path, table_html, config: str, api_key, base_url, model_name):
    """
    实际的表格分析实现函数
    """
    def safe_json_parse(json_str):
        try:
            if "json" in json_str:
                json_str = json_str.replace("json", "")
            if "'''" in json_str:
                json_str = json_str.replace("'''", "")
            if "\n" in json_str:
                json_str = json_str.replace("\n", "")
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
            return json_str

    # 1. 准备异步客户端
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=base_url,
    )

    # 2. 处理并编码图片 (此处加入了缩放逻辑)
    try:
        base64_image = process_and_encode_image(image_path, max_size=800)
    except Exception as e:
        return {"image_cls": "error", "description": f"图片处理出错: {str(e)}"}

    image_message = {
        "type": "image_url",
        "image_url": {"url": f"data:image/png;base64,{base64_image}"},
    }

    # ==========================================
    # 第一步：k-value,description，kv_desc prompt构写
    # ==========================================
    kvalue_prompt = (
        "你是一个数据分析技术员，请仔细分析该表格的内容，并将其转化为键值对（key-value）的形式，最终输出为JSON格式。需注意以下要点：\n"
        "1. 请确保不遗漏HTML中的任何一个单元格数据，每一个键（key）或值（value）应当对应表格中的某个单元格，不能将多个单元格的数据拼接成一个值。\n"
        "2. 输出格式必须是标准的JSON格式。\n"
        "3. 不要添加任何额外的解释性文字。\n"
        "4. 相同的key不能出现在同一个dict里面且确保输出的JSON是有效且可以解析的。\n"
    )
    desc_prompt = (
        "你是一个数据分析技术员，请仔细分析该表格的内容，分析并描述该表格传达的信息，需注意以下要点\n"
        "1. 用简明的语言说明这是一张什么什么表格，如'这是一张xx公司的员工工资表'，'这是一张学生成绩表'\n"
        "2. 如果表格内容以数据为主，需要分析表格中如最大值，最小值等能反映数据特点的信息。\n"
        "3. 如果表格内容中涉及文字信息，则应对文字信息和数据进行简要描述。\n"
    )
    kv_desc_prompt = (
    "你是一个数据分析技术员，请仔细分析该表格的内容，并以结构化的JSON格式返回你的分析结果。JSON应包含以下键值：\n"
    "{\n"
    "\"kv\": \"[请仔细分析该表格的内容，并将其转化为键值对（key-value）的形式，最终输出为JSON格式,请确保不遗漏HTML中的任何一个单元格数据，每一个键（key）或值（value）应当对应表格中的某个单元格，不能将多个单元格的数据拼接成一个值，不要添加任何额外的解释性文字。相同的key不能出现在同一个dict里面且确保输出的JSON是有效且可以解析的。]\",\n"
    "\"desc\": \"[用简明的语言说明这是一张什么什么表格，如‘这是一张xx公司的员工工资表’，‘这是一张学生成绩表’。如果表格内容以数据为主，需要分析表格中如最大值，最小值等能反映数据特点的信息。]\"\n"
    "}"
    )

    # ==========================================
    # 第二步：分别构建异步调用API函数
    # ==========================================
    async def kv_api_call():
        try:
            kvalue_completion = await client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [image_message, {"type": "text", "text": kvalue_prompt}],
                    }
                ],
                temperature=0.1,
            )
            kvalue = kvalue_completion.choices[0].message.content
        except Exception as e:
            return {"k-value_extract": "error", "description": f"K-value提取出错: {str(e)}"}
        return kvalue

    async def desc_api_call():
        try:
            desc_completion = await client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [image_message, {"type": "text", "text": desc_prompt}],
                    }
                ],
            )
            description = desc_completion.choices[0].message.content
        except Exception as e:
            return {"desc_completion": "error", "description": f"描述阶段出错: {str(e)}"}
        return description

    async def kv_desc_api_call():
        try:
            kv_desc_completion = await client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [image_message, {"type": "text", "text": kv_desc_prompt}],
                    }
                ],
            )
            kv_desc = kv_desc_completion.choices[0].message.content
        except Exception as e:
            return {"kv_desc_completion": "error", "description": f"kv和描述阶段出错: {str(e)}"}
        # 解析模型输出的JSON字符串
        kv_desc_data = json.loads(kv_desc.strip())
        kv = kv_desc_data["kv"]
        desc = kv_desc_data["desc"]
        return kv, desc

    # ==========================================
    # 第三步：创建if分支识别传入config
    # ==========================================
    result = {}
    result["type"] = "table"
    # 判断config中包含的功能，更新result并返回
    if "kv" in config and "desc" and "html" in config:
        result["kv_extract"], result["description"] = await kv_desc_api_call()
        result["table_html"] = table_html
        return result
    elif "kv" in config and "desc" in config:
        result["kv_extract"], result["description"] = await kv_desc_api_call()
        return result
    elif "desc" in config and "html" in config:
        description = await desc_api_call()
        result["description"] = description
        result["table_html"] = table_html
        return result
    elif "kv" in config and "html" in config:
        kvalue = await kv_api_call()
        result["kv_extract"] = kvalue
        result["table_html"] = table_html
        return result
    elif "kv" in config:
        kvalue = await kv_api_call()
        result["kv_extract"] = kvalue
        return result
    elif "desc" in config:
        description = await desc_api_call()
        result["description"] = description
        return result
    elif "html" in config:
        result["table_html"] = table_html
        return result


# 使用示例
async def main():
    # 配置参数
    API_KEY = "your-api-key"
    BASE_URL = "https://api.openai.com/v1"
    MODEL_NAME = "gpt-4-vision-preview"
    MAX_CONCURRENT = 5  # 最大并发数
    
    # 模拟表格收集逻辑
    table_jobs = []
    # 假设已经收集了表格路径、HTML和索引
    # table_jobs.append((block_index, sub_block_index, img_path, table_html))
    
    table_count = len(table_jobs)
    print(f"已收集{table_count}张表格")
    
    # 创建信号量来控制并发数
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    
    # 并发处理所有表格
    table_results = await asyncio.gather(
        *[analyze_table_content_async(
            str(path),
            html,
            "kv,desc,html",  # table_config
            API_KEY,
            BASE_URL,
            MODEL_NAME,
            semaphore  # 传入信号量
        ) for _, _, path, html in table_jobs]
    )
    
    # 将结果写回原数据结构
    for (b_idx, sb_idx, _, _), result in zip(table_jobs, table_results):
        # full_json_data["output"][b_idx]["llm_process"] = result
        print(f"Block {b_idx}, Sub-block {sb_idx}: {result}")
    
    print(f"已处理{table_count}张表格")


if __name__ == "__main__":
    asyncio.run(main())