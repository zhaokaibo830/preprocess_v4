import json

def extract_content_from_element(element):
    """从 demo4.json 的一个 output 元素中提取完整文本内容"""
    content_parts = []
    for line in element.get("lines", []):
        for span in line.get("spans", []):
            if span.get("type") == "text":  # 确保只取文本类型
                content_parts.append(span.get("content", ""))
    return "".join(content_parts)

def main():
    # 1. 加载 extracted_texts.json 并构建 content -> type 映射
    with open("extracted_texts.json", "r", encoding="utf-8") as f:
        extracted_data = json.load(f)
    
    content_to_type = {}
    # 遍历 results 列表
    for result in extracted_data.get("results", []):
        if result.get("status") != "success":
            continue
        for item in result.get("items", []):
            content = item.get("content")
            typ = item.get("type")
            if content is not None and typ is not None:
                # 如果同一个 content 有多个 type，后面的会覆盖前面的
                content_to_type[content] = typ

    print(f"从 extracted_texts.json 中加载了 {len(content_to_type)} 个 (content, type) 映射。")

    # 2. 加载 demo4.json
    with open("demo4.json", "r", encoding="utf-8") as f:
        demo4 = json.load(f)

    # 3. 遍历 output，匹配 content 并更新 type
    updated_count = 0
    for element in demo4.get("output", []):
        current_content = extract_content_from_element(element)
        if current_content in content_to_type:
            new_type = content_to_type[current_content]
            old_type = element.get("type", "N/A")
            element["type"] = new_type
            updated_count += 1
            print(f"[更新] 内容: '{current_content}' | 类型: '{old_type}' → '{new_type}'")

    # 4. 保存结果到新文件
    with open("demo4_updated.json", "w", encoding="utf-8") as f:
        json.dump(demo4, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 处理完成！共更新了 {updated_count} 个元素。")
    print("结果已保存到 'demo4_updated.json'")

if __name__ == "__main__":
    main()