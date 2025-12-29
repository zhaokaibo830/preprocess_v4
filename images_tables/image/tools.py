from openai import OpenAI
import os
import base64
import io
from PIL import Image  # 需要安装: pip install Pillow


def process_and_encode_image(image_path, max_size=800):
    """
    读取本地图片，限制最大长宽不超过 max_size，并转换为 Base64 编码。

    Args:
        image_path (str): 图片路径
        max_size (int): 图片长或宽的最大像素值

    Returns:
        str: Base64 编码字符串
    """
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
            # print(f"图片已缩放: ({width}, {height}) -> {img.size}")

        # 将图片保存到内存缓冲区 (BytesIO)，而不是写入硬盘
        buffer = io.BytesIO()
        # 以此保持原格式保存（如PNG或JPEG），如果无法获取格式默认保存为PNG
        img_format = img.format if img.format else 'PNG'
        img.save(buffer, format=img_format)

        # 获取二进制数据并进行 Base64 编码
        return base64.b64encode(buffer.getvalue()).decode("utf-8")


def analyze_image_content(image_path, api_key, base_url, model_name):
    """
    分析图片内容：首先判断图片类型，然后使用针对性的提示词进行详细描述。
    """

    # 1. 准备客户端
    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
    )

    # 2. 处理并编码图片 (此处加入了缩放逻辑)
    try:
        # 默认限制 800px，你可以通过参数修改
        base64_image = process_and_encode_image(image_path, max_size=800)
    except Exception as e:
        return {"image_cls": "error", "description": f"图片处理出错: {str(e)}"}

    # 构建通用的图片消息体
    # 注意：这里为了通用性，URL头我们简单使用 data:image/png，
    # 实际应用中大部分模型对 data:image/jpeg 也是兼容的，或者你可以根据文件后缀动态调整
    image_message = {
        "type": "image_url",
        "image_url": {"url": f"data:image/png;base64,{base64_image}"},
    }

    # ==========================================
    # 第一步：图像分类 (Classification)
    # ==========================================
    classify_prompt = (
        "你是一个图像分类助手。请仔细观察这张图片，将其归类为以下三类之一：\n"
        "1. pictogram (统计图表，如柱状图、折线图、饼图等)\n"
        "2. flowchart (流程图等)\n"
        "3. other (自然图像、人物、风景或其他)\n\n"
        "请仅输出分类结果的英文单词（pictogram, flowchart, 或 other），不要输出任何标点符号或其他解释性文字。"
    )

    try:
        cls_completion = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "user",
                    "content": [image_message, {"type": "text", "text": classify_prompt}],
                }
            ],
            temperature=0.1,
        )
        image_cls = cls_completion.choices[0].message.content.strip().lower()

        # 简单的容错处理
        if "pictogram" in image_cls:
            image_cls = "pictogram"
        elif "flowchart" in image_cls:
            image_cls = "flowchart"
        else:
            image_cls = "other"

    except Exception as e:
        return {"image_cls": "error", "description": f"分类阶段出错: {str(e)}"}

    # ==========================================
    # 第二步：针对性描述 (Description)
    # ==========================================
    if image_cls == "pictogram":
        desc_prompt = (
            "这张图被识别为统计图表。请详细分析它：\n"
            "1. 提取图表的标题、横纵坐标含义和单位。\n"
            "2. 描述数据的整体趋势（如上升、下降、波动）。\n"
            "3. 请从统计图中提取数据，并以规范的二维html格式的表格形式进行呈现。\n"
            "4. 总结图表传达的核心结论。"
        )
    elif image_cls == "flowchart":
        desc_prompt = (
            "这张图被识别为流程图或架构图。请详细分析它：\n"
            "1. 识别图中的起始节点和结束节点。\n"
            "2. 按照逻辑顺序描述各个步骤、决策点及其流转方向。\n"
            "3. 解释不同形状或颜色代表的含义（如果明显）。\n"
            "4. 请将给定的流程图转换为对应的 mermaid 代码，确保生成的代码能够精准无误地呈现流程图的结构。\n"
            "5. 总结该流程旨在解决什么问题或描述什么系统。"
        )
    else:  # other
        desc_prompt = (
            "请详细描述这张图片的内容：\n"
            "1. 描述图中的主要主体（人物、物体、场景）。\n"
            "2. 描述环境背景、光影、颜色风格。\n"
            "3. 如果图片中有文字，请提取主要文字信息。\n"
            "4. 总结图片传达的整体氛围或信息。"
        )

    try:
        desc_completion = client.chat.completions.create(
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
        return {"image_cls": image_cls, "description": f"描述阶段出错: {str(e)}"}

    return {
        "image_cls": image_cls,
        "description": description
    }


# ==========================================
# 调用示例
# ==========================================
if __name__ == "__main__":
    # 配置参数
    IMG_PATH = "img_1.png"
    API_KEY = "sk-734ae048099b49b5b4c7981559765228"  # 替换为你的真实 Key
    BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    MODEL = "qwen3-vl-8b-instruct"

    # 运行函数
    result = analyze_image_content(IMG_PATH, API_KEY, BASE_URL, MODEL)

    # 打印结果
    print("-" * 30)
    print(f"图片类型: {result['image_cls']}")
    print("-" * 30)
    print(f"理解结果:\n{result['description']}")
    print("-" * 30)