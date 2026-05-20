import re
import json
import os
import sys
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union
from pathlib import Path
import time
from utils.client import stream_text
from openai import OpenAI
import base64
import mimetypes
import re


# def title_process(client,
#                   model: str,
#                   json_data: str,
#                   output_path: str,
#                   file_name: str,
#                   folder_name: str,
#                   vlm_enable: bool) -> Dict[str, Any]:
#     # ========== 内部辅助函数定义开始 ==========
#     def count_leading_hashes(s: str) -> int:
#         """计算 Markdown 标题层级"""
#         match = re.match(r'^(#+)', s)
#         return len(match.group(1)) if match else 0

#     def filter_string(input_string: str) -> str:
#         """仅保留汉字和字母，用于标题模糊匹配"""
#         pattern = re.compile(r'[\u4e00-\u9fffA-Za-z]')
#         return ''.join(pattern.findall(input_string))

#     def extract_text_content(para: Dict[str, Any]) -> str:
#         """从嵌套的段落结构中提取文本内容"""
#         text_parts = []
#         if 'lines' in para and isinstance(para['lines'], list):
#             for line in para['lines']:
#                 if 'spans' in line and isinstance(line['spans'], list):
#                     for span in line['spans']:
#                         if span.get('type') == 'text' and 'content' in span:
#                             text_parts.append(span['content'])
#         return "".join(text_parts).strip()

#     def get_all_nodes_recursive(full_data: Dict[str, Any]) -> List[Dict[str, Any]]:
#         collected_nodes = []

#         def recurse_blocks(blocks: List[Dict[str, Any]], parent_page_idx: int):
#             for block in blocks:
#                 current_page_idx = block.get('page_idx', parent_page_idx)
#                 if 'page_idx' not in block:
#                     block['page_idx'] = current_page_idx
#                 collected_nodes.append(block)
#                 if 'blocks' in block and isinstance(block['blocks'], list):
#                     recurse_blocks(block['blocks'], current_page_idx)

#         if isinstance(full_data, dict) and 'output' in full_data:
#             for block in full_data['output']:
#                 page_idx = block.get('page_idx', 0)
#                 collected_nodes.append(block)
#                 if 'blocks' in block and isinstance(block['blocks'], list):
#                     recurse_blocks(block['blocks'], page_idx)
#         return collected_nodes


#     def insert_level_field(node: Dict[str, Any], level_val: int):
#         """在 index 字段后面插入 level 字段"""
#         temp_items = list(node.items())
#         node.clear()
#         inserted = False
#         for k, v in temp_items:
#             node[k] = v
#             if k == 'index':
#                 node['level'] = level_val
#                 inserted = True
#         if not inserted:
#             node['level'] = level_val

#     def build_structure_relationships(all_nodes: List[Dict[str, Any]]):
#         """构建父子节点关系"""
#         for node in all_nodes:
#             if 'level' in node:
#                 node['father_node'] = None
#                 node['child_node'] = []

#         for i in range(len(all_nodes)):
#             current_node = all_nodes[i]
#             if 'level' not in current_node:
#                 continue
#             curr_lvl = current_node['level']
#             curr_id = f"{current_node.get('page_idx', 0)}-{current_node.get('index', 0)}"

#             target_father = None
#             for j in range(i - 1, -1, -1):
#                 prev_node = all_nodes[j]
#                 if 'level' not in prev_node:
#                     continue
#                 prev_lvl = prev_node['level']
#                 if curr_lvl == 0:
#                     if prev_lvl > 0:
#                         target_father = prev_node
#                         break
#                 else:
#                     if prev_lvl > 0 and prev_lvl < curr_lvl:
#                         target_father = prev_node
#                         break

#             if target_father:
#                 father_id = f"{target_father.get('page_idx', 0)}-{target_father.get('index', 0)}"
#                 current_node['father_node'] = father_id
#                 if curr_id not in target_father['child_node']:
#                     target_father['child_node'].append(curr_id)

#     def call_llm_polish_structure(client, raw_titles: str, model) -> str:
#         """调用 LLM 整理目录结构"""
#         prompt = f"""你是一位严格的文档层级结构解析专家。

#         你的输入不是全文，而是一份按文档阅读顺序抽取出来的“候选标题列表”。你的任务不是给每一条候选文本都分配层级，而是：
#         1）从候选标题列表中识别真正的结构性标题；
#         2）依据整份候选列表的全局顺序、重复关系、编号模式和层级一致性，恢复稳定的 Markdown 标题层级；
#         3）只输出去重后的真实标题结果。

#         【候选标题列表】
#         {raw_titles}

#         请注意：你不能依赖正文全文语义，只能基于“候选标题列表本身”的全局模式进行判断。因此你必须特别重视以下信号：
#         - 标题在列表中的前后顺序
#         - 同一标题或同一 clean_key 的重复出现情况
#         - 编号样式及其深度
#         - 目录页条目与正文标题的重复关系
#         - 同一文档内部的层级一致性

#         必须严格遵守以下规则：

#         ====================
#         一、总目标
#         ====================
#         - 只输出真实的结构性标题。
#         - 非结构性文本、目录噪声、封面元数据、页眉页脚、页码、图表题注等一律不要输出。
#         - 层级判断必须以整份候选标题列表的“全局一致性”为准，不能只看局部相邻两行。
#         - 同一编号模式必须映射到同一层级，禁止前后漂移。
#         - 输出结果要服务于后续父子节点构建，因此宁可少输出噪声，也不要把噪声误判成标题。
#         - 不是所有候选标题都必须输出；非结构项应直接省略。

#         ====================
#         二、目录（TOC）处理策略
#         ====================
#         采用：目录仅作参考，不直接作为输出来源。

#         具体规则：
#         1. “目录”“目次”“Contents”“Table of Contents”本身不是结构标题，不输出。
#         2. 带有明显目录特征的行默认视为目录项，不直接输出。目录特征包括但不限于：
#         - 行内有连续点线、点状引导符、明显页码尾缀；
#         - 多行连续出现、格式高度整齐、明显像目录页导航列表；
#         - 同一批条目在后文又以更干净的形式重复出现。
#         3. 目录项只有在候选标题列表中还能找到对应的“正文型重复标题”时，才可作为层级参考信号。
#         4. 即使目录项可作为参考，最终也只输出一次该标题，且应优先保留更像正文标题、噪声更少的那个版本。
#         5. 仅像目录项、没有正文型重复支持、或只出现一次且带明显目录噪声的条目，一律不输出。
#         6. 不得因为目录缩进、目录页排版或目录局部结构，把正文一级标题误降成二级标题。

#         ====================
#         三、哪些内容通常不是结构标题
#         ====================
#         以下内容默认视为非结构标题，除非整份候选标题列表强烈表明它们承担章节分隔作用，否则不要输出：
#         - 作者名、单位、邮箱、期刊名、会议名、基金信息、发布时间、版权信息
#         - 封面上的附属元数据块
#         - 单独的“目录”“图目录”“表目录”
#         - 页眉、页脚、页码、重复页头
#         - 图题、表题、公式编号、表格单元格文本
#         - 纯装饰性短语、OCR 残缺行、孤立短语
#         - 明显像公文抬头、机构名 + 文件/通知/通报等组合但不承担正文层级结构的文本
#         - 只在目录形态中出现、没有正文型重复支持的条目

#         特别说明：
#         - 文档主标题可以保留；
#         - 但封面上的作者、机构、期刊、摘要作者信息等通常不是标题，不要输出。

#         ====================
#         四、哪些内容通常应视为结构标题
#         ====================
#         1. 文档主标题：
#         - 如果列表开头存在唯一、统领全文的总标题，可作为最高层标题；
#         - 该总标题通常输出为一级标题 `#`。

#         2. 正文最高层章节：
#         - 如 `1`、`2`、`3`、`第1章`、`第一章`、`一、`、`二、` 等；
#         - 这些必须保持同级。

#         3. 正文二级/三级/四级章节：
#         - 如 `1.1`、`1.2`、`1.1.1`、`2.3.2.10`、`（一）`、`1）` 等；
#         - 层级应按编号深度稳定下降；
#         - 禁止出现同编号模式忽高忽低。

#         4. 无编号但承担标准结构角色的标题：
#         - 如“摘要”“关键词”“引言”“前言”“结论”“参考文献”“附录”“致谢”等；
#         - 它们必须与文档主结构保持一致，不能因为位于文首或文末就随意升降级。

#         ====================
#         五、层级判定规则（最重要）
#         ====================
#         在输出前，先在整份候选标题列表范围内建立“编号模式 -> Markdown 层级”的统一映射，再输出结果。

#         1. 文档主标题规则
#         - 如果存在明确的总标题，则总标题为 `#`；
#         - 在这种情况下，正文最高层章节（如 `1 引言`、`第一章`、`一、`、`摘要`、`结论`、`参考文献`）通常为 `##`；
#         - 如果不存在明确总标题，则正文最高层章节可从 `#` 开始。

#         2. 同编号模式必须同级
#         - `1`、`2`、`3`、`6 结论` 必须同级；
#         - `2.1`、`3.4`、`5.2` 必须同级；
#         - `2.3.2.9`、`2.3.2.10`、`2.3.3.1` 必须同级；
#         - `一、`、`二、`、`三、` 必须同级；
#         - `（一）`、`（二）`、`（三）` 必须同级。

#         3. 只看编号深度，不看数字大小
#         - `1.10` 与 `1.2` 是同级；
#         - `2.3.10` 与 `2.3.2` 是同级；
#         - 不得因为数字位数变化而改变层级。

