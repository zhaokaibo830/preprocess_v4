import json
import re
from typing import Dict, List, Any, Tuple, Union

def convert_json_format(json_data: Union[Dict, List]) -> List[Dict]:
    """
    将原始数据转换为目标格式。
    修复了元组(tuple)兼容性、int('')转换崩溃以及dict变量入口解析问题。
    """
    
    def extract_text_from_item(item: Dict) -> str:
        item_type = item.get("type", "")
        if item_type == "table":
            if "llm_process" in item:
                llm_data = item["llm_process"]
                if isinstance(llm_data, (list, tuple)):
                    for llm_item in llm_data:
                        if isinstance(llm_item, dict):
                            res = llm_item.get("description") or llm_item.get("desc")
                            if res: return str(res)
                elif isinstance(llm_data, dict):
                    res = llm_data.get("description") or llm_data.get("desc")
                    if res: return str(res)
            
            if "blocks" in item:
                table_texts = []
                for block in item.get("blocks", []):
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            if span.get("type") == "text" and "content" in span:
                                table_texts.append(span["content"])
                return " ".join(table_texts)
            return ""
        
        elif item_type == "image":
            if "llm_process" in item:
                llm_data = item["llm_process"]
                if isinstance(llm_data, (list, tuple)):
                    for llm_item in llm_data:
                        if isinstance(llm_item, dict) and "desc" in llm_item:
                            return str(llm_item["desc"])
                elif isinstance(llm_data, dict) and "desc" in llm_data:
                    return str(llm_data["desc"])
            
            if "blocks" in item:
                for block in item.get("blocks", []):
                    if block.get("type") == "image_caption":
                        for line in block.get("lines", []):
                            for span in line.get("spans", []):
                                if span.get("type") == "text" and "content" in span:
                                    return span["content"]
            return ""
        
        else:
            texts = []
            target_keys = ["lines", "blocks"]
            for key in target_keys:
                if key in item:
                    for entry in item[key]:
                        for line in (entry.get("lines", [entry]) if key == "blocks" else [entry]):
                            for span in line.get("spans", []):
                                if span.get("type") in ["text", "inline_equation", "interline_equation"] and "content" in span:
                                    texts.append(span["content"])
            return " ".join(texts)

    def extract_table_html(item: Dict) -> str:
        if item.get("type") == "table":
            if "llm_process" in item:
                llm_data = item["llm_process"]
                if isinstance(llm_data, (list, tuple)):
                    for llm_item in llm_data:
                        if isinstance(llm_item, dict) and "table_html" in llm_item:
                            return str(llm_item["table_html"])
                elif isinstance(llm_data, dict) and "table_html" in llm_data:
                    return str(llm_data["table_html"])
            
            for block in item.get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        if span.get("type") == "table" and "html" in span:
                            return str(span["html"])
        return ""

    def extract_caption_from_item(item: Dict) -> str:
        item_type = item.get("type", "")
        if item_type in ["table", "image"] and "blocks" in item:
            caps = []
            for block in item["blocks"]:
                if block.get("type") in ["table_caption", "image_caption"]:
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            if span.get("type") == "text" and "content" in span:
                                caps.append(span["content"])
            return " ".join(caps)
        return ""

    def extract_image_path(item: Dict) -> str:
        if "image_path" in item: return item["image_path"]
        for key in ["lines", "blocks"]:
            for entry in item.get(key, []):
                for line in (entry.get("lines", [entry]) if key == "blocks" else [entry]):
                    for span in line.get("spans", []):
                        if "image_path" in span: return span["image_path"]
        return ""

    def extract_bbox(item: Dict) -> List:
        if "bbox" in item: return item["bbox"]
        for key in ["lines", "blocks"]:
            for entry in item.get(key, []):
                for span in entry.get("spans", []):
                    if "bbox" in span: return span["bbox"]
        return []

    def normalize_type(original_type: str) -> Tuple[str, str]:
        if original_type == "page_number": return (None, "page_number")
        if original_type in ["title", "table", "image"]:
            return (original_type.capitalize(), original_type if original_type == "text" else original_type.capitalize())
        return ("text", "text")

    def clean_extra_data_numbers(data):
        """修复 int() 转换空字符串导致的崩溃问题"""
        if isinstance(data, dict):
            cleaned = {}
            for key, value in data.items():
                if key == "extra_data" and isinstance(value, dict):
                    cleaned[key] = {}
                    for sk, sv in value.items():
                        if sk == "bboxes" and isinstance(sv, list):
                            new_bboxes = []
                            for b in sv:
                                if isinstance(b, list):
                                    new_box = []
                                    for c in b:
                                        # 安全转换逻辑：去掉正则，增加空值和数字判定
                                        s_val = str(c).strip()
                                        if s_val and (s_val.isdigit() or s_val.replace('.','',1).isdigit()):
                                            new_box.append(int(float(s_val)))
                                        else:
                                            new_box.append(c)
                                    new_bboxes.append(new_box)
                                else:
                                    new_bboxes.append(b)
                            cleaned[key][sk] = new_bboxes
                        else:
                            cleaned[key][sk] = clean_extra_data_numbers(sv)
                else:
                    cleaned[key] = clean_extra_data_numbers(value)
            return cleaned
        elif isinstance(data, (list, tuple)):
            return [clean_extra_data_numbers(i) for i in data]
        return data

    # 主入口逻辑：兼容不同层级的 dict
    if isinstance(json_data, dict):
        if "output" in json_data:
            original_data = json_data["output"]
        elif "partitions" in json_data and isinstance(json_data["partitions"], dict):
            original_data = json_data["partitions"].get("output", [])
        else:
            original_data = [json_data] if "type" in json_data else []
    else:
        original_data = json_data

    converted_data = []
    for item in original_data:
        norm_type, s_type = normalize_type(item.get("type", ""))
        if norm_type is None: continue
        
        text_content = extract_text_from_item(item)
        if norm_type == "Table" and not text_content.strip(): continue
        
        new_item = {
            "type": norm_type,
            "sub_type": s_type,
            "title_type": item.get("level", -1) if norm_type == "Title" else -1,
            "caption": extract_caption_from_item(item),
            "text": text_content,
            "data": extract_table_html(item),
            "image_path": extract_image_path(item),
            "metadata": {
                "extra_data": {
                    "types": [norm_type],
                    "pages": [item.get("page_idx", 0) + 1],
                    "bboxes": [extract_bbox(item)],
                    "indexes": [(0, len(text_content))] if text_content else []
                }
            }
        }
        converted_data.append(new_item)
    
    return clean_extra_data_numbers(converted_data)

if __name__ == "__main__":
    main()