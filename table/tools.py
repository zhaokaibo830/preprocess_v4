# -*- coding: utf-8 -*-
import os
import json
import base64
import io
import time
from PIL import Image  # 需要安装: pip install Pillow
from openai import OpenAI
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
            # print(f"图片已缩放: ({width}, {height}) -> {img.size}")

        # 将图片保存到内存缓冲区 (BytesIO)，而不是写入硬盘
        buffer = io.BytesIO()
        # 以此保持原格式保存（如PNG或JPEG），如果无法获取格式默认保存为PNG
        img_format = img.format if img.format else 'PNG'
        img.save(buffer, format=img_format)

        # 获取二进制数据并进行 Base64 编码
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

def analyze_image_content(image_path,table_html, config:str,api_key, base_url, model_name):
    def safe_json_parse(json_str):
        try:
            if "json"  in json_str:
                json_str=json_str.replace("json","")
            if "'''" in json_str:
                json_str = json_str.replace("'''", "")
            if "\n" in json_str:
                json_str=json_str.replace("\n","")
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
            return json_str

    # 1. 准备客户端
    client = OpenAI(
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
    # 第一步：k-value,description，kv_descprompt构写
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
        "1. 用简明的语言说明这是一张什么什么表格，如‘这是一张xx公司的员工工资表’，‘这是一张学生成绩表’\n"
        "2. 如果表格内容以数据为主，需要分析表格中如最大值，最小值等能反映数据特点的信息。\n"
        "3. 如果表格内容中涉及文字信息，则应对文字信息和数据进行简要描述。\n"
    )
    kv_desc_prompt = (
        "你是一个数据分析技术员，请仔细分析该表格的内容，并以结构化的JSON格式返回你的分析结果。JSON应包含以下键值：\n"
        "{\n"
        "\"kv\": \"[请仔细分析该表格的内容，并将其转化为键值对（key-value）的形式，最终输出为JSON格式,请确保不遗漏HTML中的任何一个单元格数据，每一个键（key）或值（value）应当对应表格中的某个单元格，不能将多个单元格的数据拼接成一个值，不要添加任何额外的解释性文字。相同的key不能出现在同一个dict里面且确保输出的JSON是有效且可以解析的。\n"
        "\"desc\": \"[用简明的语言说明这是一张什么什么表格，如‘这是一张xx公司的员工工资表’，‘这是一张学生成绩表’。如果表格内容以数据为主，需要分析表格中如最大值，最小值等能反映数据特点的信息。\n"
    )

    # ==========================================
    # 第二步：分别构建调用API函数
    # ==========================================
    def kv_api_call():
        try:
            kvalue_completion = client.chat.completions.create(
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
    def kv_desc_api_call():
        try:
            kv_desc_completion = client.chat.completions.create(
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
        kv=kv_desc_data["kv"]
        desc=kv_desc_data["desc"]
        return kv,desc
    # ==========================================
    # 第三步：创建if分支识别传入config
    # ==========================================   
    result = {}
    result["type"] = "table"
    #判断config中包含的功能，更新result并返回
    if "kv"in config and "desc"and "html" in config:
        result["kv_extract"],result["description"]=kv_desc_api_call()
        result["table_html"]=table_html
        return result
    elif "kv"in config and "desc" in config:
        result["kv_extract"],result["description"]=kv_desc_api_call()
        return result
    elif "desc"in config and "html" in config:
        description=desc_api_call()
        result["description"]=description
        result["table_html"]=table_html
        return result
    elif "kv"in config and "html" in config:
        kvalue=kv_api_call()
        result["kv_extract"]=kvalue
        result["table_html"]=table_html
        return result
    elif "kv"in config:
        kvalue=kv_api_call()
        result["kv_extract"]=kvalue
        return result
    elif "desc"in config:
        description=desc_api_call()
        result["description"]=description
        return result
    elif "html"in config:
        result["table_html"]=table_html
        return result


if __name__ == "__main__":
    # 配置参数
    IMG_PATH = "excel.png"
    API_KEY = "sk-46af479b8d7b4a1489ff47b084831a0c"  # 替换为你的真实 Key
    BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    MODEL = "qwen3-vl-8b-instruct"
    table_html = ""  # 如果有表格HTML，可以传入此参数
    config='desc'  # 可选 'kv', 'desc', 'html' 或它们的组合，如 'kv_desc_html'

    # 运行函数
    result = analyze_image_content(IMG_PATH, table_html, config, API_KEY, BASE_URL, MODEL)
    print(result)
    print(result.keys())
  
