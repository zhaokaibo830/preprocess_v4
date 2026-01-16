from openai import OpenAI
import os
import base64
import io
import time
from PIL import Image  # 需要安装: pip install Pillow
import json

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


def analyze_image_content(image_path,config, api_key, base_url, model_name):
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
    image_message = {
        "type": "image_url",
        "image_url": {"url": f"data:image/png;base64,{base64_image}"},
    }

    # ==========================================
    # 第一步：图像分类 (Classification)
    # ==========================================
    def cls():
        classify_prompt = (
            "你是一个图像分类助手。请仔细观察这张图片，将其归类为以下三类之一：\n"
            "1. pictogram (统计图表，如柱状图、折线图、饼图等)\n"
            "2. other (自然图像、人物、风景或其他)\n\n"
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
        return image_cls

    # ==========================================
    # 第二步：prompt构建(desc_prompt,html_prompt)
    # ==========================================
    image_cls=cls()
    if image_cls == "pictogram":
        desc_prompt = (
    "你是一位专业的统计图表分析专家。请仔细分析这张统计图表，给出统计图表的相应描述，要点如下：提取图表的标题、横纵坐标含义和单位,以文字形式给出.描述数据的整体趋势（如上升、下降、波动）,若描述中涉及估计数据值，请在描述中增添'所得数据通过估算得到，请酌情参考'的说明，请确保你的回答简要精炼，不要包含额外的解释性文字。]\",\n"
        )
        html_prompt=(
            '请从统计图中尽可能准确地提取数据，并以规范的HTML表格形式呈现。例如：<table><tr><th>...</th>...</tr></table>，若无法提取，请说明，请在输出的html表格前加上"所得数据通过估算得到，请酌情参考"的说明。'
        )
    else:  # other
        desc_prompt = (
           "你是一位通用的图片描述专家。请对这张图片进行简要但全面的描述\n"
           "首先用简明的语言说明这是一张什么类型的图片（例如，'这是一张电路图'，'这是一张工人施工时的照片'，'这是一张产品效果图'等）\n"
           "描述图片中的主要主体（人物、物体、场景），以及它们在做什么或呈现出什么状态,如果图片中包含醒目的文字，请提取这些关键文字，并简要概括其传达的核心信息或功能\n"
           "如果图片涉及电力行业的专业内容和数据，请提取数据并对数据的含义进行解释，尽量使用电力行业的术语进行描述。\n"
           "如果图片与电力行业不相关，请不要提及电力行业"
        )
# ==========================================
# 第三步：构建函数调用API获取结果
# ==========================================
    def desc_api_call():
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
            return {"desc_completion": "error", "description": f"描述阶段出错: {str(e)}"}
        return description
    def html_api_call():
        try:
            html_completion = client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [image_message, {"type": "text", "text": html_prompt}],
                    }
                ],
            )
            html = html_completion.choices[0].message.content
        except Exception as e:
            return {"html_completion": "error", "description": f"html提取阶段出错: {str(e)}"}
        return html
# ==========================================
# 第四步：创建if分支识别传入config
# ==========================================
    result = {}
    if config=='cls':
            result["type"] = image_cls
            return result
    if config=='desc'and image_cls=="pictogram":
            description=desc_api_call()
            result['desc']=description
            return result
    elif config=='html'and image_cls=="pictogram":
            html=html_api_call()
            result['html']=html
            return result
    elif 'cls' in config and 'desc' in config and 'html' in config and image_cls=="pictogram":
            description=desc_api_call()
            html=html_api_call()
            result['type']=image_cls
            result['desc']=description
            result['html']=html
            return result
    elif 'cls' in config and 'desc' in config and image_cls=="pictogram":
            description=desc_api_call()
            result['type']=image_cls
            result['desc']=description
            return result
    elif 'cls' in config and 'html' in config and image_cls=="pictogram":
            html=html_api_call()
            result['type']=image_cls
            result['html']=html
            return result
    elif 'desc' in config and 'html' in config and image_cls=="pictogram":
            description=desc_api_call()
            html=html_api_call()
            result['desc']=description
            result['html']=html
            return result
    elif image_cls!="pictogram" and config=='desc':
            description=desc_api_call()
            result['desc']=description
            return result
    elif image_cls!="pictogram" and 'cls' in config and 'desc' in config:
            description=desc_api_call()
            result['type']=image_cls
            result['desc']=description
            return result



# ==========================================
# 调用示例
# ==========================================
if __name__ == "__main__":
    # 配置参数
    IMG_PATH = "不要乱看我的电脑.jpg"
    API_KEY = "sk-46af479b8d7b4a1489ff47b084831a0c"  # 替换为你的真实 Key
    BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    MODEL = "qwen3-vl-8b-instruct"
    config='desc'  # 可选 'cls', 'desc', 'html' 或它们的组合，如 'cls_desc_html'
    # 运行函数
    result = analyze_image_content(IMG_PATH,config, API_KEY, BASE_URL, MODEL)

    # 打印结果
    print(result)
  