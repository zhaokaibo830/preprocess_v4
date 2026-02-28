# jsonchangefinal.py
import json
import re
import copy
from typing import Dict, List, Any

def extract_content_from_element(element):
    """从元素中提取完整文本内容"""
    content_parts = []
    
    # 直接从 text 字段提取（你的JSON有这个字段）
    if "text" in element and element["text"]:
        content = str(element["text"])
        content_parts.append(content)
    
    # 如果没有 text 字段，尝试其他方式
    elif "content" in element and element["content"]:
        content = str(element["content"])
        content_parts.append(content)
    
    # 从 lines 中提取（备用）
    elif "lines" in element:
        for line in element.get("lines", []):
            for span in line.get("spans", []):
                if span.get("type") == "text":
                    content = span.get("content", "")
                    if content:
                        content_parts.append(content)
    
    # 合并所有文本
    result = " ".join(content_parts)
    
    # 清理空白字符
    result = re.sub(r'\s+', ' ', result).strip()
    
    return result

def normalize_content(content: str) -> str:
    """规范化内容，用于匹配"""
    if not content:
        return ""
    
    # 去除多余空白
    content = re.sub(r'\s+', ' ', content)
    # 去除首尾空白
    content = content.strip()
    # 去除特殊字符但保留中文和数字
    content = re.sub(r'[^\w\s\u4e00-\u9fff]', '', content)
    
    return content

def find_best_match(content: str, content_to_type: Dict[str, str]) -> tuple:
    """
    查找最佳匹配的内容
    
    Returns:
        (matched_type, matched_key) 匹配到的类型和匹配的key
    """
    if not content:
        return None, None
    
    normalized_content = normalize_content(content)
    
    # 1. 精确匹配
    if normalized_content in content_to_type:
        print(f"    精确匹配成功")
        return content_to_type[normalized_content], normalized_content
    
    # 2. 包含关系匹配
    for key, value in content_to_type.items():
        normalized_key = normalize_content(key)
        
        # 检查是否包含（双向）
        if (normalized_key in normalized_content) or (normalized_content in normalized_key):
            # 计算长度比例，避免过短的匹配
            len_ratio = min(len(normalized_key), len(normalized_content)) / max(len(normalized_key), len(normalized_content))
            if len_ratio > 0.3:  # 相似度阈值
                print(f"    包含匹配: '{normalized_key[:30]}' 包含在 '{normalized_content[:30]}' 中")
                return value, key
    
    return None, None

