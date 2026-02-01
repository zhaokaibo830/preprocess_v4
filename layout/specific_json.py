import json
import re
from typing import Dict, List, Any, Tuple

def extract_text_from_item(item: Dict) -> str:
    """从原始数据项中提取文本内容"""
    
    # 处理table类型
    if item.get("type") == "table":
        print(f"DEBUG extract_text_from_item: 开始处理table类型")
        
        # 首先检查llm_process
        if "llm_process" in item:
            llm_data = item["llm_process"]
            print(f"DEBUG: llm_process存在，keys: {list(llm_data.keys())}")
            
            # 检查description字段
            if "description" in llm_data:
                description = llm_data["description"]
                print(f"DEBUG: 找到description字段，类型: {type(description)}")
                print(f"DEBUG: description值预览: {str(description)[:200]}...")
                return str(description) if description is not None else ""
            else:
                print(f"DEBUG: llm_process中没有description字段")
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
    elif item.get("type") == "image":
        if "llm_process" in item and "desc" in item["llm_process"]:
            return str(item["llm_process"]["desc"]) if item["llm_process"]["desc"] is not None else ""
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
    
    # 处理其他类型（text, title, list等）
    else:
        # 从lines中提取文本
        if "lines" in item:
            texts = []
            for line in item["lines"]:
                if "spans" in line:
                    for span in line["spans"]:
                        if span.get("type") in ["text", "inline_equation"] and "content" in span:
                            texts.append(span["content"])
            return " ".join(texts)
        
        # 对于list类型，从blocks中提取
        elif "blocks" in item:
            texts = []
            for block in item.get("blocks", []):
                if "lines" in block:
                    for line in block["lines"]:
                        if "spans" in line:
                            for span in line["spans"]:
                                if span.get("type") == "text" and "content" in span:
                                    texts.append(span["content"])
            return " ".join(texts)
        
        return ""

def extract_table_html(item: Dict) -> str:
    """从table类型数据项中提取html"""
    if item.get("type") == "table":
        print(f"DEBUG extract_table_html: 处理table类型")
        
        # 尝试从llm_process中获取table_html
        if "llm_process" in item:
            llm_data = item["llm_process"]
            print(f"DEBUG: llm_process keys: {list(llm_data.keys())}")
            
            if "table_html" in llm_data:
                html = llm_data["table_html"]
                print(f"DEBUG: 找到table_html字段，类型: {type(html)}，长度: {len(str(html)) if html else 0}")
                return str(html) if html is not None else ""
            else:
                print(f"DEBUG: 没有找到table_html字段")
        
        # 尝试从blocks中获取html
        if "blocks" in item:
            for block in item.get("blocks", []):
                if "lines" in block:
                    for line in block["lines"]:
                        if "spans" in line:
                            for span in line["spans"]:
                                if span.get("type") == "table" and "html" in span:
                                    html = span["html"]
                                    print(f"DEBUG: 从span中提取到html，长度: {len(str(html)) if html else 0}")
                                    return str(html) if html is not None else ""
    
    return "无"

def extract_image_path(item: Dict) -> str:
    """从数据项中提取image_path"""
    if item.get("type") in ["table", "image"]:
        # 直接检查image_path字段
        if "image_path" in item:
            return item["image_path"]
        
        # 从blocks中查找image_path
        if "blocks" in item:
            for block in item.get("blocks", []):
                if "lines" in block:
                    for line in block["lines"]:
                        if "spans" in line:
                            for span in line["spans"]:
                                if span.get("type") in ["image", "table"] and "image_path" in span:
                                    return span["image_path"]
    
    return "无"

def extract_bbox(item: Dict) -> List:
    """从数据项中提取bbox信息"""
    if "bbox" in item:
        return item["bbox"]
    
    # 如果没有bbox，尝试从lines中获取
    if "lines" in item and item["lines"]:
        for line in item["lines"]:
            if "spans" in line and line["spans"]:
                bbox = line["spans"][0].get("bbox")
                if bbox:
                    return bbox
    
    return []

