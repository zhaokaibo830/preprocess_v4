import json


def json_to_markdown(json_str) -> str:
    """
    将结果 JSON 字符串转换为 Markdown 格式。
    """
    data = json_str
    md_parts = []

    for item in data.get("partitions", []):
        item_type = item.get("type", "")
        text = item.get("text", "").strip()
        caption = item.get("caption", "").strip()
        table_html = item.get("data", "").strip()
        image_path = item.get("image_path", "").strip()

        # 标题
        if item_type == "Title":
            level = item.get("title_type", 1)
            level = max(1, min(level, 6))
            if text:
                md_parts.append(f'{"#" * level} {text}')

        # 正文
        elif item_type == "text":
            if text:
                md_parts.append(text)

        # 表格
        elif item_type == "Table":
            section = []

            # 描述
            if text:
                quoted_text = "\n".join(f"> {line}" for line in text.splitlines())
                section.append(quoted_text)

            # HTML 表格
            if table_html:
                section.append(table_html)

            # 表格标题
            if caption:
                section.append(f"*{caption}*")

            md_parts.append("\n\n".join(section))

        # 图片
        elif item_type == "Image":
            section = []

            # 描述
            if text:
                quoted_text = "\n".join(f"> {line}" for line in text.splitlines())
                section.append(quoted_text)

            # 图片
            if image_path:
                section.append(f"![]({image_path})")

            # 图片标题
            if caption:
                section.append(f"*{caption}*")

            md_parts.append("\n\n".join(section))

        # 其它类型默认输出 text
        else:
            if text:
                md_parts.append(text)

    return "\n\n".join(md_parts)

if __name__ == "__main__":
    with open("/home/bestwish/preprocessTest/test528/output/《西北电网稳定运行规定（2026第一版）》.json", "r", encoding="utf-8") as f:
        json_str = f.read()
    md_str = json_to_markdown(json_str)
    with open("/home/bestwish/preprocessTest/test528/output/《西北电网稳定运行规定（2026第一版）》.md", "w", encoding="utf-8") as f:
        f.write(md_str)