import json
import re
from typing import Dict, List, Any, Tuple
import os

def extract_text_from_item(item: Dict) -> str:
    """从原始数据项中提取文本内容"""
    
    item_type = item.get("type", "")
    
    # 处理table类型
    if item_type == "table":
        print(f"DEBUG extract_text_from_item: 开始处理table类型")
        
        # 首先检查llm_process
        if "llm_process" in item:
            llm_data = item["llm_process"]
            print(f"DEBUG: llm_process存在，类型: {type(llm_data)}")
            
            # 处理llm_process是列表的情况
            if isinstance(llm_data, list):
                print(f"DEBUG: llm_process是列表，长度: {len(llm_data)}")
                for llm_item in llm_data:
                    if isinstance(llm_item, dict):
                        # 检查description字段
                        if "description" in llm_item:
                            description = llm_item["description"]
                            print(f"DEBUG: 找到description字段")
                            return str(description) if description is not None else ""
                        # 检查desc字段（用于image类型）
                        elif "desc" in llm_item:
                            desc = llm_item["desc"]
                            print(f"DEBUG: 找到desc字段")
                            return str(desc) if desc is not None else ""
            
            # 处理llm_process是字典的情况（兼容原有代码）
            elif isinstance(llm_data, dict):
                print(f"DEBUG: llm_process是字典，keys: {list(llm_data.keys())}")
                if "description" in llm_data:
                    description = llm_data["description"]
                    return str(description) if description is not None else ""
                elif "desc" in llm_data:
                    desc = llm_data["desc"]
                    return str(desc) if desc is not None else ""
        else:
            print(f"DEBUG: table中没有llm_process字段")
        
        # 如果没有llm_process或description，从blocks中提取
        if "blocks" in item:
            print(f"DEBUG: 尝试从blocks中提取文本")
            table_texts = []
            for block in item.get("blocks", []):
                if "lines" in block:
                    for line in block["lines"]:
                        if "spans" in line:
                            for span in line["spans"]:
                                if span.get("type") == "text" and "content" in span:
                                    table_texts.append(span["content"])
            result = " ".join(table_texts)
            print(f"DEBUG: 从blocks提取到文本，长度: {len(result)}")
            return result
        
        return ""
    
    # 处理image类型
    elif item_type == "image":
        if "llm_process" in item:
            llm_data = item["llm_process"]
            print(f"DEBUG: image的llm_process类型: {type(llm_data)}")
            
            # 处理llm_process是列表的情况
            if isinstance(llm_data, list):
                for llm_item in llm_data:
                    if isinstance(llm_item, dict):
                        if "desc" in llm_item:
                            desc = llm_item["desc"]
                            print(f"DEBUG: 从image的llm_process列表中找到desc字段")
                            return str(desc) if desc is not None else ""
            
            # 处理llm_process是字典的情况
            elif isinstance(llm_data, dict):
                if "desc" in llm_data:
                    desc = llm_data["desc"]
                    print(f"DEBUG: 从image的llm_process字典中找到desc字段")
                    return str(desc) if desc is not None else ""
        
        elif "blocks" in item:
            # 尝试从caption中提取文本
            for block in item.get("blocks", []):
                if block.get("type") == "image_caption" and "lines" in block:
                    for line in block["lines"]:
                        if "spans" in line:
                            for span in line["spans"]:
                                if span.get("type") == "text" and "content" in span:
                                    return span["content"]
        return ""
    
    # 处理其他类型...
    else:
        texts = []
        
        # 从lines中提取文本
        if "lines" in item:
            for line in item["lines"]:
                if "spans" in line:
                    for span in line["spans"]:
                        if span.get("type") in ["text", "inline_equation", "interline_equation"] and "content" in span:
                            texts.append(span["content"])
        
        # 对于有blocks的类型，从blocks中提取
        elif "blocks" in item:
            for block in item.get("blocks", []):
                if "lines" in block:
                    for line in block["lines"]:
                        if "spans" in line:
                            for span in line["spans"]:
                                if span.get("type") in ["text", "inline_equation", "interline_equation"] and "content" in span:
                                    texts.append(span["content"])
        
        return " ".join(texts)