def convert_original_to_target(original_data: List[Dict]) -> List[Dict]:
    """
    将原始JSON数据转换为目标格式
    """
    converted_data = []
    
    for idx, item in enumerate(original_data):
        item_type = item.get("type", "")
        
        # 如果是table类型，打印详细调试信息
        if item_type == "table":
            print(f"\n{'='*60}")
            print(f"处理第 {idx} 条数据 (table类型)")
            print(f"{'='*60}")
        
        # 提取文本内容
        text_content = extract_text_from_item(item)
        
        # 如果是table类型且text_content为空，打印更多调试信息
        if item_type == "table":
            print(f"提取到的text_content: {text_content[:100] if text_content else '空'}")
            print(f"text_content长度: {len(text_content)}")
            
            # 检查llm_process结构
            if "llm_process" in item:
                llm_data = item["llm_process"]
                print(f"llm_process详细结构:")
                for key, value in llm_data.items():
                    if key == "description":
                        print(f"  description (类型: {type(value)}, 长度: {len(str(value)) if value else 0}):")
                        print(f"    内容预览: {str(value)[:200] if value else '空'}...")
                    elif key == "table_html":
                        print(f"  table_html (类型: {type(value)}, 长度: {len(str(value)) if value else 0})")
                    else:
                        print(f"  {key}: (类型: {type(value)})")
        
        # 提取data字段（对于table是html）
        data_content = extract_table_html(item) if item_type == "table" else "无"
        
        # 创建新的数据结构
        new_item = {
            "type": item_type,
            "title_type": item.get("level", -1) if item_type == "title" else -1,
            "text": text_content,
            "data": data_content,
            "image_path": extract_image_path(item),
            "metadata": {
                "extra_data": {
                    "types": [item_type],
                    "pages": [item.get("page_idx", 0) + 1],
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
                                            cleaned_bbox.append(cleaned_coord)
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

def load_and_process_json(input_json, output_file: str):
    """
    加载原始JSON文件，转换格式，并保存为新的JSON文件
    """
    try:
        # 加载原始数据
        
        original_json = input_json
        
        # 提取output数组
        if isinstance(original_json, dict) and "output" in original_json:
            original_data = original_json["output"]
        elif isinstance(original_json, list):
            original_data = original_json
        else:
            raise ValueError("输入JSON格式不符合预期")
        
        print(f"加载了 {len(original_data)} 条原始数据")
        
        # 查找table类型的数量
        table_indices = []
        for idx, item in enumerate(original_data):
            if item.get("type") == "table":
                table_indices.append(idx)
        
        print(f"找到 {len(table_indices)} 个table类型数据，索引: {table_indices}")
        
        # 特别检查第一个table
        if table_indices:
            first_table_idx = table_indices[0]
            print(f"\n检查第一个table（索引 {first_table_idx}）:")
            table_item = original_data[first_table_idx]
            print(f"  数据结构keys: {list(table_item.keys())}")
            
            if "llm_process" in table_item:
                llm_data = table_item["llm_process"]
                print(f"  llm_process keys: {list(llm_data.keys())}")
                
                if "description" in llm_data:
                    desc = llm_data["description"]
                    print(f"  description类型: {type(desc)}")
                    print(f"  description长度: {len(str(desc)) if desc else 0}")
                    print(f"  description前200字符: {str(desc)[:200] if desc else '空'}")
                else:
                    print(f"  警告: 没有找到description字段")
            else:
                print(f"  警告: 没有llm_process字段")
        
        # 转换格式
        print(f"\n开始转换格式...")
        converted_data = convert_original_to_target(original_data)
        
        # 清理extra_data中的数字前缀问题
        cleaned_data = clean_extra_data_numbers(converted_data)
        
        # 保存转换后的数据
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(cleaned_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n转换完成！已将数据保存到 {output_file}")
        
        # 统计table转换结果
        table_results = []
        for idx, item in enumerate(cleaned_data):
            if item.get("type") == "table":
                table_results.append({
                    "index": idx,
                    "text_length": len(item.get("text", "")),
                    "data_length": len(item.get("data", "")),
                    "has_text": bool(item.get("text"))
                })
        
        print(f"\nTable转换结果统计:")
        print(f"  共 {len(table_results)} 个table")
        for result in table_results:
            status = "✓ 有text" if result["has_text"] else "✗ 无text"
            print(f"  索引 {result['index']}: {status}, text长度: {result['text_length']}, data长度: {result['data_length']}")
        
        # 打印第一个table的完整结果
        for idx, item in enumerate(cleaned_data):
            if item.get("type") == "table":
                print(f"\n第一个table（索引{idx}）转换结果:")
                print(f"  text长度: {len(item.get('text', ''))}")
                if item.get("text"):
                    print(f"  text前200字符: {item['text'][:200]}...")
                print(f"  data长度: {len(item.get('data', ''))}")
                print(f"  image_path: {item.get('image_path', '无')}")
                break
            
    except Exception as e:
        print(f"处理过程中出错: {e}")
        import traceback
        traceback.print_exc()

def main():
    """
    主函数：执行JSON格式转换
    """
    # 配置输入输出文件路径
    input_json_file = "demo.json"
    output_json_file = "converted_demo_final.json"
    
    print("开始JSON格式转换...")
    print(f"输入文件: {input_json_file}")
    print(f"输出文件: {output_json_file}")
    print("-" * 50)
    
    # 执行转换
    load_and_process_json(input_json_file, output_json_file)
    
    # 验证转换结果
    print("\n" + "=" * 50)
    print("转换完成！")

if __name__ == "__main__":
    main()