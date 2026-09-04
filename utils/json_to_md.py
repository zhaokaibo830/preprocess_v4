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

def extract_text(item: dict) -> str:
    """
    递归提取文本，同时处理公式 span
    """
    texts = []

    for line in item.get("lines", []):
        line_parts = []

        for span in line.get("spans", []):

            span_type = span.get("type", "")

            # 普通文本
            if span_type == "text":
                line_parts.append(span.get("content", ""))

            # 行内公式
            elif span_type == "inline_equation":
                formula = (
                    span.get("latex")
                    or span.get("content")
                    or ""
                )
                line_parts.append(f"${formula}$")

            # 块公式
            elif span_type == "equation":
                formula = (
                    span.get("latex")
                    or span.get("content")
                    or ""
                )
                line_parts.append(f"\n$$\n{formula}\n$$\n")

        if line_parts:
            texts.append("".join(line_parts))

    for block in item.get("blocks", []):
        text = extract_text(block)
        if text:
            texts.append(text)

    return "\n".join(texts)


def find_span_by_type(item: dict, span_type: str):
    """
    查找指定 type 的 span
    """
    for block in item.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if span.get("type") == span_type:
                    return span
    return None


def quote_block(text: str) -> str:
    """
    多行 Markdown 引用
    """
    return "\n".join(
        f"> {line}" if line else ">"
        for line in text.splitlines()
    )


def custom_json_to_markdown(json_str: str) -> str:
    """
    将 interface2 结果 JSON 字符串转换为 Markdown 格式。
    """
    data = json_str

    outputs = data.get("partitions", {}).get("output", [])

    md = []

    for item in outputs:

        item_type = item.get("type", "").lower()

        # 忽略
        if item_type in {
            "page_number",
            "header",
            "footer",
            "abandoned"
        }:
            continue

        # Title
        if item_type == "title":

            text = extract_text(item).strip()

            if text:
                level = max(1, min(item.get("level", 1), 6))
                md.append(f'{"#" * level} {text}')

        # Text
        elif item_type == "text":

            text = extract_text(item).strip()

            if text:
                md.append(text)

        # List
        elif item_type == "list":

            text = extract_text(item).strip()

            if text:
                md.append(text)

        # Image
        elif item_type == "image":

            section = []

            # AI 描述
            desc = item.get("llm_process", {}).get("desc", "").strip()

            if desc:
                section.append(quote_block(desc))

            span = find_span_by_type(item, "image")

            if span:

                image_path = span.get("image_path", "")

                if image_path:
                    section.append(f"![]({image_path})")

            if section:
                md.append("\n\n".join(section))

        # Table
        elif item_type == "table":

            section = []

            llm = item.get("llm_process", {})

            description = llm.get("description", "").strip()

            if description:
                section.append(quote_block(description))

            table_html = llm.get("table_html", "")

            if not table_html:

                span = find_span_by_type(item, "table")

                if span:
                    table_html = span.get("html", "")

            if table_html:
                section.append(table_html)

            if section:
                md.append("\n\n".join(section))

        # Block Equation
        elif item_type == "equation":

            span = find_span_by_type(item, "equation")

            if span:

                latex = span.get("latex", "").strip()

                if latex:
                    md.append(f"\n$$\n{latex}\n$$\n")

        # Inline Equation
        elif item_type == "inline_equation":

            span = find_span_by_type(item, "inline_equation")

            if span:

                latex = span.get("latex", "").strip()

                if latex:
                    md.append(f"${latex}$")

        # 其它
        else:

            text = extract_text(item).strip()

            if text:
                md.append(text)

    return "\n\n".join(md)

if __name__ == "__main__":
    with open("/home/bestwish/preprocessTest/test704/output/long_text_9793997b-b977-4637-873e-cfa454e2d7bb.txt", "r", encoding="utf-8") as f:
        json_str = f.read()
    md_str = custom_json_to_markdown(json_str)
    with open("/home/bestwish/preprocessTest/test704/output/long_text_9793997b-b977-4637-873e-cfa454e2d7bb.md", "w", encoding="utf-8") as f:
        f.write(md_str)