def extract_table_html(item: Dict) -> str:
    """从table类型数据项中提取html"""
    if item.get("type") == "table":
        print(f"DEBUG extract_table_html: 处理table类型")
        
        # 尝试从llm_process中获取table_html
        if "llm_process" in item:
            llm_data = item["llm_process"]
            print(f"DEBUG: llm_process类型: {type(llm_data)}")
            
            # 处理llm_process是列表的情况
            if isinstance(llm_data, list):
                print(f"DEBUG: llm_process是列表，长度: {len(llm_data)}")
                for llm_item in llm_data:
                    if isinstance(llm_item, dict):
                        if "table_html" in llm_item:
                            html = llm_item["table_html"]
                            print(f"DEBUG: 从llm_process列表中找到table_html字段")
                            return str(html) if html is not None else ""
                        elif "key_value" in llm_item:
                            # 如果只有key_value，尝试构建HTML？或者返回空
                            print(f"DEBUG: 找到key_value字段，但没有table_html")
            
            # 处理llm_process是字典的情况
            elif isinstance(llm_data, dict):
                if "table_html" in llm_data:
                    html = llm_data["table_html"]
                    return str(html) if html is not None else ""
        
        # 尝试从blocks中获取html
        if "blocks" in item:
            for block in item.get("blocks", []):
                if "lines" in block:
                    for line in block["lines"]:
                        if "spans" in line:
                            for span in line["spans"]:
                                if span.get("type") == "table" and "html" in span:
                                    html = span["html"]
                                    print(f"DEBUG: 从span中提取到html")
                                    return str(html) if html is not None else ""
    
    return ""


def extract_caption_from_item(item: Dict) -> str:
    """
    从数据项中提取caption（标题）
    对于table类型，从table_caption中提取
    对于image类型，从image_caption中提取
    其他类型返回空字符串
    """
    item_type = item.get("type", "")
    caption = ""
    
    if item_type in ["table", "image"] and "blocks" in item:
        caption_texts = []
        
        # 查找caption类型的block
        for block in item.get("blocks", []):
            block_type = block.get("type", "")
            
            # 检查是否为caption类型
            if block_type in ["table_caption", "image_caption"]:
                print(f"DEBUG: 找到{block_type} block")
                
                # 从block中提取文本内容
                if "lines" in block:
                    for line in block["lines"]:
                        if "spans" in line:
                            for span in line["spans"]:
                                if span.get("type") == "text" and "content" in span:
                                    caption_texts.append(span["content"])
        
        # 合并所有caption文本
        if caption_texts:
            caption = " ".join(caption_texts)
    
    return caption


def extract_image_path(item: Dict) -> str:
    """从数据项中提取image_path"""
    item_type = item.get("type", "")
    
    # 处理table和image类型
    if item_type in ["table", "image", "inline_equation", "interline_equation"]:
        # 直接检查image_path字段
        if "image_path" in item:
            return item["image_path"]
        
        # 从lines中的spans查找image_path
        if "lines" in item:
            for line in item["lines"]:
                if "spans" in line:
                    for span in line["spans"]:
                        if "image_path" in span:
                            return span["image_path"]
        
        # 从blocks中查找image_path
        if "blocks" in item:
            for block in item.get("blocks", []):
                if "lines" in block:
                    for line in block["lines"]:
                        if "spans" in line:
                            for span in line["spans"]:
                                if "image_path" in span:
                                    return span["image_path"]
    
    return ""

