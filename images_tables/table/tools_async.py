# -*- coding: utf-8 -*-
import asyncio
import json
from openai import AsyncOpenAI
from openai import APIConnectionError, APIError, RateLimitError

# 控制“表格级别”的并发
semaphore_table = asyncio.Semaphore(10)


async def table_extract_async(
    table_html: str,
    api_key: str,
    base_url: str,
    model_name: str
) -> dict:
    """
    并行版 table_extract
    - 接口参数 & 返回结构 与串行版完全一致
    - 仅执行方式由串行 → 并行
    """

    # ---------------- 工具函数（行为完全一致） ----------------
    def safe_json_parse(json_str):
        try:
            if "json" in json_str:
                json_str = json_str.replace("json", "")
            if "'''" in json_str:
                json_str = json_str.replace("'''", "")
            if "\n" in json_str:
                json_str = json_str.replace("\n", "")
            print("--------------------------------")
            print(json_str)
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
            return json_str

    async def make_api_call(client, table_content, prompt, model):
        try:
            completion = await client.chat.completions.create(
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

    # ---------------- 主逻辑 ----------------
    async with semaphore_table:
        # 初始化客户端
        try:
            client = AsyncOpenAI(
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
        [{"时段/h":"1","频率/Hz":"45.7857","时段/h":"17","频率/Hz":"46.9250"}]

        请按照这个格式输出JSON，不需要其他多余的解释，HTML中的每一个数据都要体现出来不能遗漏,
        每一个键（key）或值（value）应当对应表格中的某个单元格，
        相同的key不能出现在同一个dict里面且确保输出的JSON是有效且可以解析的。
        """

        prompt_description = "请用一段话详细的描述此表格，不要遗漏任何数据。"

        # -------- 并发执行两次 LLM 调用 --------
        keyvalue_result, description_result = await asyncio.gather(
            make_api_call(client, table_html, prompt_keyvalue, model_name),
            make_api_call(client, table_html, prompt_description, model_name),
        )

        # -------- 结果封装（完全一致） --------
        result = {}

        if isinstance(keyvalue_result, dict) and "error" in keyvalue_result:
            result["key_value"] = keyvalue_result
        else:
            print("LLM输出：", keyvalue_result)
            result["key_value"] = safe_json_parse(keyvalue_result)
            print("==============================================")
            print(result["key_value"])

        if isinstance(description_result, dict) and "error" in description_result:
            result["description"] = description_result
        else:
            result["description"] = description_result

        await client.close()
        return result
