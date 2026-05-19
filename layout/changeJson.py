import json


def modify_json_structure_complete(data):
    """
    完整修改JSON结构，包括：
    1. 删除每个页面的 "page_size" 字段
    2. 删除每个result中第一个 "bbox" 字段（文本块级别的bbox）
    3. 删除每个lines中第一个 "bbox" 字段（行级别的bbox）
    4. 将page_idx复制到每个result项目中的index字段上方（包括嵌套结构）
    5. 删除原始的page_idx字段
    6. 删除"lines"和"spans"字段下的page_idx，除非下一个字段是index
    7. 将所有页的result内容合并到第一个result中，然后将所有内容放在output底下
    8. 删除description字段里边的所有page_idx（包括key_value中的）
    9. 删除blocks字段里边的page_idx
    """

    def add_page_idx_to_item(item, page_idx_value):
        """为单个项目添加page_idx字段（放在index字段之前）"""
        if page_idx_value is not None and "page_idx" not in item:
            # 创建一个新字典，确保page_idx在index之前
            keys = list(item.keys())
            if "index" in keys:
                # 找到index的位置
                index_pos = keys.index("index")
                # 在index位置插入page_idx
                keys.insert(index_pos, "page_idx")
            else:
                # 如果没有index，就在最前面添加
                keys.insert(0, "page_idx")

            # 创建新的有序字典
            new_item = {}
            for key in keys:
                if key != "page_idx":  # 跳过刚刚添加的page_idx
                    new_item[key] = item[key]
                else:
                    new_item[key] = page_idx_value

            # 清空原item并更新
            item.clear()
            item.update(new_item)

        return item

    def process_nested_blocks(item, page_idx_value):
        """递归处理嵌套的blocks，添加page_idx"""
        if isinstance(item, dict):
            # 为当前项目添加page_idx
            item = add_page_idx_to_item(item, page_idx_value)

            # 递归处理嵌套结构
            for key, value in item.items():
                if key in ["blocks", "lines", "spans"] and isinstance(value, list):
                    for i, sub_item in enumerate(value):
                        if isinstance(sub_item, dict):
                            # 为嵌套项目添加page_idx
                            process_nested_blocks(sub_item, page_idx_value)

                # 处理其他可能的嵌套结构
                elif isinstance(value, dict):
                    process_nested_blocks(value, page_idx_value)
                elif isinstance(value, list):
                    for sub_item in value:
                        if isinstance(sub_item, dict):
                            process_nested_blocks(sub_item, page_idx_value)

        return item

    def remove_bbox_fields(item):
        """递归删除bbox字段，但保留spans中的bbox"""
        if isinstance(item, dict):
            # 删除result级别的bbox（文本块级别）
            if "bbox" in item and "lines" in item:
                del item["bbox"]

            # 删除lines级别的bbox（行级别）
            if "lines" in item and isinstance(item["lines"], list):
                for line in item["lines"]:
                    if isinstance(line, dict) and "bbox" in line:
                        # 检查是否是行级别的bbox（有spans子元素）
                        if "spans" in line:
                            del line["bbox"]

            # 递归处理嵌套结构
            for key, value in item.items():
                if isinstance(value, (dict, list)):
                    remove_bbox_fields(value)

        elif isinstance(item, list):
            for sub_item in item:
                remove_bbox_fields(sub_item)

        return item

    def remove_lines_spans_page_idx(item):
        """删除lines和spans字段下的page_idx，但保留那些下一个字段是index的page_idx"""
        if isinstance(item, dict):
            # 处理lines字段
            if "lines" in item and isinstance(item["lines"], list):
                for line in item["lines"]:
                    if isinstance(line, dict):
                        # 获取line的所有字段名
                        line_keys = list(line.keys())
                        if "page_idx" in line_keys:
                            page_idx_pos = line_keys.index("page_idx")

                            # 检查page_idx后面是否有字段，以及下一个字段是否为index
                            if page_idx_pos + 1 < len(line_keys):
                                next_field = line_keys[page_idx_pos + 1]
                                if next_field == "index":
                                    # 下一个字段是index，保留page_idx
                                    pass
                                else:
                                    # 下一个字段不是index，删除page_idx
                                    del line["page_idx"]
                            else:
                                # page_idx是最后一个字段，删除
                                del line["page_idx"]

                        # 处理spans字段
                        if "spans" in line and isinstance(line["spans"], list):
                            for span in line["spans"]:
                                if isinstance(span, dict):
                                    span_keys = list(span.keys())
                                    if "page_idx" in span_keys:
                                        page_idx_pos = span_keys.index("page_idx")

                                        # 检查page_idx后面是否有字段，以及下一个字段是否为index
                                        if page_idx_pos + 1 < len(span_keys):
                                            next_field = span_keys[page_idx_pos + 1]
                                            if next_field == "index":
                                                # 下一个字段是index，保留page_idx
                                                pass
                                            else:
                                                # 下一个字段不是index，删除page_idx
                                                del span["page_idx"]
                                        else:
                                            # page_idx是最后一个字段，删除
                                            del span["page_idx"]

            # 递归处理其他嵌套结构，但跳过已经处理的lines和spans
            for key, value in item.items():
                if key not in ["lines", "spans"]:  # 跳过已经处理的lines和spans
                    if isinstance(value, (dict, list)):
                        remove_lines_spans_page_idx(value)

        elif isinstance(item, list):
            for sub_item in item:
                remove_lines_spans_page_idx(sub_item)

        return item

    def remove_description_page_idx(item):
        """删除description字段中的所有page_idx（包括key_value中的）"""
        if isinstance(item, dict):
            # 处理description字段
            if "description" in item and isinstance(item["description"], dict):
                description_data = item["description"]

                # 1. 删除description根级别的page_idx
                if "page_idx" in description_data:
                    del description_data["page_idx"]

                # 2. 处理description中的key_value列表
                if "key_value" in description_data and isinstance(description_data["key_value"], list):
                    for kv_item in description_data["key_value"]:
                        if isinstance(kv_item, dict) and "page_idx" in kv_item:
                            del kv_item["page_idx"]

                # 3. 递归处理description内部的其他结构
                for key, value in description_data.items():
                    if key != "key_value":  # key_value已经处理过了
                        if isinstance(value, (dict, list)):
                            remove_description_page_idx(value)

            # 递归处理其他嵌套结构
            for key, value in item.items():
                if key != "description":  # description已经处理过了
                    if isinstance(value, (dict, list)):
                        remove_description_page_idx(value)

        elif isinstance(item, list):
            for sub_item in item:
                remove_description_page_idx(sub_item)

        return item

    def remove_blocks_page_idx(item):
        """递归删除blocks字段中的page_idx"""
        if isinstance(item, dict):
            # 处理blocks字段
            if "blocks" in item and isinstance(item["blocks"], list):
                for block in item["blocks"]:
                    if isinstance(block, dict) and "page_idx" in block:
                        # 删除blocks中的page_idx字段
                        del block["page_idx"]
                    # 递归处理blocks中的嵌套结构
                    remove_blocks_page_idx(block)

            # 递归处理其他嵌套结构
            for key, value in item.items():
                if key != "blocks":  # blocks已经处理过了
                    if isinstance(value, (dict, list)):
                        remove_blocks_page_idx(value)

        elif isinstance(item, list):
            for sub_item in item:
                remove_blocks_page_idx(sub_item)

        return item

    if "output" in data:
        # 收集所有页面的result内容
        all_result_items = []

        for page in data["output"]:
            # 1. 删除 page_size 字段
            if "page_size" in page:
                del page["page_size"]

            # 获取当前页面的page_idx
            page_idx_value = page.get("page_idx")

            # 处理result中的每个项目
            if "result" in page:
                for item in page["result"]:
                    # 4. 为每个项目添加page_idx字段（包括嵌套结构）
                    process_nested_blocks(item, page_idx_value)

                    # 6. 删除lines和spans字段下的page_idx（除非下一个字段是index）
                    remove_lines_spans_page_idx(item)

                    # 8. 删除description字段中的所有page_idx（包括key_value中的）
                    remove_description_page_idx(item)

                    # 9. 删除blocks字段中的page_idx
                    remove_blocks_page_idx(item)

                    # 2. & 3. 删除bbox字段
                    remove_bbox_fields(item)

                    # 收集当前页面的item到总列表中
                    all_result_items.append(item)

            # 5. 删除原始的page_idx字段
            if "page_idx" in page:
                del page["page_idx"]

        # 7. 将所有result内容合并到第一个result中
        if all_result_items:
            # 删除所有页面的result字段
            for page in data["output"]:
                if "result" in page:
                    del page["result"]

            # 将所有内容直接放在output下
            # 首先清空output，然后添加所有items
            data["output"] = all_result_items

            # 检查是否有空的页面对象
            # 如果有的话删除空对象
            data["output"] = [item for item in data["output"] if item]

    return data