def extract_bbox(item: Dict) -> List:
    """从数据项中提取bbox信息"""
    # 首先检查item本身的bbox
    if "bbox" in item:
        return item["bbox"]
    
    # 从lines中的第一个span获取bbox
    if "lines" in item and item["lines"]:
        for line in item["lines"]:
            if "spans" in line and line["spans"]:
                for span in line["spans"]:
                    bbox = span.get("bbox")
                    if bbox:
                        return bbox
    
    # 从blocks中获取bbox
    if "blocks" in item:
        for block in item.get("blocks", []):
            if "lines" in block:
                for line in block["lines"]:
                    if "spans" in line and line["spans"]:
                        for span in line["spans"]:
                            bbox = span.get("bbox")
                            if bbox:
                                return bbox
    
    return []

def contains_chinese(text: str) -> bool:
    """检查字符串是否包含汉字"""
    # 使用正则表达式匹配中文字符
    chinese_pattern = re.compile(r'[\u4e00-\u9fff]+')
    return bool(chinese_pattern.search(text))

def normalize_sub_type(original_sub_type: str) -> str:
    """
    规范化sub_type字段：
    1. 如果sub_type为text，保持小写
    2. 其他英文类型改为首字母大写
    """
    if original_sub_type == "text":
        return "text"  # text保持小写
    else:
        # 只处理字母类型，非字母类型保持不变
        if original_sub_type.isalpha():
            return original_sub_type.capitalize()  # 首字母大写
        else:
            return original_sub_type  # 非字母类型保持不变

def normalize_type(original_type: str) -> Tuple[str, str]:
    """
    规范化type字段并返回(规范化后的type, sub_type)
    
    规范化规则：
    1. 如果type是title, table, image，首字母大写
    2. 其他类型（除page_number外）转为text
    3. text保持不变
    4. sub_type存储原始type值，并根据规则规范化
    """
    if original_type == "page_number":
        return (None, "page_number")  # 返回None表示需要过滤掉
    
    # 定义需要首字母大写的类型
    capitalize_types = ["title", "table", "image"]
    
    if original_type in capitalize_types:
        # 首字母大写
        normalized_sub_type = normalize_sub_type(original_type)
        return (original_type.capitalize(), normalized_sub_type)
    elif original_type == "text":
        # text保持不变
        return ("text", normalize_sub_type(original_type))
    else:
        # 其他类型转为text，但sub_type保留原始值并规范化
        normalized_sub_type = normalize_sub_type(original_type)
        return ("text", normalized_sub_type)

def adjust_sub_type_by_page(sub_type: str, page_value: int) -> str:
    """
    根据page字段值调整sub_type：
    1. 如果page字段值为1且sub_type是汉字，则把sub_type改为Official_Header
    2. 若page字段值不为1且sub_type是汉字，则把sub_type改为Colophon
    """
    # 检查sub_type是否包含汉字
    if contains_chinese(sub_type):
        if page_value == 1:
            return "Official_Header"
        else:
            return "Colophon"
    
    return sub_type