def update_json_in_memory(original_json: Any, extracted_json: Dict) -> Any:
    """
    在内存中修改JSON数据
    """
    print(f"\n开始修改JSON数据...")
    
    # 深拷贝原始数据，避免修改原数据
    modified_json = copy.deepcopy(original_json)
    
    # 构建 content -> type 映射
    content_to_type = {}
    
    for result in extracted_json.get("results", []):
        image_name = result.get("image_name", "unknown")
        for item in result.get("classified_items", []):
            content = item.get("content")
            typ = item.get("type")
            if content and typ:
                normalized = normalize_content(content)
                content_to_type[normalized] = typ
                print(f"  添加映射: '{content[:50]}...' -> {typ} (来自 {image_name})")
    
    print(f"从提取的JSON中加载了 {len(content_to_type)} 个 (content, type) 映射")
    
    # 处理原始JSON - 适配 test.json 的格式
    if isinstance(modified_json, dict):
        print(f"原始JSON是字典，keys: {list(modified_json.keys())}")
        
        # test.json 的格式：有 partitions 数组
        if "partitions" in modified_json:
            data_to_process = modified_json["partitions"]
            print(f"从 partitions 字段获取数据，长度: {len(data_to_process)}")
        else:
            data_to_process = []
            print(f"未找到 partitions 字段")
    
    elif isinstance(modified_json, list):
        data_to_process = modified_json
        print(f"原始JSON是列表，长度: {len(data_to_process)}")
    
    else:
        data_to_process = [modified_json] if modified_json else []
        print(f"原始JSON是其他类型: {type(modified_json)}")
    
    updated_count = 0
    updated_elements = []  # 记录更新的元素索引和内容
    
    print(f"\n开始匹配和更新，共 {len(data_to_process)} 个元素...")
    
    for idx, element in enumerate(data_to_process):
        print(f"\n处理元素 [{idx}], 类型: {element.get('type', 'unknown')}")
        
        # 提取当前元素的内容
        current_content = extract_content_from_element(element)
        
        if not current_content:
            print(f"  ❌ 元素 {idx} 无内容，跳过")
            continue
        
        normalized_current = normalize_content(current_content)
        print(f"  内容: '{current_content[:50]}...'")
        
        # 尝试匹配
        matched_type, matched_key = find_best_match(normalized_current, content_to_type)
        
        if matched_type:
            old_type = element.get("type", "N/A")
            old_sub_type = element.get("sub_type", "N/A")
            
            # 更新 type 字段
            element["type"] = matched_type
            
            # 根据匹配的类型更新 sub_type
            if matched_type == "版头":
                element["sub_type"] = "Official_Header"
            elif matched_type == "版记":
                element["sub_type"] = "Colophon"
            
            updated_count += 1
            updated_elements.append({
                "index": idx,
                "content": current_content[:50],
                "old_type": old_type,
                "new_type": matched_type,
                "old_sub_type": old_sub_type,
                "new_sub_type": element.get("sub_type")
            })
            
            print(f"  ✅ 更新: '{current_content[:30]}...'")
            print(f"     类型: '{old_type}' → '{matched_type}'")
            print(f"     子类型: '{old_sub_type}' → '{element.get('sub_type', 'N/A')}'")
        else:
            print(f"  ❌ 未匹配: '{current_content[:30]}...'")
    
    # 确保修改被保存回原结构
    if isinstance(modified_json, dict) and "partitions" in modified_json:
        # 已经直接修改了 partitions 中的元素，不需要额外操作
        pass
    
    print(f"\n✅ 处理完成！共更新了 {updated_count} 个元素")
    
    # 打印更新摘要
    if updated_elements:
        print("\n更新摘要:")
        for item in updated_elements:
            print(f"  元素 {item['index']}: '{item['content']}'")
            print(f"    {item['old_type']} ({item['old_sub_type']}) → {item['new_type']} ({item['new_sub_type']})")
    
    # 验证修改是否生效
    print("\n【验证修改】")
    if isinstance(modified_json, dict) and "partitions" in modified_json:
        for idx in [34, 35]:  # 检查你关注的两个元素
            if idx < len(modified_json["partitions"]):
                element = modified_json["partitions"][idx]
                print(f"元素 [{idx}]:")
                print(f"  type: {element.get('type')}")
                print(f"  sub_type: {element.get('sub_type')}")
                print(f"  text: {element.get('text')}")
    
    return modified_json

# 如果你想要更详细的调试，可以使用这个版本
def update_json_in_memory_debug(original_json: Any, extracted_json: Dict) -> Any:
    """
    调试版本的JSON修改函数
    """
    print("\n" + "="*60)
    print("开始修改JSON数据（调试模式）")
    print("="*60)
    
    result = update_json_in_memory(original_json, extracted_json)
    
    # 额外调试信息
    print("\n" + "="*60)
    print("调试信息:")
    print("="*60)
    
    if isinstance(result, dict) and "partitions" in result:
        print(f"返回的JSON类型: dict，有 partitions 数组，长度: {len(result['partitions'])}")
        
        # 检查第34和35个元素
        for idx in [34, 35]:
            if idx < len(result["partitions"]):
                element = result["partitions"][idx]
                print(f"\n元素 [{idx}] 最终状态:")
                print(f"  type: {element.get('type')}")
                print(f"  sub_type: {element.get('sub_type')}")
                print(f"  text: {element.get('text')}")
    
    return result