#         4. 层级逐级下降，禁止跳变
#         - `1` 的下一级通常是 `1.1`；
#         - `1.1` 的下一级通常是 `1.1.1`；
#         - 除非整份候选列表中存在明确且稳定的一致模式，否则不要让 `1.1.1` 直接与 `1` 同级；
#         - 严禁出现“前面 1-5 章是二级，后面 6 章突然变一级”的情况。

#         5. 收尾结构必须与正文主结构对齐
#         - “结论”“参考文献”“附录”“致谢”等，如果与正文一级章节同属主体结构，则必须与 `1`、`2`、`3` 同级；
#         - 不能因为它们位于文末就擅自升一级或降一级。

#         ====================
#         六、候选列表内部的一致性与重复处理
#         ====================
#         1. 若同一标题在前部出现一次、后部又出现一次，且前者更像目录项、后者更像正文标题，则应理解为“目录 + 正文重复”，最终只输出一次正文标题。
#         2. 若同一标题出现多次，应优先保留：
#         - 不带点线、页码、目录噪声的版本；
#         - 文本更完整、OCR 更干净的版本；
#         - 更符合正文章节序列的位置版本。
#         3. 若同名标题仅出现一次，但与上下文编号链、层级链不匹配，且更像噪声，则不要输出。
#         4. 若某行更像封面信息、目录复写、页眉页脚或版式噪声，而不像正文结构节点，则不要输出。
#         5. 当局部格式与整份候选标题列表的主模式冲突时，优先服从全局主模式。

#         ====================
#         七、文本保真与匹配约束
#         ====================
#         1. 输出文本尽量保持候选标题原文，不要改写、翻译、补写、合并、拆分。
#         2. 不要凭空新增候选列表中不存在的标题文本。
#         3. 允许忽略目录页中的页码、点线、无意义空格等目录噪声，但不要把清洗后的新文本当成全新标题创造出来。
#         4. 对“结 论”这类标题，应在理解时忽略中间异常空格，但输出时优先保留候选列表中更像正文标题、噪声更少的原始写法。
#         5. 每个输出标题都必须能够与候选标题列表中的某一条原始候选文本对应。

#         ====================
#         八、最终输出格式
#         ====================
#         - 只输出最终 Markdown 结果；
#         - 一行一个标题；
#         - 每一行都必须以 `#` 开头；
#         - 除 Markdown 标题行外，不要输出任何解释、分析、注释、说明、代码块、项目符号、序号或空话；
#         - 只输出判定为真实结构标题的内容；
#         - 对于非结构标题、目录项、封面元数据、页眉页脚、页码等，直接不输出。

#         请按以下顺序完成任务：
#         1）先识别真实结构标题；
#         2）再根据整份候选标题列表建立统一层级映射；
#         3）再去除目录/封面/页眉页脚/噪声；
#         4）最后输出去重后的 Markdown 标题结果。
#         """
#         try:
#             answer = ""
#             for chunk in stream_text(client,
#                                      prompt,
#                                      model
#                                      ):
#                 print(chunk, end="", flush=True)
#                 answer += chunk
#             return answer
#         except Exception as e:
#             print(f"Error during LLM structure polishing: {e}")
#             raise RuntimeError(f"标题层级分析LLM调用失败: {str(e)}")

#     def process_titles_with_llm(client, all_nodes: List[Dict[str, Any]], model) -> Tuple[Dict[str, int], str]:
#         """提取标题，LLM 处理，返回 {标题文本: level} 映射"""
#         print("1. Collecting text from type='title' blocks...")
#         titles_input_to_llm = []

#         for node in all_nodes:
#             if node.get("type") == "title":
#                 text_content = extract_text_content(node)
#                 if text_content and "<html><body><table>" not in text_content:
#                     titles_input_to_llm.append(text_content)

#         if not titles_input_to_llm:
#             print("   Warning: No blocks with type='title' found. Skipping LLM call.")
#             return {}, ""

#         full_titles_input = "\n".join(titles_input_to_llm)
#         print("2. Calling LLM to polish structure (with cover/TOC protection)...")

#         error_info = ""
#         title_level_map = {}
#         try:
#             title_md_result = call_llm_polish_structure(client, full_titles_input, model)
#             if not title_md_result:
#                 return {}, "LLM返回结果为空"
#             title_lines = title_md_result.split("\n")
#             for line in title_lines:
#                 line = line.strip()
#                 if not line:
#                     continue
#                 level = count_leading_hashes(line)
#                 if level > 0:
#                     clean_key = filter_string(re.sub(r'^#+\s*', '', line))
#                     if clean_key:
#                         title_level_map[clean_key] = level
#         except Exception as e:
#             error_info = str(e)
#             print(f"[ERROR] {error_info}")
#         return title_level_map, error_info

#     def is_specific_title(title):
#         """判断是否是真正的红头文件标题"""
#         clean_title = title.strip()

#         special_titles = {
#             "会议纪要",
#             "部门会议纪要",
#             "内部情况通报",
#             "通报"
#         }

#         if clean_title in special_titles:
#             return True

#         organization_names = [
#             "国家电网有限公司",
#             "国网陕西省电力有限公司",
#             "陕西省电力公司",
#             "陕西省人力资源和社会保障厅",
#             "陕西省财政厅",
#             "国家电网公司"
#         ]

#         internal_departments = [
#             "党组", "董事会", "办公室", "部门",
#             "工会委员会", "委员会", "纪检监察组",
#             "直属纪律检查委员会"
#         ]

#         document_types = [
#             "文件", "通知", "任免通知",
#             "会议纪要", "部门会议纪要",
#             "内部情况通报", "通报"
#         ]

#         clean_title_no_space = clean_title.replace(" ", "")

#         for org in organization_names:
#             for doc in document_types:
#                 if clean_title == f"{org}{doc}":
#                     return True
#                 if clean_title_no_space == f"{org}{doc}":
#                     return True
#                 if clean_title.replace(" ", "") == f"{org}{doc}":
#                     return True

#         for org in organization_names:
#             for dept in internal_departments:
#                 for doc in document_types:
#                     if clean_title == f"{org}{dept}{doc}":
#                         return True
#                     if clean_title_no_space == f"{org}{dept}{doc}":
#                         return True
#                     if clean_title.replace(" ", "") == f"{org}{dept}{doc}":
#                         return True

#         org_pattern = "|".join(organization_names)
#         dept_pattern = "|".join(internal_departments)
#         doc_pattern = "|".join(document_types)

#         pattern1 = re.compile(rf'^\s*({org_pattern})\s*({dept_pattern})?\s*({doc_pattern})\s*$')
#         prefix_pattern = r'(?:中共|中央纪委国家监委驻|共青团)?'
#         pattern2 = re.compile(rf'^\s*{prefix_pattern}({org_pattern})\s*({dept_pattern})?\s*({doc_pattern})\s*$')

#         if pattern1.match(clean_title) or pattern2.match(clean_title):
#             return True

#         if len(clean_title) <= 20:
#             has_org = any(org in clean_title for org in organization_names)
#             has_doc = any(doc in clean_title for doc in document_types)
#             if has_org and has_doc:
#                 content_keywords = [
#                     "项目", "汇总表", "申报表", "方案", "报告", "研究",
#                     "技术", "科技", "获奖", "成果", "指南", "办法",
#                     "规定", "细则", "规范", "标准", "目录", "索引",
#                     "年度", "季度", "月度", "计划", "总结", "分析"
#                 ]
#                 if not any(keyword in clean_title for keyword in content_keywords):
#                     return True

#         for org in organization_names:
#             for doc in document_types:
#                 if clean_title.startswith(org) and clean_title.endswith(doc):
#                     middle = clean_title[len(org):-len(doc)]
#                     middle_clean = middle.replace(" ", "").strip()
#                     if middle_clean == "" or middle_clean in internal_departments:
#                         return True

#         return False

#     def export_structure_to_markdown(nodes: List[Dict[str, Any]], output_path: str):
#         """将处理后的标题结构导出为 Markdown 文件"""
#         print(f"5. Exporting Markdown structure view to: {output_path}")

#         md_lines = []
#         count = 0
#         for node in nodes:
#             if node.get("type") == "title":
#                 level = node.get("level", 0)
#                 text = extract_text_content(node)
#                 if level > 0:
#                     prefix = "#" * level
#                     md_lines.append(f"{prefix} {text}")
#                     count += 1

#         with open(output_path, 'w', encoding='utf-8') as f:
#             f.write("\n\n".join(md_lines))

#         print(f"   Exported {count} structured titles.")

#     # ========== 内部辅助函数定义结束，以下是原 title_process 主体 ==========

#     print("--- Structure Processor Started ---")

#     try:
#         # 递归获取节点
#         all_process_nodes = get_all_nodes_recursive(json_data)
#     except Exception as e:
#         print(f"Startup Failed: {e}")
#         sys.exit(1)

#     # 4. LLM 处理
#     title_level_map, error_info = process_titles_with_llm(client, all_process_nodes, model)

#     print("3. Assigning levels to ALL nodes (Task 2)...")

#     total_processed = 0

#     for node in all_process_nodes:
#         total_processed += 1
#         node_type = node.get("type")
#         assigned_level = 0

#         if node_type == "title":
#             original_text = extract_text_content(node)
#             if is_specific_title(original_text):
#                 assigned_level = 0
#             else:
#                 key = filter_string(original_text)
#                 if key in title_level_map:
#                     assigned_level = title_level_map[key]
#                 else:
#                     assigned_level = 0