def convert_original_to_target(original_data: List[Dict]) -> List[Dict]:
    """
    将原始JSON数据转换为目标格式
    """
    converted_data = []
    
    for idx, item in enumerate(original_data):
        original_type = item.get("type", "")
        
        # 规范化type
        normalized_type, sub_type = normalize_type(original_type)
        
        # 获取page值
        page_value = item.get("page_idx", 0) + 1  # page_idx从0开始，所以+1
        
        # 根据page字段调整sub_type
        sub_type = adjust_sub_type_by_page(sub_type, page_value)
        
        # 如果type是page_number，跳过此项
        if normalized_type is None:
            print(f"跳过第 {idx} 条数据 (page_number类型)")
            continue
        
        # 如果是table类型，打印详细调试信息
        if normalized_type == "Table":
            print(f"\n{'='*60}")
            print(f"处理第 {idx} 条数据 (table类型)")
            print(f"原始type: {original_type}, 规范化后: {normalized_type}, sub_type: {sub_type}, page: {page_value}")
            print(f"{'='*60}")
        # 如果是image类型，打印调试信息
        elif normalized_type == "Image":
            print(f"\n{'='*60}")
            print(f"处理第 {idx} 条数据 (image类型)")
            print(f"原始type: {original_type}, 规范化后: {normalized_type}, sub_type: {sub_type}, page: {page_value}")
            print(f"{'='*60}")
        # 如果是equation类型，也打印调试信息
        elif original_type in ["inline_equation", "interline_equation"]:
            print(f"\n{'='*60}")
            print(f"处理第 {idx} 条数据 ({original_type}类型)")
            print(f"原始type: {original_type}, 规范化后: {normalized_type}, sub_type: {sub_type}, page: {page_value}")
            print(f"{'='*60}")
        # 如果是汉字sub_type，打印调试信息
        elif contains_chinese(original_type):
            print(f"\n{'='*60}")
            print(f"处理第 {idx} 条数据 (汉字类型)")
            print(f"原始type: {original_type}, 规范化后: {normalized_type}, sub_type: {sub_type}, page: {page_value}")
            print(f"{'='*60}")
        
        # 提取文本内容
        text_content = extract_text_from_item(item)
        
        # 提取caption（只有Table和Image类型需要）
        caption_content = ""
        if normalized_type in ["Table", "Image"]:
            caption_content = extract_caption_from_item(item)
            if caption_content:
                print(f"DEBUG: 提取到caption: {caption_content}")
        
        # 如果是equation类型，显示提取的内容
        if original_type in ["inline_equation", "interline_equation"]:
            print(f"提取到的text_content: {text_content[:200] if text_content else '空'}")
            print(f"text_content长度: {len(text_content)}")
            
            # 检查数据结构
            if "lines" in item:
                print(f"lines结构:")
                for line_idx, line in enumerate(item["lines"]):
                    if "spans" in line:
                        print(f"  第{line_idx}行有{len(line['spans'])}个spans")
                        for span_idx, span in enumerate(line["spans"]):
                            span_type = span.get("type", "")
                            has_content = "content" in span
                            content_preview = span.get("content", "")[:100] if has_content else "无"
                            print(f"    span{span_idx}: type={span_type}, 有content={has_content}")
                            print(f"      内容预览: {content_preview}")
        
        # 如果是Table类型且text为空，跳过此项
        if normalized_type == "Table" and not text_content.strip():
            print(f"跳过第 {idx} 条数据 (Table类型但text为空)")
            continue
        
        # 提取data字段（对于Table是html）
        data_content = extract_table_html(item) if normalized_type == "Table" else ""
        
        # 提取image_path
        image_path_content = extract_image_path(item)
        
        # 创建新的数据结构
        new_item = {
            "type": normalized_type,
            "sub_type": sub_type,  # 添加sub_type字段
            "title_type": item.get("level", -1) if normalized_type == "Title" else -1,
            "caption": caption_content,  # 添加caption字段
            "text": text_content,
            "data": data_content,
            "image_path": image_path_content,
            "metadata": {
                "extra_data": {
                    "types": [normalized_type],
                    "pages": [page_value],  # 使用调整后的page_value
                    "bboxes": [extract_bbox(item)],
                    "indexes": [(0, len(text_content))] if text_content else []
                }
            }
        }
        
        converted_data.append(new_item)
    
    return converted_data

