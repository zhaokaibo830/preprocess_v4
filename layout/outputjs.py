import json

def merge_blocks(json_data):
    # 确保 pdf_info 存在
    if "pdf_info" not in json_data:
        raise ValueError("JSON中缺少 'pdf_info' 字段")
    
    for page in json_data["pdf_info"]:
        para_blocks = page.get("para_blocks", [])
        discarded_blocks = page.get("discarded_blocks", [])
        
        # 合并两个列表
        merged_blocks = para_blocks + discarded_blocks
        
        # 移除原字段
        if "para_blocks" in page:
            del page["para_blocks"]
        if "discarded_blocks" in page:
            del page["discarded_blocks"]
        
        # 添加新的 result 字段
        page["result"] = merged_blocks
    
    return json_data


if __name__=="__main__":
    # 读取JSON文件
    with open("/root/autodl-tmp/pdf/test_output/demo0/vlm/demo0_middle.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    # 处理数据
    processed_data = merge_blocks(data)


    output_data = {"output": processed_data["pdf_info"]}

    # 保存到新文件
    with open("demo0_middle_final.json", "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print("处理完成，已保存到 demo0_middle_final.json")