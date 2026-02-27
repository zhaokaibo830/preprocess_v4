import re
import json
import os
import sys
from typing import List, Dict, Any, Tuple
from pathlib import Path
import time
from utils.LLMcall.client import stream_text
from openai import OpenAI


def title_process(client,
                  model: str,
                  json_data: str,
                  output_path: str,
                  file_name: str,
                  folder_name: str,
                  vlm_enable: bool) -> Dict[str, Any]:
    # ========== 内部辅助函数定义开始 ==========
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

    def get_all_nodes_recursive(full_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        collected_nodes = []

        def recurse_blocks(blocks: List[Dict[str, Any]], parent_page_idx: int):
            for block in blocks:
                current_page_idx = block.get('page_idx', parent_page_idx)
                if 'page_idx' not in block:
                    block['page_idx'] = current_page_idx
                collected_nodes.append(block)
                if 'blocks' in block and isinstance(block['blocks'], list):
                    recurse_blocks(block['blocks'], current_page_idx)

        if isinstance(full_data, dict) and 'output' in full_data:
            for block in full_data['output']:
                page_idx = block.get('page_idx', 0)
                collected_nodes.append(block)
                if 'blocks' in block and isinstance(block['blocks'], list):
                    recurse_blocks(block['blocks'], page_idx)
        return collected_nodes


    def insert_level_field(node: Dict[str, Any], level_val: int):
        """在 index 字段后面插入 level 字段"""
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
        """构建父子节点关系"""
        for node in all_nodes:
            if 'level' in node:
                node['father_node'] = None
                node['child_node'] = []

        for i in range(len(all_nodes)):
            current_node = all_nodes[i]
            if 'level' not in current_node:
                continue
            curr_lvl = current_node['level']
            curr_id = f"{current_node.get('page_idx', 0)}-{current_node.get('index', 0)}"

            target_father = None
            for j in range(i - 1, -1, -1):
                prev_node = all_nodes[j]
                if 'level' not in prev_node:
                    continue
                prev_lvl = prev_node['level']
                if curr_lvl == 0:
                    if prev_lvl > 0:
                        target_father = prev_node
                        break
                else:
                    if prev_lvl > 0 and prev_lvl < curr_lvl:
                        target_father = prev_node
                        break

            if target_father:
                father_id = f"{target_father.get('page_idx', 0)}-{target_father.get('index', 0)}"
                current_node['father_node'] = father_id
                if curr_id not in target_father['child_node']:
                    target_father['child_node'].append(curr_id)

    def call_llm_polish_structure(client, raw_titles: str, model) -> str:
        """调用 LLM 整理目录结构"""
        prompt = f"""您是一位专业的文档结构审计专家。

        待处理标题列表：
        {raw_titles}
        
        请将上述标题转化为 Markdown 层级格式（#，##，###...），并严格遵守以下【层级逻辑约束】：
        
        1. **封面/干扰项处理**：
           - 将封面上的论文题目、期刊信息、作者信息、“目录”字样统统标记为一级标题（#）。它们是独立的文档元数据块。
        
        2. **正文编号强一致性（核心要求）**：
           - **逻辑同级原则**：在正文中，凡是具有【相同编号格式】的标题必须处于【同一层级】。
           - 例如：如果“1 地质背景”被你定为二级标题（##），那么后续出现的“2...”、“3...”、“5...”、“6 结 论”必须全部统一为二级标题（##）。
           - 同理，如果“2.3.2.9 日前检修计划的执行”被你定为四级标题（##），那么后续出现的“2.3.2.10”、“2.3.3.1”等必须全部统一为四级标题（####）  
           - **禁止跳变**：严禁出现“1-5章是二级，6章却变成一级”的情况。
        
        3. **学术论文结构规范**：
           - 通常情况下：封面/题目 (#) -> 摘要/1.前言/2.正文/6.结论/参考文献 (##) -> 2.1子章节 (###)。
           - 请检查“结论”和“参考文献”是否与正文第1章保持了相同的 # 数量。
        
        4. **处理标题内的空格**：
           - 忽略“结 论”中间的空格，将其视为“结论”处理。
        
        输出要求：仅输出 Markdown 结果，包含列表中所有原始文本，严禁遗漏。
        """
        try:
            answer = ""
            for chunk in stream_text(client,
                                     prompt,
                                     model,
                                     client.timeout.connect,
                                     client.timeout.read
                                     ):
                print(chunk, end="", flush=True)
                answer += chunk
            return answer
        except Exception as e:
            print(f"Error during LLM structure polishing: {e}")
            raise RuntimeError(f"标题层级分析LLM调用失败: {str(e)}")

    def process_titles_with_llm(client, all_nodes: List[Dict[str, Any]], model) -> Tuple[Dict[str, int], str]:
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
            return {}, ""

        full_titles_input = "\n".join(titles_input_to_llm)
        print("2. Calling LLM to polish structure (with cover/TOC protection)...")

        error_info = ""
        title_level_map = {}
        try:
            title_md_result = call_llm_polish_structure(client, full_titles_input, model)
            if not title_md_result:
                return {}, "LLM返回结果为空"
            title_lines = title_md_result.split("\n")
            for line in title_lines:
                line = line.strip()
                if not line:
                    continue
                level = count_leading_hashes(line)
                if level > 0:
                    clean_key = filter_string(re.sub(r'^#+\s*', '', line))
                    if clean_key:
                        title_level_map[clean_key] = level
        except Exception as e:
            error_info = str(e)
            print(f"[ERROR] {error_info}")
        return title_level_map, error_info

    def is_specific_title(title):
        """判断是否是真正的红头文件标题"""
        clean_title = title.strip()

        special_titles = {
            "会议纪要",
            "部门会议纪要",
            "内部情况通报",
            "通报"
        }

        if clean_title in special_titles:
            return True

        organization_names = [
            "国家电网有限公司",
            "国网陕西省电力有限公司",
            "陕西省电力公司",
            "陕西省人力资源和社会保障厅",
            "陕西省财政厅",
            "国家电网公司"
        ]

        internal_departments = [
            "党组", "董事会", "办公室", "部门",
            "工会委员会", "委员会", "纪检监察组",
            "直属纪律检查委员会"
        ]

        document_types = [
            "文件", "通知", "任免通知",
            "会议纪要", "部门会议纪要",
            "内部情况通报", "通报"
        ]

        clean_title_no_space = clean_title.replace(" ", "")

        for org in organization_names:
            for doc in document_types:
                if clean_title == f"{org}{doc}":
                    return True
                if clean_title_no_space == f"{org}{doc}":
                    return True
                if clean_title.replace(" ", "") == f"{org}{doc}":
                    return True

        for org in organization_names:
            for dept in internal_departments:
                for doc in document_types:
                    if clean_title == f"{org}{dept}{doc}":
                        return True
                    if clean_title_no_space == f"{org}{dept}{doc}":
                        return True
                    if clean_title.replace(" ", "") == f"{org}{dept}{doc}":
                        return True

        org_pattern = "|".join(organization_names)
        dept_pattern = "|".join(internal_departments)
        doc_pattern = "|".join(document_types)

        pattern1 = re.compile(rf'^\s*({org_pattern})\s*({dept_pattern})?\s*({doc_pattern})\s*$')
        prefix_pattern = r'(?:中共|中央纪委国家监委驻|共青团)?'
        pattern2 = re.compile(rf'^\s*{prefix_pattern}({org_pattern})\s*({dept_pattern})?\s*({doc_pattern})\s*$')

        if pattern1.match(clean_title) or pattern2.match(clean_title):
            return True

        if len(clean_title) <= 20:
            has_org = any(org in clean_title for org in organization_names)
            has_doc = any(doc in clean_title for doc in document_types)
            if has_org and has_doc:
                content_keywords = [
                    "项目", "汇总表", "申报表", "方案", "报告", "研究",
                    "技术", "科技", "获奖", "成果", "指南", "办法",
                    "规定", "细则", "规范", "标准", "目录", "索引",
                    "年度", "季度", "月度", "计划", "总结", "分析"
                ]
                if not any(keyword in clean_title for keyword in content_keywords):
                    return True

        for org in organization_names:
            for doc in document_types:
                if clean_title.startswith(org) and clean_title.endswith(doc):
                    middle = clean_title[len(org):-len(doc)]
                    middle_clean = middle.replace(" ", "").strip()
                    if middle_clean == "" or middle_clean in internal_departments:
                        return True

        return False

    def export_structure_to_markdown(nodes: List[Dict[str, Any]], output_path: str):
        """将处理后的标题结构导出为 Markdown 文件"""
        print(f"5. Exporting Markdown structure view to: {output_path}")

        md_lines = []
        count = 0
        for node in nodes:
            if node.get("type") == "title":
                level = node.get("level", 0)
                text = extract_text_content(node)
                if level > 0:
                    prefix = "#" * level
                    md_lines.append(f"{prefix} {text}")
                    count += 1

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("\n\n".join(md_lines))

        print(f"   Exported {count} structured titles.")

    # ========== 内部辅助函数定义结束，以下是原 title_process 主体 ==========

    print("--- Structure Processor Started ---")

    try:
        # 递归获取节点
        all_process_nodes = get_all_nodes_recursive(json_data)
    except Exception as e:
        print(f"Startup Failed: {e}")
        sys.exit(1)

    # 4. LLM 处理
    title_level_map, error_info = process_titles_with_llm(client, all_process_nodes, model)

    print("3. Assigning levels to ALL nodes (Task 2)...")

    total_processed = 0

    for node in all_process_nodes:
        total_processed += 1
        node_type = node.get("type")
        assigned_level = 0

        if node_type == "title":
            original_text = extract_text_content(node)
            if is_specific_title(original_text):
                assigned_level = 0
            else:
                key = filter_string(original_text)
                if key in title_level_map:
                    assigned_level = title_level_map[key]
                else:
                    assigned_level = 0

        insert_level_field(node, assigned_level)

    print(f"   Assigned levels to {total_processed} nodes.")

    print("4. Building Structure (Father/Child Nodes) (Task 3)...")
    build_structure_relationships(all_process_nodes)

    if vlm_enable:
        base_dir = Path(output_path) / folder_name / 'vlm'
    else:
        base_dir = Path(output_path) / folder_name / 'auto'
    base_dir.mkdir(parents=True, exist_ok=True)

    md_output_path = base_dir / f"{file_name}_titles_only.md"

    export_structure_to_markdown(all_process_nodes, md_output_path)
    return json_data, error_info