def clean_extra_data_numbers(data):
    """递归清理extra_data中的数字前缀问题"""
    if isinstance(data, dict):
        cleaned = {}
        for key, value in data.items():
            if key == "extra_data":
                cleaned[key] = {}
                for sub_key, sub_value in value.items():
                    # 清理types中的数字前缀
                    if sub_key == "types" and isinstance(sub_value, list):
                        cleaned_types = []
                        for item in sub_value:
                            if isinstance(item, str):
                                cleaned_item = re.sub(r'^\d+', '', item)
                                cleaned_types.append(cleaned_item)
                            else:
                                cleaned_types.append(item)
                        cleaned[key][sub_key] = cleaned_types
                    
                    # 清理pages中的数字前缀
                    elif sub_key == "pages" and isinstance(sub_value, list):
                        cleaned_pages = []
                        for item in sub_value:
                            if isinstance(item, str):
                                cleaned_item = re.sub(r'^\d+', '', item)
                                if cleaned_item.isdigit():
                                    cleaned_pages.append(int(cleaned_item))
                                else:
                                    cleaned_pages.append(item)
                            else:
                                cleaned_pages.append(item)
                        cleaned[key][sub_key] = cleaned_pages
                    
                    # 清理bboxes
                    elif sub_key == "bboxes" and isinstance(sub_value, list):
                        cleaned_bboxes = []
                        for bbox in sub_value:
                            if isinstance(bbox, list):
                                cleaned_bbox = []
                                for coord in bbox:
                                    if isinstance(coord, str):
                                        cleaned_coord = re.sub(r'^\d+', '', coord)
                                        if cleaned_coord.isdigit():
                                            cleaned_bbox.append(int(cleaned_coord))
                                        else:
                                            cleaned_bbox.append(coord)
                                    else:
                                        cleaned_bbox.append(coord)
                                cleaned_bboxes.append(cleaned_bbox)
                            else:
                                cleaned_bboxes.append(bbox)
                        cleaned[key][sub_key] = cleaned_bboxes
                    
                    # 清理indexes
                    elif sub_key == "indexes" and isinstance(sub_value, list):
                        cleaned_indexes = []
                        for index_item in sub_value:
                            if isinstance(index_item, tuple) and len(index_item) == 2:
                                start, end = index_item
                                if isinstance(start, str):
                                    start = int(re.sub(r'^\d+', '', start)) if re.sub(r'^\d+', '', start).isdigit() else start
                                if isinstance(end, str):
                                    end = int(re.sub(r'^\d+', '', end)) if re.sub(r'^\d+', '', end).isdigit() else end
                                cleaned_indexes.append((start, end))
                            else:
                                cleaned_indexes.append(index_item)
                        cleaned[key][sub_key] = cleaned_indexes
                    
                    else:
                        cleaned[key][sub_key] = clean_extra_data_numbers(sub_value)
            else:
                cleaned[key] = clean_extra_data_numbers(value)
        return cleaned
    elif isinstance(data, list):
        return [clean_extra_data_numbers(item) for item in data]
    else:
        return data

