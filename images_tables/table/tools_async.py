import asyncio
import json
from openai import AsyncOpenAI          # ① 唯一区别：异步客户端
from openai import (
    APIConnectionError, APIError, RateLimitError
)
semaphore_table = asyncio.Semaphore(10)
# --------------- 内部工具 ---------------
def safe_json_parse(json_str: str):
    """与旧版完全一致的脏字符串清洗"""
    if "json" in json_str:
        json_str = json_str.replace("json", "")
    if "'''" in json_str:
        json_str = json_str.replace("'''", "")
    if "\n" in json_str:
        json_str = json_str.replace("\n", "")
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return json_str


# --------------- 单次异步调用 ---------------
async def _make_api_call_async(client: AsyncOpenAI,
                               table_content: str,
                               prompt: str,
                               model: str):
    """异步请求，超时/重试由外层统一控制"""
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
    except (APIConnectionError, RateLimitError, APIError) as e:
        # 返回 dict 方便外层识别
        return {"error": e.__class__.__name__, "details": str(e)}
    except Exception as e:
        return {"error": "Unknown", "details": str(e)}


# --------------- 对外唯一接口 ---------------
async def table_extract_async(table_html: str,
                              api_key: str,
                              base_url: str,
                              model_name: str) -> dict:
    async with semaphore_table:
        """
        完全对标旧版 table_extract，只是变成 async，可配合 asyncio.gather 并发。
        """
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)

        prompt_keyvalue = """
        给定内容是一个以HTML格式呈现的表格，请详细分析该表格的内容，并将其转化为键值对（key-value）的形式，最终输出为JSON格式。请确保不遗漏HTML中的任何一个单元格数据，每一个键（key）或值（value）应当对应表格中的某个单元格，不能将多个单元格的数据拼接成一个值。示例如下：

    输入的HTML表格内容如下：
    <table><tr><td rowspan=2 colspan=1>序号</td><td rowspan=1 colspan=3>学生信息</td></tr><tr><td rowspan=1 colspan=1>姓名</td><td rowspan=1 colspan=1>年龄</td><td rowspan=1 colspan=1>家庭地址</td></tr><tr><td rowspan=1 colspan=1>1</td><td rowspan=1 colspan=1>张三</td><td rowspan=1 colspan=1>23</td><td rowspan=1 colspan=1>北京</td></tr><tr><td rowspan=1 colspan=1>2</td><td rowspan=1 colspan=1>李四</td><td rowspan=1 colspan=1>12</td><td rowspan=1 colspan=1>上海</td></tr></table>
        以上HTML表格内容转化为JSON格式。最终输出的JSON格式如下：
        [{"序号":"1","学生信息":{"姓名":"张三","年龄":"23","家庭地址":"北京"}},{"序号":"2","学生信息":{"姓名":"李四","年龄":"12","家庭地址":"上海"}}]

        请按照这个格式输出JSON，不需要其他多余的解释，HTML中的每一个数据都要体现出来不能遗漏,每一个键（key）或值（value）应当对应表格中的某个单元格，不能将多个单元格的数据拼接成一个值,且确保输出的JSON是有效且可以解析的。
        """
        prompt_description = "请用一段话详细的描述此表格，不要遗漏任何数据。"

        # 并发跑两次 LLM 请求（key_value + description）
        keyvalue_result, description_result = await asyncio.gather(
            _make_api_call_async(client, table_html, prompt_keyvalue, model_name),
            _make_api_call_async(client, table_html, prompt_description, model_name)
        )

        # 统一包装结果，与旧版格式完全一致
        result = {}
        if isinstance(keyvalue_result, dict) and "error" in keyvalue_result:
            result["key_value"] = keyvalue_result
        else:
            result["key_value"] = safe_json_parse(keyvalue_result)

        if isinstance(description_result, dict) and "error" in description_result:
            result["description"] = description_result
        else:
            result["description"] = description_result

        return result