# 主程序
def main():
    # 读取原始JSON文件
    input_file = "test.json"
    output_file = "test_modified.json"

    print(f"正在读取文件: {input_file}")
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        print("✅ 文件读取成功")
    except FileNotFoundError:
        print(f"❌ 文件不存在: {input_file}")
        print("请确保example.json文件在当前目录中")
        return
    except json.JSONDecodeError as e:
        print(f"❌ JSON解析错误: {e}")
        return

    # 应用完整修改
    print("正在应用修改...")
    modified_data = modify_json_structure_complete(json_data)

    # 保存结果
    print(f"正在保存到: {output_file}")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(modified_data, f, ensure_ascii=False, indent=2)
    print("✅ 文件保存成功")


def changeJson(json_data):
    # 读取原始JSON文件
    #input_file = json_path
    #output_file = "test_modified.json"


    """
    print(f"正在读取文件: {input_file}")
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        print("✅ 文件读取成功")
    except FileNotFoundError:
        print(f"❌ 文件不存在: {input_file}")
        print("请确保example.json文件在当前目录中")
        return
    except json.JSONDecodeError as e:
        print(f"❌ JSON解析错误: {e}")
        return
    """
    # 应用完整修改
    print("正在应用修改...")
    modified_data = modify_json_structure_complete(json_data)

    # 保存结果
    #print(f"正在保存到: {output_file}")
    #with open(output_file, 'w', encoding='utf-8') as f:
    #    json.dump(modified_data, f, ensure_ascii=False, indent=2)
    #print("✅ 文件保存成功")
    return modified_data

# 运行主程序
if __name__ == "__main__":
    main()