def process_single_json_file(input_json, output_file: str, json_index: int, total_jsons: int = 12):
    """
    处理单个JSON文件
    
    Args:
        input_json: 输入JSON数据（字典或列表）
        output_file: 输出文件路径
        output_file: 输出文件路径
        json_index: 当前JSON文件的索引
        total_jsons: 总的JSON文件数量
    """
    print(f"\n{'#'*60}")
    #print(f"处理第 {json_index + 1} 个JSON文件: {input_file}")
    print(f"文件位置: {'前7个' if json_index < 7 else '后5个'}")
    print(f"{'#'*60}")
    
    try:
        # 加载原始数据
        
        original_json = input_json
        
        # 修改：适配 test2.json 的结构
        if isinstance(original_json, dict):
            # 检查是否为 test2.json 的嵌套结构
            if "partitions" in original_json and "output" in original_json["partitions"]:
                original_data = original_json["partitions"]["output"]
                print(f"从 partitions.output 加载了 {len(original_data)} 条原始数据")
            elif "output" in original_json:
                original_data = original_json["output"]
                print(f"从 output 加载了 {len(original_data)} 条原始数据")
            else:
                # 如果都没有，尝试获取任意一个可能是数据数组的键
                possible_data_keys = ['data', 'items', 'content', 'results']
                found = False
                for key in possible_data_keys:
                    if key in original_json and isinstance(original_json[key], list):
                        original_data = original_json[key]
                        print(f"从 {key} 加载了 {len(original_data)} 条原始数据")
                        found = True
                        break
                if not found:
                    raise ValueError("输入JSON格式不符合预期：找不到包含数据的数组")
        elif isinstance(original_json, list):
            original_data = original_json
            print(f"直接使用数组数据，共 {len(original_data)} 条")
        else:
            raise ValueError("输入JSON格式不符合预期")
        
        # 统计各种类型的数量
        type_counts = {}
        chinese_sub_types = []  # 记录汉字sub_type的项
        
        for idx, item in enumerate(original_data):
            item_type = item.get("type", "")
            type_counts[item_type] = type_counts.get(item_type, 0) + 1
            
            # 检查是否为汉字类型
            if contains_chinese(item_type):
                chinese_sub_types.append((idx, item_type))
        
        print(f"原始数据类型统计:")
        for item_type, count in type_counts.items():
            print(f"  {item_type}: {count}")
        
        # 显示汉字sub_type统计
        if chinese_sub_types:
            print(f"\n找到 {len(chinese_sub_types)} 个汉字sub_type:")
            for idx, chinese_type in chinese_sub_types[:5]:  # 只显示前5个
                print(f"  索引 {idx}: {chinese_type}")
            
            # 根据位置确定应该转换为什么
            if json_index < 7:
                target_type = "Official_Header"
            elif json_index >= total_jsons - 5:
                target_type = "Colophon"
            else:
                target_type = "保持原样"
            
            print(f"  这些汉字sub_type将转换为: {target_type}")
        
        # 转换格式
        print(f"\n开始转换格式...")
        converted_data = convert_original_to_target(original_data)
        
        # 统计sub_type转换情况
        official_header_count = 0
        colophon_count = 0
        
        for item in converted_data:
            sub_type = item.get("sub_type", "")
            if sub_type == "Official_Header":
                official_header_count += 1
            elif sub_type == "Colophon":
                colophon_count += 1
        
        if official_header_count > 0:
            print(f"转换为Official_Header的数量: {official_header_count}")
        if colophon_count > 0:
            print(f"转换为Colophon的数量: {colophon_count}")
        
        # 清理extra_data中的数字前缀问题
        cleaned_data = clean_extra_data_numbers(converted_data)
        
        # 保存转换后的数据
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(cleaned_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n转换完成！已将数据保存到 {output_file}")
        
        # 显示转换结果示例
        if cleaned_data:
            print(f"\n转换结果示例:")
            for idx, item in enumerate(cleaned_data[:3]):  # 只显示前3个
                item_type = item.get("type", "")
                sub_type = item.get("sub_type", "")
                caption = item.get("caption", "")
                text_preview = item.get("text", "")[:100]
                
                print(f"  索引 {idx}: type={item_type}, sub_type={sub_type}")
                if caption:
                    print(f"    caption: {caption[:100]}{'...' if len(caption) > 100 else ''}")
                if text_preview:
                    print(f"    text预览: {text_preview}{'...' if len(item.get('text', '')) > 100 else ''}")
                print()
        
        return True
        
    except Exception as e:
        #print(f"处理文件 {input_file} 过程中出错: {e}")
        import traceback
        traceback.print_exc()
        return False

def load_and_process_json(input_json, output_file: str):
    """
    加载原始JSON文件，转换格式，并保存为新的JSON文件
    """
    # 处理单个文件
    process_single_json_file(input_json, output_file, json_index=0, total_jsons=1)

def main():
    """
    主函数：执行JSON格式转换
    """
    # 配置输入输出文件路径
    input_json_file = "test2.json"
    output_json_file = "test2_result.json"
    
    print("开始JSON格式转换...")
    print(f"输入文件: {input_json_file}")
    print(f"输出文件: {output_json_file}")
    print("-" * 50)
    
    # 执行转换
    load_and_process_json(input_json, output_json_file)
    
    # 验证转换结果
    print("\n" + "=" * 50)
    print("转换完成！")

if __name__ == "__main__":
    main()