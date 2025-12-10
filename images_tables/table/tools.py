import os
from openai import OpenAI
import json

import json
from openai import OpenAI
from openai import APIConnectionError, APIError, RateLimitError


def table_extract(table_html: str, api_key: str, base_url: str, model_name: str) -> dict:
    def safe_json_parse(json_str):
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
            return {"error": "JSON解析失败", "raw_content": json_str}

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
    给定内容是一个以HTML格式呈现的表格，请深入理解该表格内容，并将其以键值对（key和value）的形式进行整理，最终输出为JSON格式，示例如下：{“姓名”: “李四”, “年龄”: 26},只需要输出JSON,以{开始，以}结束，不需要其他多余解释。
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
        result["key_value"] = safe_json_parse(keyvalue_result)

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
