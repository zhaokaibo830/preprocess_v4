# -*- coding: utf-8 -*-
import os
from openai import OpenAI
import json

import json
from openai import OpenAI
from openai import APIConnectionError, APIError, RateLimitError


def table_extract(table_html: str, api_key: str, base_url: str, model_name: str) -> dict:
    def safe_json_parse(json_str):
        try:
            if "json"  in json_str:
                json_str=json_str.replace("json","")
            if "'''" in json_str:
                json_str = json_str.replace("'''", "")
            if "\n" in json_str:
                json_str=json_str.replace("\n","")
            print("--------------------------------")
            print(json_str)
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
            return json_str

    def make_api_call(client, table_content, prompt, model):
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": table_content + "\n" + prompt},
                ],
                extra_body={"enable_thinking": False}
            )
            return completion.choices[0].message.content
        except APIConnectionError as e:
            print(f"处理表格时API连接错误: {e}")
            return {"error": "API连接失败", "details": str(e)}
        except RateLimitError as e:
            print(f"处理表格时API速率限制错误: {e}")
            return {"error": "处理表格时API请求超过速率限制", "details": str(e)}
        except APIError as e:
            print(f"处理表格时API错误: {e}")
            return {"error": "处理表格时API请求失败", "details": str(e)}
        except Exception as e:
            print(f"处理表格时未知错误: {e}")
            return {"error": "处理表格时未知错误", "details": str(e)}

    # 初始化客户端
    try:
        client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )
    except Exception as e:
        print(f"处理表格时OpenAI客户端初始化失败: {e}")
        return {
            "key_value": {"error": "处理表格时客户端初始化失败", "details": str(e)},
            "description": {"error": "处理表格时客户端初始化失败", "details": str(e)}
        }

    prompt_keyvalue = """
    给定内容是一个以HTML格式呈现的表格，请详细分析该表格的内容，并将其转化为键值对（key-value）的形式，最终输出为JSON格式。请确保不遗漏HTML中的任何一个单元格数据，每一个键（key）或值（value）应当对应表格中的某个单元格，不能将多个单元格的数据拼接成一个值。示例如下：

输入的HTML表格内容如下：
<table><tr><td rowspan=2 colspan=1>序号</td><td rowspan=1 colspan=3>学生信息</td></tr><tr><td rowspan=1 colspan=1>姓名</td><td rowspan=1 colspan=1>年龄</td><td rowspan=1 colspan=1>家庭地址</td></tr><tr><td rowspan=1 colspan=1>1</td><td rowspan=1 colspan=1>张三</td><td rowspan=1 colspan=1>23</td><td rowspan=1 colspan=1>北京</td></tr><tr><td rowspan=1 colspan=1>2</td><td rowspan=1 colspan=1>李四</td><td rowspan=1 colspan=1>12</td><td rowspan=1 colspan=1>上海</td></tr></table>
以上HTML表格内容转化为JSON格式。最终输出的JSON格式如下：
[{"序号":"1","学生信息":{"姓名":"张三","年龄":"23","家庭地址":"北京"}},{"序号":"2","学生信息":{"姓名":"李四","年龄":"12","家庭地址":"上海"}}]

要避免出现同一个dict里面出现相同的key，例如如下类似例子要避免出现：
[{"时段/h":"1","频率/Hz":"45.7857","时段/h":"17","频率/Hz":"46.9250"},{"时段/h":"10","频率/Hz":"47.4718","时段/h":"18","频率/Hz":"46.9588"}]

请按照这个格式输出JSON，不需要其他多余的解释，HTML中的每一个数据都要体现出来不能遗漏,每一个键（key）或值（value）应当对应表格中的某个单元格，不能将多个单元格的数据拼接成一个值,相同的key不能出现在同一个dict里面且确保输出的JSON是有效且可以解析的。

    """
    prompt_description = "请用一段话详细的描述此表格，不要遗漏任何数据。"

    # 调用API获取键值对结果
    keyvalue_result = make_api_call(client, table_html, prompt_keyvalue, model_name)

    # 调用API获取描述结果
    description_result = make_api_call(client, table_html, prompt_description, model_name)

    # 处理返回结果
    result = {}

    # 处理键值对结果
    if isinstance(keyvalue_result, dict) and "error" in keyvalue_result:
        result["key_value"] = keyvalue_result
    else:
        print("LLM输出：", keyvalue_result)
        result["key_value"] = safe_json_parse(keyvalue_result)
        print("==============================================")
        print(result["key_value"])

    # 处理描述结果
    if isinstance(description_result, dict) and "error" in description_result:
        result["description"] = description_result
    else:
        result["description"] = description_result

    return result


if __name__ == "__main__":
    table_html = """
    <table><tr><td rowspan=2 colspan=1>河段</td><td rowspan=2 colspan=1>冲淤量（万m）</td><td rowspan=1 colspan=3>冲淤厚度(m)</td></tr><tr><td rowspan=1 colspan=1>平均</td><td rowspan=1 colspan=1>最大</td><td rowspan=1 colspan=1>最大淤积部位及影响</td></tr><tr><td rowspan=1 colspan=1>全河段</td><td rowspan=1 colspan=1>-2267.6</td><td rowspan=1 colspan=1>-0.57</td><td rowspan=1 colspan=1>12.1</td><td rowspan=1 colspan=1>最大淤积厚度为12.1m，位于CY02（汇合口以下14km）深槽右侧，淤后高程133m左右，在通航及港口作业区域外，对通航无影响</td></tr><tr><td rowspan=1 colspan=1>朝天门汇口以上</td><td rowspan=1 colspan=1>-1881.7</td><td rowspan=1 colspan=1>-1.11</td><td rowspan=1 colspan=1>3.1</td><td rowspan=1 colspan=1>最大淤积厚度为3.1m，位于CY34（九龙坡河段）断面中部，淤后高程154m左右，对通航无影响</td></tr><tr><td rowspan=1 colspan=1>朝天门汇口以下</td><td rowspan=1 colspan=1>-96.2</td><td rowspan=1 colspan=1>-0.09</td><td rowspan=1 colspan=1>12.1</td><td rowspan=1 colspan=1>最大淤积厚度为12.1m，位于CY02（汇合口以下14km）深槽右侧，淤后高程133m左右，在通航及港口作业区域外，对通航无影响</td></tr><tr><td rowspan=1 colspan=1>嘉陵江</td><td rowspan=1 colspan=1>-289.7</td><td rowspan=1 colspan=1>-0.25</td><td rowspan=1 colspan=1>2.1</td><td rowspan=1 colspan=1>最大淤积厚度2.1m，位于CY43（嘉陵江，汇合口上游约1.2km）主槽内，淤后高程155.5m左右，对通航无影响</td></tr></table>
    """
    print(table_extract(table_html, api_key="sk-734ae048099b49b5b4c798155976522",
                        base_url="https://dashscope.aliyuncs.com/compatible-mode/v", model_name="qwen3-14b"))
