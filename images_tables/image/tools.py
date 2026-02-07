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
    """
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

def analyze_image_content(image_path, title, config, api_key, base_url, model_name):
    """
    分析图片内容：首先判断图片类型，然后使用针对性的提示词进行详细描述。
    增加了 raise 异常处理，确保系统级错误能被主函数捕获。
    """
    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
    )

    # 处理并编码图片
    try:
        base64_image = process_and_encode_image(image_path, max_size=800)
    except Exception as e:
        # 图片编码失败通常是本地IO问题，按原逻辑返回错误字典
        return {"image_cls": "error", "description": f"图片处理出错: {str(e)}"}

    image_message = {
        "type": "image_url",
        "image_url": {"url": f"data:image/png;base64,{base64_image}"},
    }

    # 内部统一调用工具，增加超时和异常抛出
    def _safe_api_call(messages, temp=0):
        try:
            completion = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=temp,
                timeout=(5.0, 60.0)  # 连接超时5s，响应超时60s（针对本地大模型较慢的情况）
            )
            return completion.choices[0].message.content.strip()
        except Exception as e:
            # 向上抛出异常，触发主循环的熔断
            raise RuntimeError(f"LLM调用失败: {str(e)}")

    # ==========================================
    # 第一步：图像分类 (Classification)
    # ==========================================
    classify_prompt = (
        "你是一个图像分类助手。请仔细观察这张图片，将其归类为以下三类之一：\n"
        "1. line graph (折线图)\n"
        "2. bar chart (柱状图)\n"
        "3. pie chart (饼图)\n"
        "4. 铭牌(涉及电力行业的铭牌)\n"
        "5. other (自然图像、人物、风景或其他)\n\n"
        "在分类时请务必仔细分析图片中的元素构成，确保分类准确请仅输出分类结果名词（line graph, bar chart, pie chart, 铭牌或 other），不要输出任何标点符号或其他解释性文字。"
    )

    image_cls_raw = _safe_api_call([
        {
            "role": "user",
            "content": [image_message, {"type": "text", "text": classify_prompt}],
        }
    ], temp=0.1)
    
    image_cls = image_cls_raw.lower()
    if "line graph" in image_cls:
        image_cls = "line graph"
    elif "bar chart" in image_cls:
        image_cls = "bar chart"
    elif "pie chart" in image_cls:
        image_cls = "pie chart"
    elif "铭牌" in image_cls:
        image_cls = "铭牌"
    else:
        image_cls = "other"

    # ==========================================
    # 第二步：prompt构建
    # ==========================================
    if image_cls == "line graph":
        desc_prompt = (
            "你是资深数据分析师，擅长捕捉数据的动态变化与趋势。请结合图片标题（若有）与折线图内容，输出一份约150字的分析报告。\n\n"
            "请先判断横轴属性，并按以下逻辑进行分析：\n"
            "1. **趋势与模式识别**：\n"
            "   - 若横轴为时间/序列：核心描述整体走势（如持续攀升、波动下降、周期性震荡或趋于平稳）。\n"
            "   - 若横轴为非序列类别：重点描述数值的分布形态与差异。\n"
            "2. **关键节点定位**：指出具有统计意义的“拐点”，即峰值、谷值或趋势发生逆转的时刻/位置。\n"
            "3. **多维对比**（若有多条线）：分析线条间的互动关系（如齐头并进、剪刀差扩大、某条线显著偏离），而非单独描述每一条线。\n\n"
            "要求：\n"
            "- 提炼核心结论，严禁枯燥的数据罗列。\n"
            "- 结尾必须包含：'本内容由AI生成，内容仅供参考'。"
        )
        html_prompt = (
            '请分析统计图中的数据，并从统计图中尽可能准确地提取数据，并以规范的HTML表格形式呈现：\n'
            "参考格式：<table><tr><th>...</th>...</tr></table>，若无法提取，请说明。\n"
            "输出应该值包含html表格代码，不要包含其他内容."
            "示例输出：'<table><tr><th>供电所名称</th><th>半年度最高最低收入额（单位：元）</th></tr><tr><td>文溪镇供电所</td><td>22000</td></tr><tr><td>昌东供电所</td><td>11000</td></tr><tr><td>洪都供电所</td><td>14000</td></tr><tr><td>解放供电所</td><td>15000</td></tr><tr><td>李家供电所</td><td>34000</td></tr><tr><td>罗家供电所</td><td>12000</td></tr><tr><td>青云供电所</td><td>21000</td></tr><tr><td>扬子洲供电所</td><td>6000</td></tr></table>'\n"
        )
    elif image_cls == "bar chart":
        desc_prompt = (
            "你是资深商业数据分析师，擅长通过柱状图挖掘核心趋势。请结合图片标题（若有）与图表内容，输出一份约150字的精炼分析报告。\n\n"
            "在进行内容分析前，应先分析并统计柱状图的数据信息，将类别，图例和纵坐标反映的信息进行严格准确的对应，确保后续分析建立在良好的数据基础上。\n"
            "分析应建立在已得到的数据信息基础上，对数据进行分析的逻辑如下：\n"
            "1. **宏观概括**：一句话定义图表主题及反映的核心信息。\n"
            "2. **维度分析**：\n"
            "   - 若含图例：基于颜色区分对比不同组别（如同比/环比/竞品），分析组间差距及变化趋势。\n"
            "   - 若无图例：直接分析类别的分布特征（如长尾分布、正态分布或两极分化）。\n"
            "3. **关键洞察**：指出极值（最高/最低）、显著的断层或异常点，不要逐一罗列数值，而是总结“头部效应”或“均衡性”。\n\n"
            "输出要求：\n"
            "- 语言专业简练，严禁逐项报数。\n"
            "- 结尾必须包含：'本内容由AI生成，内容仅供参考'。"
        )
        html_prompt = (
            '请分析统计图中的数据，并从统计图中尽可能准确地提取数据，并以规范的HTML表格形式呈现：\n'
            "参考格式：<table><tr><th>...</th>...</tr></table>，若无法提取，请说明。\n"
            "输出应该值包含html表格代码，不要包含其他内容."
            "示例输出：'<table><tr><th>供电所名称</th><th>半年度最高最低收入额（单位：元）</th></tr><tr><td>文溪镇供电所</td><td>22000</td></tr><tr><td>昌东供电所</td><td>11000</td></tr><tr><td>洪都供电所</td><td>14000</td></tr><tr><td>解放供电所</td><td>15000</td></tr><tr><td>李家供电所</td><td>34000</td></tr><tr><td>罗家供电所</td><td>12000</td></tr><tr><td>青云供电所</td><td>21000</td></tr><tr><td>扬子洲供电所</td><td>6000</td></tr></table>'\n"
        )
    elif image_cls == "pie chart":
        desc_prompt = (
            "你是擅长数据解读的统计专家，能够从图表中提取关键洞察。给定内容为一张饼图和图片标题，请结合图片标题(若图片标题不为空)对提供的饼图进行简要分析，重点关注以下方面：\n"
            "宏观概括：一句话定义图表主题及反映的核心信息。\n"
            "- 主要组成部分及其占比排序\n"
            "- 最大和最小占比的突出说明\n"
            "- 是否有主导部分（超过50%）\n"
            "- 各部分之间的相对关系\n"
            "要求：分析控制在120字左右，使用专业表述，避免简单重复百分比，描述最后增添'本内容由AI生成，内容仅供参考'。\n"
        )
        html_prompt = (
            '请分析统计图中的数据，并从统计图中尽可能准确地提取数据，并以规范的HTML表格代码形式呈现,请务必注意以下要点：\n'
            "1.输出应该值包含html表格，不要包含其他内容."
            "2.**禁止**在html表格内部使用任何转义字符（如`\\n`、`\\t`）。"
            "示例输出：'<table><tr><th>供电所名称</th><th>半年度最高最低收入额（单位：元）</th></tr><tr><td>文溪镇供电所</td><td>22000</td></tr><tr><td>昌东供电所</td><td>11000</td></tr><tr><td>洪都供电所</td><td>14000</td></tr><tr><td>解放供电所</td><td>15000</td></tr><tr><td>李家供电所</td><td>34000</td></tr><tr><td>罗家供电所</td><td>12000</td></tr><tr><td>青云供电所</td><td>21000</td></tr><tr><td>扬子洲供电所</td><td>6000</td></tr></table>'\n"
        )
    elif image_cls == "铭牌":
        desc_prompt = (
            "你是一个电力设备铭牌信息分析专家。你的任务是从用户提供的电力设备铭牌图片中准确识别并提取所有关键信息。\n"
            "### 重要指令 ###\n"
            "1.  **输出格式**：你的输出必须是且仅是一个**纯净的JSON对象**。\n"
            "2.  **内容要求**：确保每个字段名称和对应的数值都准确无误地反映铭牌上的内容。\n"
            "3.  **严格禁止**："
            "   - **禁止**在JSON字符串内部使用任何转义字符（如`\\n`、`\\t`）。"
            "   - **禁止**在JSON对象外包裹任何额外的引号或说明文字。"
            "   - **禁止**对JSON对象进行任何美化或格式化（不要换行和缩进）。请输出紧凑的一行JSON。\n"
            "4.  **示例**：正确的输出格式应为：`{\"设备名称\": \"低压抽出式开关柜\", \"型号\": \"GCS\", ...}`"
        )
    else:  # other
        desc_prompt = (
            "你是一位通用的图片描述专家。请对这张图片进行简要但全面的描述\n"
            "首先用简明的语言说明这是一张什么类型的图片（例如，'这是一张工人施工时的照片'，'这是一张产品效果图'等）\n"
            "描述图片中的主要主体（人物、物体、场景），以及它们在做什么或呈现出什么状态,如果图片中包含醒目的文字，请提取这些关键文字，并简要概括其传达的核心信息或功能\n"
            "要求：描述控制在100字以内，语言流畅自然，避免冗长和重复，描述最后增添'本内容由AI生成，内容仅供参考'。\n"
        )

    # ==========================================
    # 第三步 & 第四步：构建结果
    # ==========================================
    result = {}
    if 'cls' in config:
        result["type"] = image_cls

    if 'desc' in config:
        # 将 title 加入 content
        desc_content = [image_message]
        if title:
            desc_content.append({"type": "text", "text": f"图片标题: {title}"})
        desc_content.append({"type": "text", "text": desc_prompt})
        
        description = _safe_api_call([{"role": "user", "content": desc_content}])
        result['desc'] = description

    if "html" in config and image_cls in ["line graph", "bar chart", "pie chart"]:
        html_res = _safe_api_call([
            {
                "role": "user",
                "content": [image_message, {"type": "text", "text": html_prompt}],
            }
        ])
        result['html'] = html_res

    return result



# ==========================================
# 调用示例
# ==========================================
if __name__ == "__main__":
    # 配置参数
    IMG_PATH = "./datatest/1_3.png"
    API_KEY = "sk-46af479b8d7b4a1489ff47b084831a0c"  # 替换为你的真实 Key
    BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    MODEL = "qwen3-vl-8b-instruct"
    config='html,desc,cls'  # 可选 'cls', 'desc', 'html' 或它们的组合，如 'cls_desc_html'
    title=""
    # 运行函数
    result = analyze_image_content(IMG_PATH,title,config, API_KEY, BASE_URL, MODEL)

    # 打印结果
    print(result)
  