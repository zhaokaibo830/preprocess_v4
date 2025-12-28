import os
import base64
import io
import httpx
from PIL import Image
import asyncio
semaphore_img = asyncio.Semaphore(10)
from openai import AsyncOpenAI   # ① 关键：异步客户端

# ---------------- 工具函数 ----------------
async def process_and_encode_image_async(image_path: str, max_size: int = 800) -> str:
    """异步版：图片缩放 + base64"""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"未找到图片文件: {image_path}")

    # 使用 run_in_executor 把 CPU 密集的 PIL 操作扔到线程池，避免阻塞事件循环
    loop = asyncio.get_event_loop()
    img_bytes = await loop.run_in_executor(
        None, _sync_resize, image_path, max_size)
    return base64.b64encode(img_bytes).decode("utf-8")

def _sync_resize(image_path: str, max_size: int) -> bytes:
    """同步部分，单独拆出来方便 run_in_executor"""
    with Image.open(image_path) as img:
        if max(img.size) > max_size:
            img.thumbnail((max_size, max_size))
        buffer = io.BytesIO()
        fmt = img.format or "PNG"
        img.save(buffer, format=fmt)
        return buffer.getvalue()

# ---------------- 业务函数 ----------------
async def analyze_image_content_async(
        image_path: str,
        api_key: str,
        base_url: str,
        model_name: str) -> dict:
    async with semaphore_img:
        """完全对标原来的 analyze_image_content，只是变成 async"""
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)

        try:
            base64_image = await process_and_encode_image_async(image_path, max_size=800)
        except Exception as e:
            return {"image_cls": "error", "description": f"图片处理出错: {str(e)}"}

        image_message = {
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{base64_image}"},
        }

        # ===== 分类 =====
        classify_prompt = (
            "你是一个图像分类助手。请仔细观察这张图片，将其归类为以下三类之一：\n"
            "1. pictogram (统计图表，如柱状图、折线图、饼图等)\n"
            "2. flowchart (流程图、架构图、思维导图等)\n"
            "3. other (自然图像、人物、风景或其他)\n\n"
            "请仅输出分类结果的英文单词（pictogram, flowchart, 或 other），"
            "不要输出任何标点符号或其他解释性文字。"
        )
        try:
            cls_resp = await client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user",
                        "content": [image_message, {"type": "text", "text": classify_prompt}]}],
                temperature=0.1,
            )
            image_cls = cls_resp.choices[0].message.content.strip().lower()
            if "pictogram" in image_cls:
                image_cls = "pictogram"
            elif "flowchart" in image_cls:
                image_cls = "flowchart"
            else:
                image_cls = "other"
        except Exception as e:
            return {"image_cls": "error", "description": f"分类阶段出错: {str(e)}"}

        # ===== 描述 =====
        if image_cls == "pictogram":
            desc_prompt = (
                "这张图被识别为统计图表。请详细分析它：\n"
                "1. 提取图表的标题、横纵坐标含义和单位。\n"
                "2. 描述数据的整体趋势（如上升、下降、波动）。\n"
                "3. 请从统计图中提取数据，并以规范的二维 html 表格形式呈现。\n"
                "4. 总结图表传达的核心结论。"
            )
        elif image_cls == "flowchart":
            desc_prompt = (
                "这张图被识别为流程图或架构图。请详细分析它：\n"
                "1. 识别图中的起始节点和结束节点。\n"
                "2. 按照逻辑顺序描述各个步骤、决策点及其流转方向。\n"
                "3. 解释不同形状或颜色代表的含义（如果明显）。\n"
                "4. 请将流程图转换为对应的 mermaid 代码，确保精准还原结构。\n"
                "5. 总结该流程旨在解决什么问题或描述什么系统。"
            )
        else:
            desc_prompt = (
                "请详细描述这张图片的内容：\n"
                "1. 描述图中的主要主体（人物、物体、场景）。\n"
                "2. 描述环境背景、光影、颜色风格。\n"
                "3. 如果图片中有文字，请提取主要文字信息。\n"
                "4. 总结图片传达的整体氛围或信息。"
            )

        try:
            desc_resp = await client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user",
                        "content": [image_message, {"type": "text", "text": desc_prompt}]}],
            )
            description = desc_resp.choices[0].message.content
        except Exception as e:
            return {"image_cls": image_cls, "description": f"描述阶段出错: {str(e)}"}

        return {"image_cls": image_cls, "description": description}