import json
import io
import time
from openai import OpenAI

def table_extract(table_html: str, title, config, api_key: str, base_url: str, model_name: str) -> dict:
    # ==========================================
    # 第一步：工具函数
    # ========================================== 
    def safe_json_parse(json_str):
        try:
            if "json" in json_str:
                json_str = json_str.replace("json", "")
            if "'''" in json_str:
                json_str = json_str.replace("'''", "")
            if "```" in json_str: # 补充：通常markdown块是```
                json_str = json_str.replace("```", "")
            if "\n" in json_str:
                json_str = json_str.replace("\n", "")
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
            return json_str

    # ==========================================
    # 第二步：统一的 API 调用封装（带超时和异常上抛）
    # ========================================== 
    client = OpenAI(api_key=api_key, base_url=base_url)

    def _safe_api_call(user_content):
        try:
            completion = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": user_content},
                ],
                extra_body={"enable_thinking": False},
                timeout=(20.0, 600)  # 连接5秒，响应60秒超时
            )
            return completion.choices[0].message.content
        except Exception as e:
            # 核心修改：向上抛出异常，触发主循环熔断
            raise RuntimeError(f"表格处理API调用失败: {str(e)}")

    # ==========================================
    # 第三步：构建 Prompt (保留原文)
    # ========================================== 
    prompt_kv = """
    给定内容是一个以HTML格式呈现的表格，请详细分析该表格的内容，并将其转化为键值对（key-value）的形式，最终输出为JSON格式。请确保不遗漏HTML中的任何一个单元格数据，每一个键（key）或值（value）应当对应表格中的某个单元格，不能将多个单元格的数据拼接成一个值。示例如下：

输入的HTML表格内容如下：
<table><tr><td rowspan=2 colspan=1>序号</td><td rowspan=1 colspan=3>学生信息</td></tr><tr><td rowspan=1 colspan=1>姓名</td><td rowspan=1 colspan=1>年龄</td><td rowspan=1 colspan=1>家庭地址</td></tr><tr><td rowspan=1 colspan=1>1</td><td rowspan=1 colspan=1>张三</td><td rowspan=1 colspan=1>23</td><td rowspan=1 colspan=1>北京</td></tr><tr><td rowspan=1 colspan=1>2</td><td rowspan=1 colspan=1>李四</td><td rowspan=1 colspan=1>12</td><td rowspan=1 colspan=1>上海</td></tr></table>
以上HTML表格内容转化为JSON格式。最终输出的JSON格式如下：
[{"序号":"1","学生信息":{"姓名":"张三","年龄":"23","家庭地址":"北京"}},{"序号":"2","学生信息":{"姓名":"李四","年龄":"12","家庭地址":"上海"}}]

要避免出现同一个dict里面出现相同的key，例如如下类似例子要避免出现：
[{"时段/h":"1","频率/Hz":"45.7857","时段/h":"17","频率/Hz":"46.9250"},{"时段/h":"10","频率/Hz":"47.4718","时段/h":"18","频率/Hz":"46.9588"}]

请按照这个格式输出JSON，不需要其他多余的解释，HTML中的每一个数据都要体现出来不能遗漏,每一个键（key）或值（value）应当对应表格中的某个单元格，不能将多个单元格的数据拼接成一个值,相同的key不能出现在同一个dict里面且确保输出的JSON是有效且可以解析的。
    """
    
    prompt_desc = (
        "你是一个数据分析技术员，给定内容是表格的HTML格式和表格标题，请仔细分析该以HTML格式呈现的表格的内容，并结合表格标题（若不为空）分析并描述该表格传达的信息，需注意以下要点\n"
        "1. 用简明的语言说明这是一张什么什么表格，如‘这是一张xx公司的员工工资表’，‘这是一张学生成绩表’\n"
        "2. 如果表格内容以数据为主，需要分析表格中如最大值，最小值等能反映数据特点的信息。\n"
        "3. 如果表格内容中涉及文字信息，则应对文字信息和数据进行简要描述。\n"
    )

    # ==========================================
    # 第四步：执行逻辑与分支识别
    # ==========================================   
    result = {}
    result["type"] = "table"

    # 执行 KV 提取
    if "kv" in config:
        kv_raw = _safe_api_call(table_html + "\n" + prompt_kv)
        result["key_value"] = safe_json_parse(kv_raw)

    # 执行描述提取
    if "desc" in config:
        desc_raw = _safe_api_call(table_html + "\n" + (title if title else "") + "\n" + prompt_desc)
        result["description"] = desc_raw

    # 执行 HTML 保留
    if "html" in config:
        result["table_html"] = table_html

    return result


if __name__ == "__main__":
    # 配置参数
    API_KEY = "sk-46af479b8d7b4a1489ff47b084831a0c"  # 替换为你的真实 Key
    BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    MODEL = "qwen3-vl-8b-instruct"
    table_html = "<table><tr><th>岗位名称</th><th>占比</th></tr><tr><td>监理员</td><td>41%</td></tr><tr><td>资料员</td><td>13%</td></tr><tr><td>总监理工程师</td><td>7%</td></tr><tr><td>总监代表</td><td>8%</td></tr><tr><td>专业监理工程师</td><td>18%</td></tr><tr><td>安全监理工程师</td><td>13%</td></tr></table>"
    config='desc'  # 可选 'kv', 'desc', 'html' 或它们的组合，如 'kv_desc_html'
    title=""
    # 运行函数
    result = table_extract(table_html, title,config, API_KEY, BASE_URL, MODEL)
    print(result)
  
  