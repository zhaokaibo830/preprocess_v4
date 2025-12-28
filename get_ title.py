import re
import json
import os
import sys
from openai import OpenAI
from typing import List, Dict, Any, Tuple

# ================= 配置区域 =================
CONFIG = {
    # LLM API 配置
    "LLM_API_KEY": "sk-92d983e317d24d2da8ef19ddd2359008",
    "LLM_BASE_URL": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "LLM_MODEL": "qwen3-14b",

    # 文件路径配置
    "INPUT_JSON_PATH": r"D:\py_projects\preprocess\preprocess\GPU\get_title\demo0_middle_final.json",
    "OUTPUT_JSON_PATH": "processed_with_structure.json",
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

# ================= 核心处理逻辑 =================

def get_all_nodes_recursive(full_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    递归遍历整个 JSON 结构 (Task 1)。
    返回一个包含所有需要处理元素的线性列表。
    """
    collected_nodes = []

    def recurse_blocks(blocks: List[Dict[str, Any]], page_idx: int):
        for block in blocks:
            # 排除不需要处理的类型 (Task 2: 除去页眉页脚和页码)
            if block.get("type") in ["header", "footer", "page_number", "page_footnote"]:
                continue

            # 临时记录 page_idx，方便后续生成 ID
            block['_temp_page_idx'] = page_idx
            collected_nodes.append(block)

            # 递归处理嵌套结构 (Task 1: list/table等嵌套)
            if 'blocks' in block and isinstance(block['blocks'], list):
                recurse_blocks(block['blocks'], page_idx)

    if isinstance(full_data, dict) and 'output' in full_data and isinstance(full_data['output'], list):
        for page in full_data['output']:
            page_idx = page.get('page_idx', 0)
            if 'result' in page and isinstance(page['result'], list):
                recurse_blocks(page['result'], page_idx)

    return collected_nodes

def extract_all_text_context_from_nodes(nodes: List[Dict[str, Any]]) -> str:
    """从递归收集的节点中提取上下文文本"""
    all_text_parts = []
    for node in nodes:
        # 只提取主要文本块作为上下文，减少 Token 消耗
        if node.get("type") in ["text", "title"]:
            text_content = extract_text_content(node)
            if text_content and "<html><body><table>" not in text_content:
                all_text_parts.append(text_content)
    return "\n".join(all_text_parts)

def insert_level_field(node: Dict[str, Any], level_val: int):
    """
    Task 2: 在 index 字段后面插入 level 字段。
    """
    temp_items = list(node.items())
    node.clear()

    inserted = False
    for k, v in temp_items:
        node[k] = v
        if k == 'index':
            node['level'] = level_val
            inserted = True

    if not inserted:
        node['level'] = level_val

def build_structure_relationships(all_nodes: List[Dict[str, Any]]):
    """
    1. 确保所有具有 level 的元素初始化。
    2. 采用'最近邻'原则：每个节点向上寻找最邻近的、层级更高的标题作为父节点。
    """
    # 1. 字段初始化
    for node in all_nodes:
        if 'level' in node:
            node['father_node'] = None
            node['child_node'] = []

    # 2. 遍历所有节点构建关系
    for i in range(len(all_nodes)):
        current_node = all_nodes[i]
        if 'level' not in current_node:
            continue

        curr_lvl = current_node['level']
        curr_id = f"{current_node.get('_temp_page_idx', 0)}-{current_node.get('index', 0)}"

        # 向上寻找父节点
        target_father = None
        for j in range(i - 1, -1, -1):
            prev_node = all_nodes[j]
            if 'level' not in prev_node:
                continue

            prev_lvl = prev_node['level']

            # 逻辑：
            # 如果当前是正文 (Level 0)，父节点是上方最近的任何标题 (Level > 0)
            # 如果当前是标题 (Level > 0)，父节点是上方最近的、Level 比自己小的标题
            if curr_lvl == 0:
                if prev_lvl > 0:
                    target_father = prev_node
                    break
            else:
                if prev_lvl > 0 and prev_lvl < curr_lvl:
                    target_father = prev_node
                    break

        # 3. 建立双向绑定
        if target_father:
            father_id = f"{target_father.get('_temp_page_idx', 0)}-{target_father.get('index', 0)}"
            current_node['father_node'] = father_id

            # 将当前节点 ID 加入父节点的 child_node 列表
            if curr_id not in target_father['child_node']:
                target_father['child_node'].append(curr_id)
    # 4. 清理辅助字段
    for node in all_nodes:
        if '_temp_page_idx' in node:
            del node['_temp_page_idx']
# ================= LLM 调用函数 (Prompt 重点修改区域) =================

def call_llm_polish_structure(raw_titles: str, full_context: str) -> str:
    """
    整理目录结构并标记层级。
    在此处通过 Prompt Engineering 解决"封面干扰"问题。
    """
    context_limit = 12000 # 略微增加上下文长度

    prompt = f"""您是一位专业的文档结构审计专家。
    以下是文档上下文摘要：
    ---
    {full_context[:context_limit]}
    ---
    
    待处理标题列表：
    {raw_titles}
    
    请将上述标题转化为 Markdown 层级格式（#，##，###...），并严格遵守以下【层级逻辑约束】：
    
    1. **封面/干扰项处理**：
       - 将封面上的论文题目、期刊信息、作者信息、“目录”字样统统标记为一级标题（#）。它们是独立的文档元数据块。
    
    2. **正文编号强一致性（核心要求）**：
       - **逻辑同级原则**：在正文中，凡是具有【相同编号格式】的标题必须处于【同一层级】。
       - 例如：如果“1 地质背景”被你定为二级标题（##），那么后续出现的“2...”、“3...”、“5...”、“6 结 论”必须全部统一为二级标题（##）。
       - **禁止跳变**：严禁出现“1-5章是二级，6章却变成一级”的情况。
    
    3. **学术论文结构规范**：
       - 通常情况下：封面/题目 (#) -> 摘要/1.前言/2.正文/6.结论/参考文献 (##) -> 2.1子章节 (###)。
       - 请检查“结论”和“参考文献”是否与正文第1章保持了相同的 # 数量。
    
    4. **处理标题内的空格**：
       - 忽略“结 论”中间的空格，将其视为“结论”处理。
    
    输出要求：仅输出 Markdown 结果，包含列表中所有原始文本，严禁遗漏。
    """

    try:
        client = OpenAI(
            api_key=CONFIG['LLM_API_KEY'],
            base_url=CONFIG['LLM_BASE_URL'],
        )
        completion = client.chat.completions.create(
            model=CONFIG['LLM_MODEL'],
            messages=[
                {'role': 'system', 'content': 'You are a professional document structure analyzer. You are distinct at identifying metadata/cover info vs body content.'},
                {'role': 'user', 'content': prompt}
            ],
            extra_body={"enable_thinking": False}
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"Error during LLM structure polishing: {e}")
        return ""

def process_titles_with_llm(all_nodes: List[Dict[str, Any]], full_context: str) -> Dict[str, int]:
    """提取标题，LLM 处理，返回 {标题文本: level} 映射"""
    print("1. Collecting text from type='title' blocks...")
    titles_input_to_llm = []

    for node in all_nodes:
        if node.get("type") == "title":
            text_content = extract_text_content(node)
            if text_content and "<html><body><table>" not in text_content:
                titles_input_to_llm.append(text_content)

    if not titles_input_to_llm:
        print("   Warning: No blocks with type='title' found. Skipping LLM call.")
        return {}

    full_titles_input = "\n".join(titles_input_to_llm)
    print("2. Calling LLM to polish structure (with cover/TOC protection)...")
    title_md_result = call_llm_polish_structure(full_titles_input, full_context)

    # 打印 LLM 返回结果以便调试
    # print("--- LLM Output ---")
    # print(title_md_result)
    # print("------------------")

    title_lines = title_md_result.split("\n")
    title_level_map = {}
    for line in title_lines:
        line = line.strip()
        if not line: continue
        level = count_leading_hashes(line)
        if level > 0:
            clean_key = filter_string(re.sub(r'^#+\s*', '', line))
            if clean_key:
                title_level_map[clean_key] = level

    return title_level_map

def export_structure_to_markdown(nodes: List[Dict[str, Any]], output_path: str):
    """
    将处理后的标题结构导出为 Markdown 文件，方便人工校验层级。
    只导出 level > 0 的 type='title' 元素。
    """
    print(f"5. Exporting Markdown structure view to: {output_path}")

    md_lines = []

    count = 0
    for node in nodes:
        # 仅处理被标记了层级的标题
        if node.get("type") == "title":
            level = node.get("level", 0)
            text = extract_text_content(node)

            if level > 0:
                # 生成 Markdown 标题行，例如: "## 1.1 背景"
                prefix = "#" * level
                # 添加页面索引信息方便回溯
                page_info = f"  *(Page {node.get('index', '?')})*" if 'index' in node else ""
                # 这里为了纯净的目录视图，我们只保留标题文本
                md_lines.append(f"{prefix} {text}")
                count += 1
            else:
                # 记录一下未分级（Level 0）的标题，作为列表项展示，方便检查是否有漏网之鱼
                # md_lines.append(f"- [Level 0] {text}")
                pass

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\n\n".join(md_lines))

    print(f"   Exported {count} structured titles.")

# ================= 主执行逻辑 =================

if __name__ == "__main__":
    print("--- Structure Processor Started ---")

    try:
        # 1. 加载
        full_json_data = load_json_data(CONFIG['INPUT_JSON_PATH'])

        # 2. 递归获取节点 (Task 1: 深入 blocks)
        all_process_nodes = get_all_nodes_recursive(full_json_data)

        # 3. 提取上下文
        full_context = extract_all_text_context_from_nodes(all_process_nodes)

    except Exception as e:
        print(f"Startup Failed: {e}")
        sys.exit(1)

    # 4. LLM 处理 (含干扰项剔除逻辑)
    title_level_map = process_titles_with_llm(all_process_nodes, full_context)

    print("3. Assigning levels to ALL nodes (Task 2)...")

    total_processed = 0

    for node in all_process_nodes:
        total_processed += 1
        node_type = node.get("type")

        assigned_level = 0 # 默认 level 0 (非 title 元素)

        if node_type == "title":
            original_text = extract_text_content(node)
            key = filter_string(original_text)
            if key in title_level_map:
                assigned_level = title_level_map[key]
            else:
                # 如果 LLM 没有返回该标题的层级（可能是漏了，或者是太短的干扰项）
                # 策略：默认为 0，防止其作为错误的父节点干扰后续结构
                # 或者：如果看起来像干扰项，也可以设为 1。这里保守设为 0。
                assigned_level = 0

                # 插入 level 字段
        insert_level_field(node, assigned_level)

    print(f"   Assigned levels to {total_processed} nodes.")

    print("4. Building Structure (Father/Child Nodes) (Task 3)...")
    # 这一步依赖于 level。由于我们将干扰项设为了 Level 1 (或其他 Level)，
    # 只要正文也是 Level 1，这里的逻辑会自动将它们视为“兄弟”而不是“父子”。
    build_structure_relationships(all_process_nodes)

    # 5. 保存
    save_json_data(full_json_data, CONFIG['OUTPUT_JSON_PATH'])
    print(f"--- Task Complete. Result saved to: {CONFIG['OUTPUT_JSON_PATH']} ---")

    base_dir = os.path.dirname(CONFIG['OUTPUT_JSON_PATH'])
    base_name = os.path.splitext(os.path.basename(CONFIG['OUTPUT_JSON_PATH']))[0]
    md_output_path = os.path.join(base_dir, f"{base_name}_titles_only.md")

    export_structure_to_markdown(all_process_nodes, md_output_path)