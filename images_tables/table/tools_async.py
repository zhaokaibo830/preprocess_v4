# -*- coding: utf-8 -*-
import json
import asyncio
from openai import AsyncOpenAI
from openai import APIConnectionError, APIError, RateLimitError

async def analyze_table_content_async(
    table_html: str, 
    title: str, 
    config: str, 
    api_key: str, 
    base_url: str, 
    model_name: str,
    semaphore=None
) -> dict:
    """
    并发处理表格提取的异步主函数
    """
    if semaphore:
        async with semaphore:
            return await _table_extract_impl(table_html, title, config, api_key, base_url, model_name)
    else:
        return await _table_extract_impl(table_html, title, config, api_key, base_url, model_name)

async def _table_extract_impl(table_html, title, config, api_key, base_url, model_name) -> dict:
    # ==========================================
    # 第一步：工具函数
    # ========================================== 
    def safe_json_parse(json_str):
        if not isinstance(json_str, str):
            return json_str
        try:
            # 清洗 markdown 标签和换行
            cleaned = json_str.replace("json", "").replace("'''", "").replace("```", "").strip()
            # 处理可能的换行符污染
            cleaned = "".join(cleaned.splitlines())
            return json.loads(cleaned)
        except Exception as e:
            print(f"JSON解析错误: {e}")
            return json_str

    # ==========================================
    # 第二步：初始化异步客户端
    # ========================================== 
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    # ==========================================
    # 第三步：构建 Prompt
    # ========================================== 
    prompt_kv = """
    给定内容是一个以HTML格式呈现的表格，请详细分析该表格的内容，并将其转化为键值对（key-value）的形式，最终输出为JSON格式。
    请确保不遗漏HTML中的任何一个单元格数据，每一个键（key）或值（value）应当对应表格中的某个单元格。
    避免在同一个dict中出现重复的key。
    请直接输出JSON内容，不要任何解释。
    """

    prompt_desc = (
        "你是一个数据分析技术员，给定内容是表格的HTML格式和表格标题，请仔细分析并描述该表格传达的信息：\n"
        "1. 用简明的语言说明这是一张什么类型的表格。\n"
        "2. 分析表格中如最大值、最小值等能反映数据特点的信息。\n"
        "3. 对应文字信息和数据进行简要描述。\n"
    )

    # ==========================================
    # 第四步：定义异步 API 调用任务
    # ========================================== 
    async def kv_api_call():
        try:
            resp = await client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": f"{table_html}\n{prompt_kv}"}
                ],
                temperature=0.1,
                extra_body={"enable_thinking": False}
            )
            return safe_json_parse(resp.choices[0].message.content)
        except (APIConnectionError, RateLimitError, APIError) as e:
            return {"error": "API请求失败", "details": str(e)}
        except Exception as e:
            return {"error": "未知错误", "details": str(e)}

    async def desc_api_call():
        try:
            # 包含 title 信息
            full_content = f"表格HTML: {table_html}\n表格标题: {title}\n{prompt_desc}"
            resp = await client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": full_content}
                ],
                extra_body={"enable_thinking": False}
            )
            return resp.choices[0].message.content
        except Exception as e:
            return f"描述获取失败: {str(e)}"

    # ==========================================
    # 第五步：并发执行任务 (关键并发逻辑)
    # ========================================== 
    tasks = {}
    
    # 只有当需要时才创建协程任务
    if "kv" in config:
        tasks["key_value"] = kv_api_call()
    
    if "desc" in config:
        tasks["description"] = desc_api_call()

    # 使用 gather 并行执行 kv 和 desc 调用
    if tasks:
        task_names = list(tasks.keys())
        task_objects = list(tasks.values())
        api_responses = await asyncio.gather(*task_objects)
        
        # 将结果映射回字典
        execution_results = dict(zip(task_names, api_responses))
    else:
        execution_results = {}

    # ==========================================
    # 第六步：组装最终结果
    # ========================================== 
    result = {"type": "table"}
    
    if "kv" in config:
        result["key_value"] = execution_results.get("key_value")
    
    if "desc" in config:
        result["description"] = execution_results.get("description")
        
    if "html" in config:
        result["table_html"] = table_html

    return result

# ==========================================
# 调用示例
# ==========================================
async def main():
    # 模拟输入
    HTML_DATA = "<table><tr><td>项目</td><td>数值</td></tr><tr><td>收入</td><td>100</td></tr></table>"
    TITLE = "2025年财务报表"
    CONFIG = "kv,desc,html"
    API_KEY = "your_api_key"
    BASE_URL = "[https://api.openai.com/v1](https://api.openai.com/v1)"
    MODEL = "gpt-4-turbo"

    # 限制最大并发数为 10
    sem = asyncio.Semaphore(10)

    result = await table_extract_async(HTML_DATA, TITLE, CONFIG, API_KEY, BASE_URL, MODEL, semaphore=sem)
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    asyncio.run(main())