#         insert_level_field(node, assigned_level)

#     print(f"   Assigned levels to {total_processed} nodes.")

#     print("4. Building Structure (Father/Child Nodes) (Task 3)...")
#     build_structure_relationships(all_process_nodes)

#     if vlm_enable:
#         base_dir = Path(output_path) / folder_name / 'vlm'
#     else:
#         base_dir = Path(output_path) / folder_name / 'auto'
#     base_dir.mkdir(parents=True, exist_ok=True)

#     md_output_path = base_dir / f"{file_name}_titles_only.md"

#     export_structure_to_markdown(all_process_nodes, md_output_path)
#     return json_data, error_info

JsonDict = Dict[str, Any]


TITLE_LEVEL_NAMES = {
    0: '正文/干扰项',
    1: '一级标题',
    2: '二级标题',
    3: '三级标题',
    4: '四级标题',
    5: '五级标题',
    6: '六级标题',
}


EXTRACT_MODE_SKILLS = {
    'json_only': {
        'name': 'skill_json_only',
        'description': (
            '只使用 JSON 中已有的版面块信息进行标题判定与层级归并；'
            '保持旧流程兼容性最高，不依赖图片。'
        ),
    },
    'hybrid': {
        'name': 'skill_hybrid_json_vlm',
        'description': (
            '先保留 JSON 的候选标题召回，再用多模态逐页核验真假标题、剔除伪标题，'
            '同时补充 JSON 漏掉的结构性标题；兼顾召回率与精度。'
        ),
    },
    'multimodal_only': {
        'name': 'skill_multimodal_only',
        'description': (
            '完全以页面图像为准逐页抽取结构性标题，再进行全局层级排序；'
            '适合图片输入或追求更高视觉精度的场景。'
        ),
    },
}


PRECISION_PROFILE_SKILLS = {
    'fast': {
        'name': 'skill_fast',
        'description': (
            '偏向高效率：只接受版式与语义都很明显的标题；'
            '对边界模糊项从严处理，宁可给 level=0，也不要误报。'
        ),
    },
    'balanced': {
        'name': 'skill_balanced',
        'description': (
            '平衡召回与精度：结合编号模式、视觉字号/粗细/位置、章节语义和上下文一致性综合判断。'
        ),
    },
    'precise': {
        'name': 'skill_precise',
        'description': (
            '偏向高精度：使用跨页一致性、版式层级、编号体系、章节闭环和视觉证据联合决策；'
            '重点剔除页眉页脚、图表题注、作者单位、目录噪声、重复抬头等伪标题。'
        ),
    },
}


ImageInput = Union[str, Dict[str, Any]]

