import re
import json
import os
import sys
from openai import OpenAI
from typing import List, Dict, Any

# ================= 配置区域 =================
CONFIG = {
    # LLM API 配置
    "LLM_API_KEY": "sk-92d983e317d24d2da8ef19ddd2359008",
    "LLM_BASE_URL": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "LLM_MODEL": "qwen3-14b",

    # 文件路径配置
    "INPUT_JSON_PATH": "xxxx.json",
    "OUTPUT_JSON_PATH": "processed_with_levels.json",
}
# ===============================================


# ================= 辅助函数 =================

def load_json_data(path: str) -> Dict[str, Any]:
    """读取完整的 JSON 文件结构"""
    if not os.path.exists(path):
        print(f"Error: Input file not found {path}")
        sys.exit(1)
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json_data(data: Any, path: str):
    """保存 JSON 数据"""
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def count_leading_hashes(s: str) -> int:
    """计算 Markdown 标题层级"""
    match = re.match(r'^(#+)', s)
    return len(match.group(1)) if match else 0

def filter_string(input_string: str) -> str:
    """仅保留汉字和字母，用于标题模糊匹配"""
    pattern = re.compile(r'[\u4e00-\u9fffA-Za-z]')
    return ''.join(pattern.findall(input_string))

def extract_text_content(para: Dict[str, Any]) -> str:
    """从嵌套的段落结构中提取文本内容"""
    text_parts = []
    if 'lines' in para and isinstance(para['lines'], list):
        for line in para['lines']:
            if 'spans' in line and isinstance(line['spans'], list):
                for span in line['spans']:
                    if span.get('type') == 'text' and 'content' in span:
                        text_parts.append(span['content'])
    return "".join(text_parts).strip()

def extract_all_text_context(json_data_flat: List[Dict[str, Any]]) -> str:
    """提取所有段落的文本内容，用于提供上下文。"""
    all_text_parts = []
    for para in json_data_flat:
        if para.get("type") in ["text", "title"]: # 仅包含常规文本和标题
            text_content = extract_text_content(para)
            if text_content and "<html><body><table>" not in text_content:
                all_text_parts.append(text_content)
    return "\n".join(all_text_parts)

def flatten_json_data(full_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """将嵌套结构中的所有段落块提取为一个扁平列表 (引用)"""
    flat_list = []
    if isinstance(full_data, dict) and 'output' in full_data and isinstance(full_data['output'], list):
        for page in full_data['output']:
            if 'result' in page and isinstance(page['result'], list):
                flat_list.extend(page['result'])
    return flat_list

# ================= LLM 调用函数 =================

def _call_llm_polish_structure(raw_titles: str, full_context: str) -> str:
    """整理目录结构并标记层级，使用完整的文档上下文。"""

    # 限制上下文大小，防止 token 超限
    context_limit = 10000

    prompt = f"""以下是完整的文档内容，请作为参考上下文来判断标题层级：
--- 文档上下文开始 (约前 {context_limit} 字符) ---
{full_context[:context_limit]}
--- 文档上下文结束 ---

以下是该文档中被识别为标题的列表：
{raw_titles}

请根据上面的【文档上下文】（特别是编号和格式），对【标题列表】中的内容进行结构化和层级划分。
请务必包含【标题列表】中的每一个标题，不要进行任何遗漏或合并。
输出格式要求：以 markdown 格式输出，一级标题前面加# 二级标题加##，以此类推。
不要遗漏标题前面出现的数字编号，和标题无关内容直接忽略。不需要其他多余解释。
"""

    try:
        client = OpenAI(
            api_key=CONFIG['LLM_API_KEY'],
            base_url=CONFIG['LLM_BASE_URL'],
        )
        completion = client.chat.completions.create(
            model=CONFIG['LLM_MODEL'],
            messages=[
                {'role': 'system', 'content': 'You are a document structure analysis assistant. Your task is to accurately determine the hierarchy of provided titles based on the full document context.'},
                {'role': 'user', 'content': prompt}
            ],
            extra_body={"enable_thinking": False}
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"Error during LLM structure polishing: {e}")
        return ""

# ================= 核心处理函数 =================

def get_markdown_titles_with_level(json_data_flat: List[Dict[str, Any]], full_context: str) -> List[str]:
    """基于 JSON 中 type='title' 的块，将其内容提取并交由 LLM 进行结构化和层级划分。"""

    print("1. Collecting text from type='title' blocks...")
    titles_input_to_llm = []

    for para in json_data_flat:
        if para.get("type") == "title":
            text_content = extract_text_content(para)
            if text_content and "<html><body><table>" not in text_content:
                titles_input_to_llm.append(text_content)

    if not titles_input_to_llm:
        print("   Warning: No blocks with type='title' found in the JSON. Skipping LLM call.")
        return []

    full_titles_input = "\n".join(titles_input_to_llm)

    print("2. Calling LLM to polish structure and determine levels using full context...")
    title_md_result = _call_llm_polish_structure(full_titles_input, full_context)

    title_lines = title_md_result.split("\n")
    final_titles = [x for x in title_lines if x.strip() != "" and count_leading_hashes(x.strip()) > 0]

    print(f"   Structured {len(final_titles)} leveled titles.")
    return final_titles

# ================= 主执行逻辑 =================

if __name__ == "__main__":
    print("--- Title Processor Started ---")

    try:
        # 1. 加载完整的嵌套 JSON 结构
        full_json_data = load_json_data(CONFIG['INPUT_JSON_PATH'])
        # 2. 获取段落块的扁平列表 (引用)
        json_data_flat = flatten_json_data(full_json_data)
        # 3. 提取所有文本作为上下文
        full_context = extract_all_text_context(json_data_flat)

    except Exception as e:
        print(f"Startup Failed: {e}")
        sys.exit(1)

    # 4. 调用核心处理逻辑，传入上下文
    final_title_list = get_markdown_titles_with_level(json_data_flat, full_context)


    print("3. Mapping levels and backfilling JSON data...")
    title_level = {}
    default_level = 1

    if final_title_list:
        # 建立 LLM 成功输出的标题到层级的映射
        for one_title in final_title_list:
            level = count_leading_hashes(one_title)
            clean_key = filter_string(re.sub(r'^#+\s*', '', one_title).strip())
            if clean_key:
                title_level[clean_key] = level

    match_count = 0
    fallback_count = 0
    total_title_blocks = 0

    # 5. 遍历扁平列表，对原结构进行修改 (只增加 'level' 字段)
    for para in json_data_flat:
        if para.get("type") == "title":
            total_title_blocks += 1
            original_text = extract_text_content(para)
            original_key = filter_string(original_text)

            level = title_level.get(original_key)

            if level is None:
                # 触发回退机制： LLM 过滤了该标题，或 LLM 根本没有输出
                para["level"] = default_level
                fallback_count += 1
            else:
                # 成功找到 LLM 结构化后的层级
                para["level"] = level

            match_count += 1 # 统计已处理的标题块


    print(f"   Total type='title' blocks processed: {total_title_blocks}")
    print(f"   - Successfully matched LLM output: {match_count - fallback_count}")
    print(f"   - Assigned fallback level ({default_level}): {fallback_count}")

    # 6. 保存完整的原始 JSON 结构
    save_json_data(full_json_data, CONFIG['OUTPUT_JSON_PATH'])
    print(f"--- Task Complete. Result saved to: {CONFIG['OUTPUT_JSON_PATH']} ---")