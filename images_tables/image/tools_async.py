import asyncio
import os
import base64
import io
from PIL import Image
from openai import AsyncOpenAI
from typing import List, Dict, Any
import traceback

def process_and_encode_image(image_path, max_size=800):
    """读取本地图片并转换为 Base64，包含缩放逻辑"""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"未找到图片文件: {image_path}")

    with Image.open(image_path) as img:
        width, height = img.size
        if width > max_size or height > max_size:
            img.thumbnail((max_size, max_size))

        buffer = io.BytesIO()
        img_format = img.format if img.format else 'PNG'
        img.save(buffer, format=img_format)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

async def analyze_image_content_async(image_path, title, config, api_key, base_url, model_name, semaphore=None):
    """
    异步分析图片内容
    semaphore: 用于控制全局最大并发数
    """
    try:
        if semaphore:
            async with semaphore:
                return await _analyze_impl(image_path, title, config, api_key, base_url, model_name)
        else:
            return await _analyze_impl(image_path, title, config, api_key, base_url, model_name)
    except Exception as e:
        # 打印错误栈，方便调试
        print(f"处理图片 {image_path} 时发生严重错误:")
        traceback.print_exc()
        # 返回包含错误信息的字典，确保后续 list 处理不崩溃
        return {"error": f"Task execution failed: {str(e)}", "path": image_path}

async def _analyze_impl(image_path, title, config, api_key, base_url, model_name):
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    try:
        base64_image = process_and_encode_image(image_path, max_size=800)
    except Exception as e:
        return {"error": f"图片处理出错: {str(e)}"}

    image_message = {
        "type": "image_url",
        "image_url": {"url": f"data:image/png;base64,{base64_image}"},
    }
    
    # 构建 title 文本消息（如果 title 为空则不加入 content）
    title_text = f"图片标题是：{title}" if title else ""

    # 1. 图像分类
    async def get_classification():
        classify_prompt = (
            "你是一个图像分类助手。请仔细观察这张图片，将其归类为以下三类之一：\n"
            "1. line graph (折线图)\n"
            "2. bar chart (柱状图)\n"
            "3. pie chart (饼图)\n"
            "4. 铭牌(涉及电力行业的铭牌)\n"
            "5. other (自然图像、人物、风景或其他)\n\n"
            "请仅输出分类结果名词（line graph, bar chart, pie chart, 铭牌或 other），不要带标点。"
        )
        response = await client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": [image_message, {"type": "text", "text": classify_prompt}]}],
            temperature=0.1,
        )
        res_text = response.choices[0].message.content.strip().lower()
        if "line graph" in res_text: return "line graph"
        if "bar chart" in res_text: return "bar chart"
        if "pie chart" in res_text: return "pie chart"
        if "铭牌" in res_text: return "铭牌"
        return "other"
    try:
        image_cls = await get_classification()
    except Exception as e:
        print(f"分类任务失败 [{image_path}]: {e}")
        return {"error": f"分类 API 调用失败: {str(e)}"}
    # 2. 根据分类准备 Prompt
    desc_prompt = ""
    html_prompt = ""

    if image_cls in ["line graph", "bar chart", "pie chart"]:
        # 统计图表描述 Prompt (合并了你的逻辑)
        if image_cls == "line graph":
            desc_prompt = "你是资深数据分析师...核心描述整体走势...结尾包含：'本内容由AI生成，内容仅供参考'。" # (此处省略重复的长文本)
        elif image_cls == "bar chart":
            desc_prompt = "你是资深商业数据分析师...宏观概括...结尾包含：'本内容由AI生成，内容仅供参考'。"
        elif image_cls == "pie chart":
            desc_prompt = "你是擅长数据解读的统计专家...占比排序...结尾包含：'本内容由AI生成，内容仅供参考'。"
        
        html_prompt = '请分析统计图中的数据，并以规范的HTML表格形式呈现：<table>...</table>。只输出代码，不要转义符。'
    
    elif image_cls == "铭牌":
        desc_prompt = "你是一个电力设备铭牌信息分析专家...输出紧凑的一行JSON...禁止转义符。"
    else:
        desc_prompt = "你是一位通用的图片描述专家...描述控制在100字以内...结尾包含：'本内容由AI生成，内容仅供参考'。"

    # 3. 执行后续 API 调用（并行处理 desc 和 html）
    tasks = []
    task_keys = []

    if 'desc' in config and desc_prompt:
        content = [image_message]
        if title_text: content.append({"type": "text", "text": title_text})
        content.append({"type": "text", "text": desc_prompt})
        
        tasks.append(client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": content}]
        ))
        task_keys.append('desc')

    if 'html' in config and html_prompt:
        tasks.append(client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": [image_message, {"type": "text", "text": html_prompt}]}]
        ))
        task_keys.append('html')

    # 并发等待所有子任务完成
    api_results = await asyncio.gather(*tasks, return_exceptions=True)

    # 4. 组装结果
    final_result = {}
    if 'cls' in config:
        final_result["type"] = image_cls

    for key, res in zip(task_keys, api_results):
        if isinstance(res, Exception):
            print(f"子任务 {key} 失败 [{image_path}]: {res}")
            final_result[key] = f"Error: {str(res)}"
        else:
            final_result[key] = res.choices[0].message.content

    return final_result

# ==========================================
# 主并发入口
# ==========================================
async def main():
    # 配置
    API_KEY = "sk-..." 
    BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    MODEL = "qwen3-vl-8b-instruct"
    
    # 待处理任务列表 (path, title)
    img_list = [
        ("./datatest/1_3.png", "测试图1"),
        ("./datatest/1_4.png", ""),
    ]
    
    # 创建信号量，限制同时只有 5 个请求在跑，保护内存和频率
    semaphore = asyncio.Semaphore(5)
    
    tasks = [
        analyze_image_content_async(path, title, "cls,desc,html", API_KEY, BASE_URL, MODEL, semaphore)
        for path, title in img_list
    ]

    print(f"开始并发处理 {len(tasks)} 张图片...")
    results = await asyncio.gather(*tasks)

    for i, res in enumerate(results):
        print(f"--- 图片 {i+1} 结果 ---")
        print(res)

if __name__ == "__main__":
    asyncio.run(main())