def title_process(client,
                  model: str,
                  json_data: Optional[JsonDict],
                  output_path: str,
                  file_name: str,
                  folder_name: str,
                  vlm_enable: bool,
                  image_inputs: Optional[Union[ImageInput, List[ImageInput]]] = None,
                  pdf_path: Optional[str] = None,
                  extract_mode: str = 'json_only',
                  precision_profile: str = 'balanced') -> Tuple[JsonDict, str]:
    """
    标题处理主入口。
    支持直接传入 PDF 文件路径，内部自动转换为图片流。
    """
    # ========== PDF 预处理：只转换 PDF 为 image_inputs，不改变 json_data / extract_mode ==========
    if pdf_path:
        try:
            import fitz  # PyMuPDF

            print(f"📄 正在读取 PDF 并转换为高清图片: {pdf_path}")
            doc = fitz.open(pdf_path)
            pdf_images = []

            try:
                for page_idx in range(len(doc)):
                    page = doc.load_page(page_idx)
                    # Matrix(2.0, 2.0) 相当于放大一倍，保证大模型能清晰看清小标题
                    mat = fitz.Matrix(2.0, 2.0)
                    pix = page.get_pixmap(matrix=mat)
                    b64_str = base64.b64encode(pix.tobytes("png")).decode("utf-8")
                    pdf_images.append({
                        'page_idx': page_idx,
                        'base64': b64_str,
                        'mime_type': 'image/png',
                        'name': f'page_{page_idx + 1}.png',
                    })
            finally:
                doc.close()

            # 只把 PDF 转换结果接入原有图片输入流；
            # 绝不修改 json_data，绝不覆盖 extract_mode。
            image_inputs = pdf_images

            print(
                f"✅ PDF 转换完成，共 {len(pdf_images)} 页。"
                f" 当前 extract_mode 保持为: {extract_mode}"
            )

        except ImportError:
            raise ImportError("处理 PDF 需要安装 PyMuPDF，请在终端运行: pip install PyMuPDF")
        except Exception as e:
            raise RuntimeError(f"PDF 处理失败: {e}")
    # ==================================================

    # ========== 内部辅助函数定义开始 ==========

    def get_node_key(node: JsonDict) -> str:
        """【关键修复】生成基于坐标的唯一键，替代不稳定的 id() 内存地址"""
        p_idx = node.get('page_idx', 0)
        i_idx = node.get('index', 0)
        n_type = node.get('type', 'node')
        return f"{n_type}_{p_idx}_{i_idx}"

    def normalize_extract_mode(raw_mode: Any) -> str:
        mode = str(raw_mode or 'json_only').strip().lower()
        if mode not in EXTRACT_MODE_SKILLS:
            return 'json_only'
        return mode

    def normalize_precision_profile(raw_profile: Any) -> str:
        profile = str(raw_profile or 'balanced').strip().lower()
        if profile not in PRECISION_PROFILE_SKILLS:
            return 'balanced'
        return profile

    def build_runtime_skill_prompt(mode: str, profile: str) -> str:
        mode_info = EXTRACT_MODE_SKILLS[mode]
        profile_info = PRECISION_PROFILE_SKILLS[profile]
        return f"""
【当前可配置技能】
- 提取策略：{mode_info['name']}
  说明：{mode_info['description']}
- 精度档位：{profile_info['name']}
  说明：{profile_info['description']}

【执行要求】
1. 必须服从当前启用的提取策略与精度档位，不得自行切换模式。
2. 当证据不足时，优先保守处理：伪标题或不确定项给 level=0 / keep=false。
3. 在 hybrid 与 multimodal_only 模式下，必须充分利用页面视觉信息（字号、粗细、留白、位置、编号体系、跨页一致性）进行判断。
4. 伪标题剔除是强约束：页眉页脚、页码、图题、表题、脚注、作者信息、单位、版权、期刊名、卷期号、DOI、网址、目录噪声、重复抬头都要优先排除。
""".strip()

    def extract_text_content(para: JsonDict) -> str:
        """从嵌套的段落结构中提取文本内容"""
        text_parts: List[str] = []
        if 'lines' in para and isinstance(para['lines'], list):
            for line in para['lines']:
                if 'spans' in line and isinstance(line['spans'], list):
                    for span in line['spans']:
                        if span.get('type') == 'text' and 'content' in span:
                            text_parts.append(str(span['content']))
        return ''.join(text_parts).strip()

    def set_text_content(node: JsonDict, text: str):
        """仅在需要时创建最小兼容 lines/spans 结构。"""
        node['lines'] = [
            {
                'spans': [
                    {
                        'type': 'text',
                        'content': str(text).strip(),
                    }
                ]
            }
        ]

    def canonicalize_text(text: str) -> str:
        cleaned = re.sub(r'\s+', '', str(text or ''))
        cleaned = cleaned.replace('．', '.').replace('。', '.').replace('：', ':').replace('（', '(').replace('）', ')')
        return cleaned.strip().lower()

    def get_all_nodes_recursive(full_data: JsonDict) -> List[JsonDict]:
        collected_nodes: List[JsonDict] = []

        def recurse_blocks(blocks: List[JsonDict], parent_page_idx: int):
            for block in blocks:
                current_page_idx = block.get('page_idx', parent_page_idx)
                if 'page_idx' not in block:
                    block['page_idx'] = current_page_idx
                collected_nodes.append(block)
                if 'blocks' in block and isinstance(block['blocks'], list):
                    recurse_blocks(block['blocks'], current_page_idx)

        if isinstance(full_data, dict) and 'output' in full_data and isinstance(full_data['output'], list):
            for block in full_data['output']:
                page_idx = block.get('page_idx', 0)
                if 'page_idx' not in block:
                    block['page_idx'] = page_idx
                collected_nodes.append(block)
                if 'blocks' in block and isinstance(block['blocks'], list):
                    recurse_blocks(block['blocks'], page_idx)
        return collected_nodes

    def get_top_level_page_roots(full_data: JsonDict) -> Dict[int, JsonDict]:
        page_roots: Dict[int, JsonDict] = {}
        if not isinstance(full_data, dict):
            return page_roots
        output_blocks = full_data.setdefault('output', [])
        if not isinstance(output_blocks, list):
            full_data['output'] = []
            output_blocks = full_data['output']
        for block in output_blocks:
            page_idx = int(block.get('page_idx', 0) or 0)
            page_roots.setdefault(page_idx, block)
        return page_roots

    def ensure_page_root(full_data: JsonDict, page_idx: int) -> JsonDict:
        page_roots = get_top_level_page_roots(full_data)
        if page_idx in page_roots:
            root = page_roots[page_idx]
            if 'blocks' not in root or not isinstance(root['blocks'], list):
                root['blocks'] = []
            return root

        root = {
            'type': 'page',
            'index': page_idx,
            'page_idx': page_idx,
            'blocks': [],
        }
        full_data.setdefault('output', []).append(root)
        full_data['output'] = sorted(
            full_data['output'], key=lambda x: (int(x.get('page_idx', 0) or 0), int(x.get('index', 0) or 0))
        )
        return root

    def get_next_block_index_for_page(page_root: JsonDict) -> int:
        indices: List[int] = []

        def collect_indices(blocks: Iterable[JsonDict]):
            for block in blocks:
                try:
                    indices.append(int(block.get('index', 0) or 0))
                except (TypeError, ValueError):
                    continue
                if 'blocks' in block and isinstance(block['blocks'], list):
                    collect_indices(block['blocks'])

        collect_indices(page_root.get('blocks', []))
        return (max(indices) + 1) if indices else 1

    def insert_level_field(node: JsonDict, level_val: int):
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

    def set_node_type(node: JsonDict, new_type: str):
        """保持字段顺序地修改 type 字段；若原节点无 type，则直接补充。"""
        temp_items = list(node.items())
        node.clear()
        replaced = False
        for k, v in temp_items:
            if k == 'type':
                node[k] = new_type
                replaced = True
            else:
                node[k] = v
        if not replaced:
            node['type'] = new_type

    def normalize_level(raw_level: Any, max_level: int = 6) -> int:
        try:
            level = int(raw_level)
        except (TypeError, ValueError):
            return 0
        return max(0, min(level, max_level))

    def get_title_level_name(level: Any) -> str:
        normalized_level = normalize_level(level)
        return TITLE_LEVEL_NAMES.get(normalized_level, f'{normalized_level}级标题')

    def normalize_type_by_level(level: int,
                                original_type: str = '',
                                suggested_type: Optional[str] = None) -> str:
        normalized_level = normalize_level(level)
        normalized_original_type = str(original_type or '').strip().lower()
        normalized_suggested_type = str(suggested_type or '').strip().lower()

        if normalized_level > 0:
            return 'title'
        if normalized_original_type == 'title':
            return 'text'
        if normalized_suggested_type in {'text', 'paragraph', 'caption', 'table', 'figure', 'formula', 'reference', 'footnote'}:
            return normalized_suggested_type
        if normalized_original_type and normalized_original_type != 'title':
            return normalized_original_type
        return 'text'

    def normalize_title_decision(level_val: Any,
                                 original_type: str = '',
                                 suggested_type: Optional[str] = None) -> Dict[str, Any]:
        """统一归一化 level/type 关系，并补充层级语义名称。"""
        normalized_level = normalize_level(level_val)
        normalized_type = normalize_type_by_level(
            normalized_level,
            original_type=original_type,
            suggested_type=suggested_type,
        )
        return {
            'level': normalized_level,
            'type': normalized_type,
            'level_name': get_title_level_name(normalized_level),
        }

    def apply_title_decision(node: JsonDict,
                             level_val: Any,
                             decided_type: Optional[str] = None):
        original_type = str(node.get('type', '') or '').strip().lower()
        normalized_decision = normalize_title_decision(
            level_val,
            original_type=original_type,
            suggested_type=decided_type,
        )
        insert_level_field(node, normalized_decision['level'])

        final_type = normalized_decision['type']
        if str(node.get('type', '') or '').strip().lower() != final_type:
            set_node_type(node, final_type)

    def build_structure_relationships(all_nodes: List[JsonDict]):
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

    def strip_code_fences(text: str) -> str:
        text = text.strip()
        if text.startswith('```'):
            text = re.sub(r'^```[a-zA-Z0-9_\-]*\s*', '', text)
            text = re.sub(r'\s*```$', '', text)
        return text.strip()

    def extract_json_payload(text: str, expect: str = 'any') -> Any:
        """强化版 JSON 提取器：支持 dict / list 两种主流返回类型。"""
        raw_text = str(text or '').strip()
        if not raw_text:
            raise ValueError("大模型返回了空字符串，没有任何内容。")

        cleaned = strip_code_fences(raw_text)
        decoder = json.JSONDecoder()

        for i, ch in enumerate(cleaned):
            if ch not in '{[':
                continue
            try:
                payload, _ = decoder.raw_decode(cleaned[i:])
            except json.JSONDecodeError:
                continue

            if expect == 'dict' and isinstance(payload, dict):
                return payload
            if expect == 'list' and isinstance(payload, list):
                return payload
            if expect == 'any':
                return payload

        candidate_snippets: List[str] = []
        if expect in {'dict', 'any'}:
            start_obj = cleaned.find('{')
            end_obj = cleaned.rfind('}')
            if start_obj != -1 and end_obj != -1 and end_obj > start_obj:
                candidate_snippets.append(cleaned[start_obj:end_obj + 1])

        if expect in {'list', 'any'}:
            start_arr = cleaned.find('[')
            end_arr = cleaned.rfind(']')
            if start_arr != -1 and end_arr != -1 and end_arr > start_arr:
                candidate_snippets.append(cleaned[start_arr:end_arr + 1])

        for snippet in candidate_snippets:
            try:
                payload = json.loads(snippet)
            except Exception:
                continue

            if expect == 'dict' and isinstance(payload, dict):
                return payload
            if expect == 'list' and isinstance(payload, list):
                return payload
            if expect == 'any':
                return payload

        if expect in {'list', 'any'}:
            try:
                start_arr = cleaned.find('[')
                if start_arr != -1 and cleaned.rfind(']') == -1:
                    fixed_str = cleaned[start_arr:]
                    last_brace = fixed_str.rfind('}')
                    if last_brace != -1:
                        fixed_str = fixed_str[:last_brace + 1] + ']'
                        payload = json.loads(fixed_str)
                        if expect == 'any' or isinstance(payload, list):
                            return payload
            except Exception:
                pass

        if expect in {'dict', 'any'}:
            try:
                start_obj = cleaned.find('{')
                if start_obj != -1 and cleaned.rfind('}') == -1:
                    fixed_str = cleaned[start_obj:]
                    brace_depth = 0
                    safe_chars = []
                    for ch in fixed_str:
                        safe_chars.append(ch)
                        if ch == '{':
                            brace_depth += 1
                        elif ch == '}':
                            brace_depth = max(0, brace_depth - 1)
                    if brace_depth > 0:
                        safe_chars.extend('}' * brace_depth)
                    payload = json.loads(''.join(safe_chars))
                    if expect == 'any' or isinstance(payload, dict):
                        return payload
            except Exception:
                pass

        print("\n" + "!" * 65)
        print("🚨 [致命拦截] 大模型未能输出符合预期类型的合法 JSON！")
        print(f"期望类型: {expect}")
        print(f"\n{raw_text}\n")
        print("!" * 65 + "\n")
        raise ValueError(f'未能从模型输出中解析出合法 JSON，期望类型={expect}')

    def maybe_path_to_image_url(image_value: str) -> str:
        raw_value = str(image_value or '').strip()
        if not raw_value:
            raise ValueError('图片输入为空')
        if raw_value.startswith('data:image/'):
            return raw_value
        if re.match(r'^https?://', raw_value, flags=re.IGNORECASE):
            return raw_value

        path_obj = Path(raw_value)
        if not path_obj.exists() or not path_obj.is_file():
            raise FileNotFoundError(f'图片文件不存在: {raw_value}')

        mime_type, _ = mimetypes.guess_type(str(path_obj))
        if not mime_type:
            mime_type = 'image/png'
        encoded = base64.b64encode(path_obj.read_bytes()).decode('utf-8')
        return f'data:{mime_type};base64,{encoded}'

    def normalize_image_inputs(raw_images: Optional[Union[ImageInput, List[ImageInput]]]) -> List[Dict[str, Any]]:
        if raw_images is None:
            return []
        if not isinstance(raw_images, list):
            raw_list = [raw_images]
        else:
            raw_list = raw_images

        normalized: List[Dict[str, Any]] = []
        for idx, item in enumerate(raw_list):
            if isinstance(item, str):
                normalized.append({
                    'page_idx': idx,
                    'image_url': maybe_path_to_image_url(item),
                    'name': Path(item).name if not re.match(r'^https?://', item, flags=re.IGNORECASE) else f'page_{idx + 1}',
                })
                continue

            if not isinstance(item, dict):
                raise TypeError(f'不支持的 image_inputs 元素类型: {type(item)}')

            page_idx = int(item.get('page_idx', idx) or idx)
            image_url: Optional[str] = None

            if item.get('image_url'):
                image_url = maybe_path_to_image_url(str(item['image_url']))
            elif item.get('url'):
                image_url = maybe_path_to_image_url(str(item['url']))
            elif item.get('path'):
                image_url = maybe_path_to_image_url(str(item['path']))
            elif item.get('data_uri'):
                image_url = str(item['data_uri']).strip()
            elif item.get('base64'):
                mime_type = str(item.get('mime_type') or 'image/png').strip()
                image_url = f"data:{mime_type};base64,{str(item['base64']).strip()}"

            if not image_url:
                raise ValueError(f'第 {idx} 个图片输入缺少 path/url/image_url/base64/data_uri')

            normalized.append({
                'page_idx': page_idx,
                'image_url': image_url,
                'name': str(item.get('name') or f'page_{page_idx + 1}').strip(),
            })

        normalized.sort(key=lambda x: int(x.get('page_idx', 0) or 0))
        return normalized

    def stream_multimodal_response(client_obj,
                                   model_name: str,
                                   system_prompt: str,
                                   user_text: str,
                                   image_urls: List[str]) -> str:
        last_error: Optional[Exception] = None

        responses_input = [
            {
                'role': 'system',
                'content': [
                    {'type': 'input_text', 'text': system_prompt},
                ],
            },
            {
                'role': 'user',
                'content': [
                    {'type': 'input_text', 'text': user_text},
                    *[
                        {'type': 'input_image', 'image_url': image_url}
                        for image_url in image_urls
                    ],
                ],
            },
        ]

        chat_messages = [
            {
                'role': 'system',
                'content': system_prompt,
            },
            {
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': user_text},
                    *[
                        {'type': 'image_url', 'image_url': {'url': image_url}}
                        for image_url in image_urls
                    ],
                ],
            },
        ]

        try:
            if hasattr(client_obj, 'responses') and hasattr(client_obj.responses, 'stream'):
                answer = ''
                with client_obj.responses.stream(model=model_name, input=responses_input) as stream:
                    for event in stream:
                        event_type = getattr(event, 'type', '')
                        if event_type == 'response.output_text.delta':
                            delta = getattr(event, 'delta', '') or ''
                            print(delta, end='', flush=True)
                            answer += delta
                    if not answer and hasattr(stream, 'get_final_response'):
                        final_response = stream.get_final_response()
                        answer = getattr(final_response, 'output_text', '') or answer
                if answer:
                    return answer
        except Exception as e:
            last_error = e

        try:
            if hasattr(client_obj, 'chat') and hasattr(client_obj.chat, 'completions'):
                answer = ''
                stream = client_obj.chat.completions.create(
                    model=model_name,
                    messages=chat_messages,
                    stream=True,
                    extra_body={
                        "chat_template_kwargs": {
                            "enable_thinking": False
                        }
                    }
                )
                for chunk in stream:
                    delta_text = ''
                    choices = getattr(chunk, 'choices', None) or []
                    if choices:
                        delta_obj = getattr(choices[0], 'delta', None)
                        content = getattr(delta_obj, 'content', None)
                        if isinstance(content, str):
                            delta_text = content
                        elif isinstance(content, list):
                            for part in content:
                                if isinstance(part, dict) and part.get('type') == 'text':
                                    delta_text += str(part.get('text', ''))
                    if delta_text:
                        print(delta_text, end='', flush=True)
                        answer += delta_text
                if answer:
                    return answer
        except Exception as e:
            last_error = e

        if last_error is not None:
            raise RuntimeError(f'多模态模型调用失败: {last_error}')
        raise RuntimeError('多模态模型调用失败: 当前 client 不支持 responses.stream 或 chat.completions.create')

    def collect_title_candidates(all_nodes: List[JsonDict]) -> List[JsonDict]:
        candidates: List[JsonDict] = []
        for node in all_nodes:
            if node.get('type') != 'title':
                continue
            text_content = extract_text_content(node)
            if not text_content:
                continue
            if '<html><body><td>' in text_content:
                continue
            candidate_id = f"T{len(candidates) + 1:04d}"
            candidates.append({
                'candidate_id': candidate_id,
                'node': node,
                'node_id': get_node_key(node),
                'page_idx': int(node.get('page_idx', 0) or 0),
                'index': int(node.get('index', 0) or 0),
                'order_key': (int(node.get('page_idx', 0) or 0), int(node.get('index', 0) or 0), len(candidates)),
                'source': 'json',
                'text': text_content,
            })
        return candidates

    def group_candidates_by_page(candidates: List[JsonDict]) -> Dict[int, List[JsonDict]]:
        grouped: Dict[int, List[JsonDict]] = {}
        for item in candidates:
            page_idx = int(item.get('page_idx', 0) or 0)
            grouped.setdefault(page_idx, []).append(item)
        for page_idx in grouped:
            grouped[page_idx] = sorted(grouped[page_idx], key=lambda x: x.get('order_key', (page_idx, 0, 0)))
        return grouped

    def call_llm_polish_structure(client_obj,
                                  title_candidates: List[JsonDict],
                                  model_name: str,
                                  mode: str,
                                  profile: str) -> str:
        """调用 LLM 整理目录结构，包含业务常识强约束。"""
        title_count = len(title_candidates)
        candidate_lines = '\n'.join(
            f"{item['candidate_id']}\tP{int(item.get('page_idx', 0) or 0):04d}\tO{pos + 1:04d}\t{item['text']}"
            for pos, item in enumerate(title_candidates)
        )

        prompt = f"""你是一位专业的文档标题层级审计专家。

{build_runtime_skill_prompt(mode, profile)}

任务目标：
对下面给出的 {title_count} 个“候选标题”逐条判断：
- 它是否是真正的结构性标题；
- 如果是标题，层级是多少（1~6）；
- 如果不是标题或无法确认，必须给 level=0，并视为正文/干扰项。

说明：
- 这些候选标题可能来自 JSON、也可能由多模态逐页抽取补充得到；
- 在 hybrid / multimodal_only 模式下，其中一部分候选已经经过页面视觉核验；
- 但你仍然必须做全局层级一致性判断，不要因为来源不同就放松标准。

【输入列表】
每行格式：候选ID<TAB>页码标记<TAB>顺序标记<TAB>原文
{candidate_lines}

【判定规则】
1. 完整性最高优先级：
   - 必须覆盖全部 {title_count} 个候选ID。
   - 不能遗漏、不能新增、不能改写候选ID。
   - 若无法判断，保守输出 level=0，而不是跳过。

2. level 与标题层级的对应关系：
   - level=0：正文/干扰项，不是结构性标题，type 必须为 text。
   - level=1：一级标题，type 必须为 title。
   - level=2：二级标题，type 必须为 title。
   - level=3：三级标题，type 必须为 title。
   - level=4：四级标题，type 必须为 title。
   - level=5：五级标题，type 必须为 title。
   - level=6：六级标题，type 必须为 title。

3. 哪些内容优先判为 level=0：
   - 作者、单位、邮箱、基金项目、收稿日期、页码、页眉页脚、网址、版权声明、期刊名、卷期号、DOI。
   - 图题、表题、题注、数据来源、备注、脚注。
   - 封面零散元数据块、仅“目录”字样、重复抬头、版心信息。
   - 与上下文层级体系不连续、也不承担章节组织功能的短语。
   - 【极高优先级警告】严禁将带有数字编号的“具体规定内容、操作步骤、系统说明”（例如“2.1.4.1.5 根据通道与装置的连接关系...”）判定为标题。只要字数较长或具有陈述语气，一律判为 level=0（正文）！
   - 完全忽略页眉、页脚处的日期（如 2026-04-26）和页码，判为 level=0。

4. 哪些内容优先判为真正标题：
   - 明确的章节/节/小节标题。
   - 具有稳定编号模式的标题，如：1、1.1、1.1.1、第一章、（一）、一、1) 等。
   - 常见结构标题：摘要、Abstract、引言、前言、结论、参考文献、附录、致谢。

5. 层级一致性：
   - 相同编号模式必须尽量保持同层级。
   - 禁止无依据跳级。
   - “结论 / 参考文献 / 附录”等通常应与正文一级章节保持同层级，除非文本证据强烈表明不是。
   - 同一页中上方更大层级标题通常先于下方小层级标题出现，但仍以全局结构一致性为准。

6. 冲突时的取舍：
   - “不要漏处理”优先于“必须判成标题”。
   - 所有候选都必须返回；但不确定时，宁可返回 level=0，也不要强行给 1~6。

【输出格式】
只允许输出 JSON 数组，不要输出 Markdown，不要解释，不要额外文本。
数组长度必须等于 {title_count}，顺序必须与输入完全一致。
每个元素必须严格使用以下字段：
- id: 候选ID，必须原样返回
- level: 整数，取值 0~6
- type: 只能是 "title" 或 "text"。当 level=0 时 type 必须是 "text"；当 level>0 时 type 必须是 "title"

【正确输出示例】
[
  {{"id": "T0001", "level": 1, "type": "title"}},
  {{"id": "T0002", "level": 0, "type": "text"}},
  {{"id": "T0003", "level": 2, "type": "title"}}
]
"""
        try:
            answer = ''
            # 【核心修改】：绕过自动生成的 stream_text，直接调用原生底层的流式接口
            stream = client_obj.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                stream=True,
                # 强行注入私有参数，关闭千问的深度思考
                extra_body={"enable_thinking": False} 
            )

            # 自行解析返回的流式数据块（Chunk）
            for chunk in stream:
                delta_text = ''
                choices = getattr(chunk, 'choices', None) or []
                if choices:
                    delta_obj = getattr(choices[0], 'delta', None)
                    content = getattr(delta_obj, 'content', None)
                    if isinstance(content, str):
                        delta_text = content
                if delta_text:
                    print(delta_text, end='', flush=True)
                    answer += delta_text
                    
            return answer
        except Exception as e:
            print(f'Error during LLM structure polishing: {e}')
            raise RuntimeError(f'标题层级分析LLM调用失败: {str(e)}')

    def build_page_vlm_audit_prompt(page_idx: int,
                                    page_candidates: List[JsonDict],
                                    mode: str,
                                    profile: str) -> Tuple[str, str]:
        skill_prompt = build_runtime_skill_prompt(mode, profile)
        candidate_lines = '\n'.join(
            f"- {item['candidate_id']}\t{item['text']}"
            for item in page_candidates
        ) if page_candidates else '(本页没有来自 JSON 的候选标题)'

        system_prompt = f"""你是一名文档标题抽取与伪标题清洗智能体。

{skill_prompt}

【模块一：强制地毯式扫描模式】
你必须开启“地毯式扫描模式”：从页面左上到右下，按视觉阅读顺序逐行核对，不允许只看大号字、粗体字或页面上半部分。
你必须特别检查页边、图表附近、表格上下方、正文段落之间、换页断裂处、缩进小标题、编号短句。
凡是以“数字+点号/顿号/空格”或多级数字编号开头的短句，例如 1.、1.1、1.1.2、4.2.11、4.2.11.1，必须逐一核对，绝不能遗漏。
凡是以中文章节/条款编号开头的短句，例如 第一章、第一节、第一条、一、（一）、二、，必须逐一核对，绝不能遗漏。
即使标题紧贴图表、表格、题注或正文，也必须检查它是否承担章节组织功能；不得因为位置拥挤而漏提。

**🚨【极高优先级防噪】绝对禁止提取目录（Table of Contents）中的任何条目！如果文本包含连续的引导点号（如 ......）或在行末有对齐的页码，不管它有没有编号，必须将其剔除（keep=false）。**
**🚨【极高优先级防噪】绝对禁止提取表格内部的文本！即使表格内的单元格或表头带有数字编号或加粗，也不承担全局文档的章节组织功能，必须一律剔除。**

你必须严格根据页面视觉证据工作，只输出 JSON，不要输出 Markdown，不要解释。"""

        user_prompt = f"""
当前处理页：page_idx={page_idx}

任务：
1. 观察本页图像，核验下面这些来自 JSON 的候选标题是不是真正的结构性标题；
2. 必须用多模态视觉证据剔除伪标题；
3. 同时补充 JSON 漏掉、但在页面中实际存在的结构性标题；
4. extra_titles 仅允许返回真正承担章节组织功能的标题，不要返回正文、图表题注、作者单位、页眉页脚、页码、版权信息等。

【JSON 候选标题】
{candidate_lines}

【模块一：地毯式扫描硬性要求】
- 必须按页面视觉阅读顺序逐行扫描，不得跳读、不得只抽显眼大标题。
- 绝不能漏掉任何以“数字+点号/顿号/空格”或多级数字编号开头的短句：如 1.、1.1、1.1.2、4.2.11、4.2.11.1。
- 绝不能漏掉任何以中文章节/条款编号开头的短句：如 第一章、第一节、第一条、一、（一）、二、。
- 对紧贴图表、表格、图片、题注、公式或正文的编号短句，也必须逐行核对；只要它承担章节组织功能，就必须出现在 keep=true 或 extra_titles 中。
- 如果某个短句是图题/表题/题注，则可以剔除；但必须先确认它不是章节标题，不能因为靠近图表就默认忽略。

**🚨【极高优先级防噪】绝对禁止提取目录（Table of Contents）中的任何条目！如果文本包含连续的引导点号（如 ......）或在行末有对齐的页码，不管它有没有编号，必须将其剔除（keep=false）。**
**🚨【极高优先级防噪】绝对禁止提取表格内部的文本！即使表格内的单元格或表头带有数字编号或加粗，也不承担全局文档的章节组织功能，必须一律剔除。**

【输出格式】
只允许输出如下 JSON 对象：
{{
  "page_idx": {page_idx},
  "verified_candidates": [
    {{"id": "T0001", "keep": true}},
    {{"id": "T0002", "keep": false}}
  ],
  "extra_titles": [
    {{"text": "1 引言", "order": 1}},
    {{"text": "1.1 研究背景", "order": 2}}
  ]
}}
""".strip()
        return system_prompt, user_prompt

    def build_page_vlm_extract_prompt(page_idx: int,
                                      mode: str,
                                      profile: str) -> Tuple[str, str]:
        skill_prompt = build_runtime_skill_prompt(mode, profile)
        system_prompt = f"""你是一名文档标题抽取智能体。

{skill_prompt}

【模块一：强制地毯式扫描模式】
你必须开启“地毯式扫描模式”：从页面左上到右下，按视觉阅读顺序逐行核对，不允许只看大号字、粗体字或页面上半部分。
凡是以“数字+点号/顿号/空格”或多级数字编号开头的短句，例如 1.、1.1、1.1.2、4.2.11、4.2.11.1，必须逐一核对，绝不能遗漏。
凡是以中文章节/条款编号开头的短句，例如 第一章、第一节、第一条、一、（一）、二、，必须逐一核对，绝不能遗漏。
即使标题紧贴图表、表格、题注或正文，也必须检查它是否承担章节组织功能；不得因为位置拥挤而漏提。

**🚨【极高优先级防噪】绝对禁止提取目录（Table of Contents）中的任何条目！如果文本包含连续的引导点号（如 ......）或在行末有对齐的页码，不管它有没有编号，必须将其剔除（keep=false）。**
**🚨【极高优先级防噪】绝对禁止提取表格内部的文本！即使表格内的单元格或表头带有数字编号或加粗，也不承担全局文档的章节组织功能，必须一律剔除。**

你需要只根据页面图像提取结构性标题，并且严格输出 JSON。"""

        user_prompt = f"""
当前处理页：page_idx={page_idx}

任务：
1. 只根据当前页图像，抽取本页所有真正的结构性标题；
2. 必须剔除伪标题：页眉页脚、页码、作者单位、基金、版权、期刊信息、图题、表题、脚注、目录噪声、重复抬头、正文句子；
3. 仅返回应该进入目录层级树的标题；
4. 按照页面中从上到下的顺序输出。

**🚨【极高优先级防噪】绝对禁止提取目录（Table of Contents）中的任何条目！如果文本包含连续的引导点号（如 ......）或在行末有对齐的页码，不管它有没有编号，必须将其剔除（keep=false）。**
**🚨【极高优先级防噪】绝对禁止提取表格内部的文本！即使表格内的单元格或表头带有数字编号或加粗，也不承担全局文档的章节组织功能，必须一律剔除。**

【输出格式】
只允许输出如下 JSON 对象：
{{
  "page_idx": {page_idx},
  "titles": [
    {{"text": "1 引言", "order": 1}}
  ]
}}
""".strip()
        return system_prompt, user_prompt

    def call_vlm_page_audit(client_obj,
                            model_name: str,
                            page_image: Dict[str, Any],
                            page_candidates: List[JsonDict],
                            mode: str,
                            profile: str) -> Dict[str, Any]:
        system_prompt, user_prompt = build_page_vlm_audit_prompt(
            page_idx=int(page_image.get('page_idx', 0) or 0),
            page_candidates=page_candidates,
            mode=mode,
            profile=profile,
        )
        raw = stream_multimodal_response(
            client_obj,
            model_name,
            system_prompt,
            user_prompt,
            [str(page_image['image_url'])],
        )
        payload = extract_json_payload(raw, expect='dict')
        if not isinstance(payload, dict):
            raise ValueError('逐页多模态核验返回结果不是 JSON 对象')
        return payload

    def call_vlm_page_extract(client_obj,
                              model_name: str,
                              page_image: Dict[str, Any],
                              mode: str,
                              profile: str) -> Dict[str, Any]:
        system_prompt, user_prompt = build_page_vlm_extract_prompt(
            page_idx=int(page_image.get('page_idx', 0) or 0),
            mode=mode,
            profile=profile,
        )
        raw = stream_multimodal_response(
            client_obj,
            model_name,
            system_prompt,
            user_prompt,
            [str(page_image['image_url'])],
        )
        payload = extract_json_payload(raw, expect='dict')
        if not isinstance(payload, dict):
            raise ValueError('逐页多模态标题提取返回结果不是 JSON 对象')
        return payload

    def create_synthetic_title_node(page_idx: int,
                                    index: int,
                                    text: str,
                                    source: str = 'multimodal') -> JsonDict:
        node: JsonDict = {
            'type': 'title',
            'index': index,
            'page_idx': page_idx,
            'source': source,
            'lines': [],
        }
        set_text_content(node, text)
        return node

    def append_synthetic_titles_to_page(full_data: JsonDict, page_idx: int, titles: List[Dict[str, Any]], source: str = 'multimodal') -> List[JsonDict]:
        if not titles: return []
        page_root = ensure_page_root(full_data, page_idx)
        page_root.setdefault('blocks', [])
        
        existing_page_texts = set() 
        current_index = get_next_block_index_for_page(page_root)
        created_nodes: List[JsonDict] = []
        sorted_titles = sorted(titles, key=lambda x: int(x.get('order', 0) or 0))
        for title_item in sorted_titles:
            text = str(title_item.get('text', '')).strip()
            text_key = canonicalize_text(text)
            if not text_key or text_key in existing_page_texts: continue 
            
            synthetic_node = create_synthetic_title_node(page_idx, current_index, text, source=source)
            page_root['blocks'].append(synthetic_node)
            created_nodes.append(synthetic_node)
            existing_page_texts.add(text_key)
            current_index += 1
        return created_nodes

    def build_json_from_images(page_images: List[Dict[str, Any]]) -> JsonDict:
        full_data: JsonDict = {'output': []}
        for page_image in page_images:
            page_idx = int(page_image.get('page_idx', 0) or 0)
            full_data['output'].append({
                'type': 'page',
                'index': page_idx,
                'page_idx': page_idx,
                'blocks': [],
            })
        full_data['output'] = sorted(
            full_data['output'], key=lambda x: (int(x.get('page_idx', 0) or 0), int(x.get('index', 0) or 0))
        )
        return full_data

    def build_candidate_items_from_nodes(nodes: List[JsonDict], source: str) -> List[JsonDict]:
        items: List[JsonDict] = []
        for node in nodes:
            text = extract_text_content(node)
            if not text:
                continue
            candidate_id = f"T{len(items) + 1:04d}"
            items.append({
                'candidate_id': candidate_id,
                'node': node,
                'node_id': get_node_key(node),
                'page_idx': int(node.get('page_idx', 0) or 0),
                'index': int(node.get('index', 0) or 0),
                'order_key': (int(node.get('page_idx', 0) or 0), int(node.get('index', 0) or 0), len(items)),
                'source': source,
                'text': text,
            })
        return items

    def renumber_candidates(candidates: List[JsonDict]) -> List[JsonDict]:
        sorted_items = sorted(candidates, key=lambda x: x.get('order_key', (0, 0, 0)))
        for idx, item in enumerate(sorted_items, start=1):
            item['candidate_id'] = f"T{idx:04d}"
        return sorted_items

    def run_hierarchy_classification(client_obj,
                                     model_name: str,
                                     candidates: List[JsonDict],
                                     mode: str,
                                     profile: str) -> Tuple[Dict[str, Dict[str, Any]], str]:
        """
        改进版标题层级分类函数。
        - 保留三级/四级多级标题
        - 增加正文条款去噪
        - 全局父子锚点引用
        - 保留批处理与 LLM 调用逻辑
        """

        if not candidates:
            return {}, ''

        title_candidates = renumber_candidates(candidates)
        node_decision_map: Dict[str, Dict[str, Any]] = {}
        result_by_id: Dict[str, Dict[str, Any]] = {}
        fallback_count = 0

        # ------------------ 全局硬过滤函数 ------------------
        # ========== 终极物理拦截网 ==========
        def is_physical_noise_title(text: str) -> Tuple[bool, str]:
            n_text = re.sub(r'\s+', ' ', str(text or '')).strip()
            c_text = re.sub(r'\s+', '', n_text)
            if not c_text: return True, 'empty'
            
            # 1. 孤立数字/页码
            if re.fullmatch(r'[-—_・]*\d+[-—_・]*', c_text) or re.fullmatch(r'\d+/\d+', c_text): return True, 'page_number_isolated'
            # 2. 日期元数据
            if re.fullmatch(r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?', c_text): return True, 'date_metadata'
            # 3. 页脚/页眉特征词
            if re.fullmatch(r'(?i)(page|p\.)\d+(/\d+)?', c_text) or re.fullmatch(r'第\d+页', c_text) or '页码' in c_text: return True, 'page_number_text'
            # 4. 文件名
            if re.fullmatch(r'(?i).*?\.(md|pdf|docx?|txt|json|csv|png|jpe?g)$', c_text): return True, 'filename_metadata'
            
            # 5. [修复] 安全的断句拦截（只拦截标点，去掉汉字）
            if c_text.endswith(('。', '；', ';')): return True, 'terminal_punctuation'
            
            # 6. [修复] 基于层级的安全长度拦截 (阈值放宽，容纳正常标题)
            num_match = re.match(r'^(\d+(?:\.\d+)+)', c_text)
            if num_match:
                depth = num_match.group(1).count('.') + 1
                if depth >= 4 and len(c_text) > 45: return True, 'deep_level_clause'
                if depth >= 5 and len(c_text) > 45: return True, 'extreme_level_clause'
            
            # 7. 全局长度强行压制
            if len(c_text) > 65: return True, 'global_length_gt_65'
            
            # 8. [修复] 强特征词拦截 (增加锚定，防止误杀)
            if re.search(r'(具体配置为|原则为|不得|应当|投入运行;)', c_text): return True, 'clause_keywords'
            return False, ''

        # ------------------ 标题模式与编号提取 ------------------
        def get_title_pattern(text: str) -> str:
            normalized_text = str(text or '').strip().replace('．', '.')
            if not normalized_text: return 'unknown'
            if re.match(r'^第[一二三四五六七八九十百千万零〇两0-9]+[章篇部卷]', normalized_text): return 'L_ZHANG'
            if re.match(r'^第[一二三四五六七八九十百千万零〇两0-9]+[节条款项]', normalized_text): return 'L_JIE_TIAO'
            num_match = re.match(r'^(\d+(?:\.\d+)+)(?=$|[\s　、，,：:；;）)\]】\-—_])', normalized_text)
            if num_match: return f"L_NUM_DEPTH_{num_match.group(1).count('.') + 1}"
            return 'unknown'

        def extract_numeric_prefix(text: str) -> Tuple[Optional[str], int]:
            normalized_text = str(text or '').strip().replace('．', '.')
            multi_match = re.match(r'^(\d+(?:\.\d+)+)(?=$|[\s　、，,：:；;）)\]】\-—_])', normalized_text)
            if multi_match: return multi_match.group(1), multi_match.group(1).count('.') + 1
            single_match = re.match(r'^(\d+)(?:[\.、]|\s+)(?=\S)|^(\d+)$', normalized_text)
            if single_match: return single_match.group(1) or single_match.group(2), 1
            return None, 0

        def get_parent_numeric_prefix(prefix: str) -> Optional[str]:
            if not prefix or '.' not in prefix: return None
            return prefix.rsplit('.', 1)[0]

        prefix_to_level_global: Dict[str, int] = {}

        # ------------------ 批处理 LLM 调用 ------------------
        batch_size = 30
        total_candidates = len(title_candidates)

        for batch_idx in range((total_candidates + batch_size - 1) // batch_size):
            batch = title_candidates[batch_idx * batch_size : (batch_idx + 1) * batch_size]
            print(f"[进度] 第 {batch_idx + 1} 批次，正在审计 {len(batch)} 条标题...")
            try:
                raw_llm_output = call_llm_polish_structure(client_obj, batch, model_name, mode, profile)
                payload = extract_json_payload(raw_llm_output, expect='list')
                for item in (payload if isinstance(payload, list) else []):
                    item_id = str(item.get('id', '')).strip()
                    if item_id: 
                        result_by_id[item_id] = item
            except Exception as e:
                print(f"⚠️ 第 {batch_idx + 1} 批次捕获到不稳定解析，触发物理防御降级保护: {e}")
                continue

        # ------------------ 层级分配 ------------------
        for candidate in title_candidates:
            c_id = candidate['candidate_id']
            item = result_by_id.get(c_id)
            if not isinstance(item, dict): continue

            text_content = str(candidate.get('text', '') or '').strip()

            # --- 优先执行物理硬过滤 ---
            is_noise, noise_reason = is_physical_noise_title(text_content)
            if is_noise:
                item['level'] = 0; item['type'] = 'text'; item['hard_filter_reason'] = noise_reason
                continue

            # 编号深度提取
            numeric_prefix, numeric_depth = None, 0
            multi_match = re.match(r'^(\d+(?:\.\d+)+)', text_content)
            if multi_match: numeric_prefix, numeric_depth = multi_match.group(1), multi_match.group(1).count('.') + 1
            else:
                single_match = re.match(r'^(\d+)(?:[\.、]|\s+)(?=\S)|^(\d+)$', text_content)
                if single_match: numeric_prefix, numeric_depth = single_match.group(1) or single_match.group(2), 1

            raw_level = normalize_level(item.get('level', 0))
            smoothed_level = raw_level

            # --- 基于物理编号深度的绝对层级裁决 ---
            # 大模型在这里仅承担二分类职责：判断候选是否是标题。
            # 一旦模型认为是标题，且文本存在明确数字编号深度，则标题层级绝对服从数字深度，
            # 防止一次 LLM 层级幻觉通过旧模式映射传播到全篇。
            if smoothed_level > 0 and numeric_depth > 0:
                smoothed_level = min(numeric_depth, 6)

            if smoothed_level > 0:
                item['level'] = smoothed_level
                item['type'] = 'title'
            else:
                item['level'] = 0
                item['type'] = 'text'

        # ------------------ 构建节点决策 ------------------
        for candidate in title_candidates:
            candidate_id = candidate['candidate_id']
            node_id = candidate['node_id']
            item = result_by_id.get(candidate_id)
            if not item:
                fallback_count += 1
                node_decision_map[node_id] = normalize_title_decision(0, original_type='title', suggested_type='text')
            else:
                node_decision_map[node_id] = normalize_title_decision(item.get('level', 0), original_type='title', suggested_type=item.get('type', 'text'))

        return node_decision_map, '；'.join([f'fallback_count={fallback_count}'] if fallback_count else [])
    def process_titles_json_only(client_obj,
                                 all_nodes: List[JsonDict],
                                 model_name: str,
                                 profile: str) -> Tuple[Dict[str, Dict[str, Any]], str]:
        print("1. Collecting text from type='title' blocks (json_only)...")
        title_candidates = collect_title_candidates(all_nodes)
        if not title_candidates:
            return {}, ''
        print(f"2. Calling LLM to polish structure for {len(title_candidates)} titles...")
        return run_hierarchy_classification(client_obj, model_name, title_candidates, 'json_only', profile)

    def process_titles_hybrid(client_obj,
                              full_data: JsonDict,
                              all_nodes: List[JsonDict],
                              model_name: str,
                              page_images: List[Dict[str, Any]],
                              profile: str) -> Tuple[Dict[str, Dict[str, Any]], str]:
        print("1. Collecting title candidates from JSON for hybrid mode...")
        title_candidates = collect_title_candidates(all_nodes)
        grouped_candidates = group_candidates_by_page(title_candidates)
        image_by_page = {int(item.get('page_idx', 0) or 0): item for item in page_images}

        explicit_decisions: Dict[str, Dict[str, Any]] = {}
        error_messages: List[str] = []

        created_nodes_all: List[JsonDict] = []
        covered_pages = sorted(set(list(grouped_candidates.keys()) + list(image_by_page.keys())))

        for page_idx in covered_pages:
            page_candidates = grouped_candidates.get(page_idx, [])
            page_image = image_by_page.get(page_idx)
            if page_image is None: continue
            
            try:
                payload = call_vlm_page_audit(
                    client_obj, model_name, page_image, page_candidates, 'hybrid', profile,
                )
            except Exception as e:
                error_messages.append(f'page_idx={page_idx} 多模态核验失败: {e}')
                continue
            
            verified_items = payload.get('verified_candidates', [])
            extra_titles = payload.get('extra_titles', [])

            verified_by_id: Dict[str, bool] = {}
            if isinstance(verified_items, list):
                for item in verified_items:
                    if not isinstance(item, dict): continue
                    item_id = str(item.get('id', '')).strip()
                    if item_id: verified_by_id[item_id] = bool(item.get('keep', False))

            for candidate in page_candidates:
                if not verified_by_id.get(candidate['candidate_id'], True):
                    explicit_decisions[candidate['node_id']] = normalize_title_decision(
                        0, original_type='title', suggested_type='text',
                    )

            clean_extra_titles: List[Dict[str, Any]] = []
            existing_text_keys = {canonicalize_text(item['text']) for item in page_candidates}
            if isinstance(extra_titles, list):
                for item in extra_titles:
                    if not isinstance(item, dict): continue
                    text = str(item.get('text', '') or '').strip()
                    if not text: continue
                    text_key = canonicalize_text(text)
                    if not text_key or text_key in existing_text_keys: continue
                    clean_extra_titles.append({
                        'text': text,
                        'order': int(item.get('order', len(clean_extra_titles) + 1) or len(clean_extra_titles) + 1),
                    })
                    existing_text_keys.add(text_key)

            if clean_extra_titles:
                created_nodes = append_synthetic_titles_to_page(
                    full_data, page_idx, clean_extra_titles, source='multimodal_hybrid_extra',
                )
                created_nodes_all.extend(created_nodes)

        refreshed_nodes = get_all_nodes_recursive(full_data)
        refreshed_candidates = collect_title_candidates(refreshed_nodes)
        hierarchy_candidates = [c for c in refreshed_candidates if c['node_id'] not in explicit_decisions]

        if not hierarchy_candidates and explicit_decisions:
            return explicit_decisions, '；'.join(error_messages)

        hierarchy_decisions, hierarchy_error = run_hierarchy_classification(
            client_obj, model_name, hierarchy_candidates, 'hybrid', profile,
        )
        
        merged = {}
        merged.update(explicit_decisions)
        merged.update(hierarchy_decisions)
        if hierarchy_error: error_messages.append(hierarchy_error)
        return merged, '；'.join(error_messages)

    def process_titles_multimodal_only(client_obj,
                                       full_data: JsonDict,
                                       existing_all_nodes: List[JsonDict],
                                       model_name: str,
                                       page_images: List[Dict[str, Any]],
                                       profile: str) -> Tuple[Dict[str, Dict[str, Any]], str]:
        error_messages: List[str] = []
        explicit_decisions: Dict[str, Dict[str, Any]] = {}

        for node in existing_all_nodes:
            if str(node.get('type', '') or '').strip().lower() == 'title':
                explicit_decisions[get_node_key(node)] = normalize_title_decision(
                    0, original_type='title', suggested_type='text',
                )

        created_nodes_all: List[JsonDict] = []
        for page_image in page_images:
            page_idx = int(page_image.get('page_idx', 0) or 0)
            try:
                payload = call_vlm_page_extract(client_obj, model_name, page_image, 'multimodal_only', profile)
            except Exception as e:
                continue

            titles = payload.get('titles', [])
            clean_titles: List[Dict[str, Any]] = []
            if isinstance(titles, list):
                dedup_keys: set = set()
                for item in titles:
                    if not isinstance(item, dict): continue
                    text = str(item.get('text', '') or '').strip()
                    if not text: continue
                    text_key = canonicalize_text(text)
                    if not text_key or text_key in dedup_keys: continue
                    clean_titles.append({
                        'text': text,
                        'order': int(item.get('order', len(clean_titles) + 1) or len(clean_titles) + 1),
                    })
                    dedup_keys.add(text_key)

            if clean_titles:
                created_nodes = append_synthetic_titles_to_page(
                    full_data, page_idx, clean_titles, source='multimodal_only',
                )
                created_nodes_all.extend(created_nodes)

        synthetic_candidates = build_candidate_items_from_nodes(created_nodes_all, 'multimodal_only')
        if not synthetic_candidates:
            raise RuntimeError('multimodal_only 未生成任何标题候选。')

        hierarchy_decisions, hierarchy_error = run_hierarchy_classification(
            client_obj, model_name, synthetic_candidates, 'multimodal_only', profile,
        )

        merged = {}
        merged.update(explicit_decisions)
        merged.update(hierarchy_decisions)
        return merged, hierarchy_error

    def export_structure_to_markdown(nodes: List[JsonDict], output_md_path: Path):
        print(f"5. Exporting Markdown structure view to: {output_md_path}")
        md_lines: List[str] = []
        count = 0
        for node in nodes:
            level = int(node.get('level', 0) or 0)
            if level > 0:
                text = extract_text_content(node)
                if text:
                    prefix = '#' * level
                    md_lines.append(f'{prefix} {text}')
                    count += 1
        output_md_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_md_path, 'w', encoding='utf-8') as f:
            f.write('\n\n'.join(md_lines))

    # ========== 内部辅助函数定义结束，以下是 title_process 主体 ==========
    print('--- Structure Processor Started ---')

    extract_mode = str(extract_mode or 'json_only').strip().lower()
    if extract_mode not in EXTRACT_MODE_SKILLS:
        raise ValueError(f"不支持的 extract_mode: {extract_mode}")

    precision_profile = normalize_precision_profile(precision_profile)
    normalized_images = normalize_image_inputs(image_inputs)

    if extract_mode == 'json_only':
        if json_data is None: raise ValueError('extract_mode=json_only 时必须提供 json_data。')
        working_data = json_data
        input_source = 'json'
    elif extract_mode == 'multimodal_only':
        if not normalized_images: raise ValueError('extract_mode=multimodal_only 时必须提供 image_inputs 或 pdf_path。')
        if json_data is None:
            working_data: JsonDict = build_json_from_images(normalized_images)
            input_source = 'image_only'
        else:
            working_data = json_data
            input_source = 'json+image'
    elif extract_mode == 'hybrid':
        if json_data is None: raise ValueError('extract_mode=hybrid 时必须提供 json_data。')
        if not normalized_images: raise ValueError('extract_mode=hybrid 时必须提供 image_inputs 或 pdf_path。')
        working_data = json_data
        input_source = 'json+image'
    else:
        raise ValueError(f'不支持的 extract_mode: {extract_mode}')

    try:
        all_process_nodes = get_all_nodes_recursive(working_data)
    except Exception as e:
        sys.exit(1)

    error_info = ''
    title_decision_map: Dict[str, Dict[str, Any]] = {}

    if extract_mode == 'json_only':
        title_decision_map, error_info = process_titles_json_only(client, all_process_nodes, model, precision_profile)
    elif extract_mode == 'hybrid':
        title_decision_map, error_info = process_titles_hybrid(client, working_data, all_process_nodes, model, normalized_images, precision_profile)
        all_process_nodes = get_all_nodes_recursive(working_data)
    elif extract_mode == 'multimodal_only':
        title_decision_map, error_info = process_titles_multimodal_only(client, working_data, all_process_nodes, model, normalized_images, precision_profile)
        all_process_nodes = get_all_nodes_recursive(working_data)

    print('4. Assigning levels and types to ALL nodes...')
    for node in all_process_nodes:
        node_type = str(node.get('type', '') or '').strip().lower()
        assigned_level = int(node.get('level', 0) or 0)
        assigned_type = node_type

        if node_type == 'title':
            node_id = get_node_key(node)
            decision = title_decision_map.get(node_id)
            if decision is not None:
                assigned_level = int(decision.get('level', 0) or 0)
                assigned_type = str(decision.get('type', 'text') or 'text').strip().lower()
            else:
                assigned_level = 0
                assigned_type = 'text'

        apply_title_decision(node, assigned_level, assigned_type)

    print('5. Building Structure (Father/Child Nodes)...')
    build_structure_relationships(all_process_nodes)

    use_multimodal_output_dir = extract_mode in {'hybrid', 'multimodal_only'} or vlm_enable or input_source == 'image_only'
    if use_multimodal_output_dir:
        base_dir = Path(output_path) / folder_name / 'vlm'
    else:
        base_dir = Path(output_path) / folder_name / 'auto'
    base_dir.mkdir(parents=True, exist_ok=True)

    md_output_path = base_dir / f'{file_name}_titles_only.md'
    export_structure_to_markdown(all_process_nodes, md_output_path)

    # 仅在确有错误信息时返回错误字符串，避免配置摘要被上层误判为异常。
    final_error_info = str(error_info).strip() if error_info and str(error_info).strip() else ''
    return working_data, final_error_info