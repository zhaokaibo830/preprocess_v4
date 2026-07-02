from pathlib import Path
from .tools import table_extract_async


import asyncio
from pathlib import Path


async def add_table_info(
    full_json_data,
    vlm_enable,
    client,
    model_name,
    output_path,
    folder_name,
    table_kv: bool = True,
    table_desc: bool = True,
    table_html: bool = True,
):
    """
    异步版：所有表格并发处理；错误各自独立，不熔断。
    单表内部 kv 和 desc 两次 LLM 调用也并行。
    并发上限由 client 底层 httpx.Limits(max_connections=...) 控制。
    """
    table_error_msg = ""

    if not (table_kv or table_desc or table_html):
        print("表格处理选项为空，跳过表格处理步骤。")
        return full_json_data, table_error_msg, 0

    def build_table_error_json(reason, original_html: str = ""):
        err_dict = {"type": "table"}
        if table_kv:
            err_dict["key_value"] = [{"error": "数据提取失败", "details": reason}]
        if table_desc:
            err_dict["description"] = f"表格分析失败: {reason}"
        if table_html:
            err_dict["table_html"] = original_html
        return err_dict

    # ---- 收集所有 table block ----
    subdir = "vlm" if vlm_enable else "auto"
    items = []  # [(block, table_html_str, table_title), ...]

    for block_index, block in enumerate(full_json_data["output"]):
        if block["type"] != "table":
            continue

        table_html_str = ""   # ⚠️ 局部变量重命名，避免遮蔽外层 bool 参数 table_html
        table_title = ""

        for sub_block in block["blocks"]:
            if sub_block["type"] == "table_body":
                try:
                    # 路径这里其实没被 LLM 调用用到，保留只是为了兼容原来的 excel 导出逻辑
                    _ = Path(output_path) / folder_name / subdir / "images" / sub_block["lines"][0]["spans"][0]["image_path"]
                    table_html_str = sub_block["lines"][0]["spans"][0]["html"]
                except (IndexError, KeyError, TypeError):
                    table_html_str = ""
                    continue
            elif sub_block["type"] == "table_caption":
                try:
                    table_title = sub_block["lines"][0]["spans"][0]["content"]
                except (IndexError, KeyError, TypeError):
                    table_title = ""

        if not table_html_str:
            print(f"[WARN] 表格 {block_index} 缺少 HTML 内容，跳过 LLM 处理")
            continue

        items.append((block, table_html_str, table_title))

    table_count = len(items)
    if table_count == 0:
        print("未发现有效表格，跳过表格处理步骤。")
        return full_json_data, table_error_msg, 0

    # ---- 每个表格起一个 coroutine，异常在函数内 catch，不抛出 ----
    async def process_one(block, table_html_str, table_title):
        try:
            block["llm_process"] = await table_extract_async(
                table_html_input=table_html_str,
                title=table_title,
                table_kv=table_kv,
                table_desc=table_desc,
                table_html=table_html,   # 现在这里是纯粹的 bool，语义正确
                client=client,
                model_name=model_name,
            )
            return None
        except Exception as e:
            err = str(e)
            block["llm_process"] = build_table_error_json(err, original_html=table_html_str)
            print(f"表格处理失败: {err}")
            return err

    errs = await asyncio.gather(
        *(process_one(b, h, t) for b, h, t in items)
    )

    for e in errs:
        if e:
            table_error_msg = e
            break

    print(f"已处理{table_count}张表格")
    return full_json_data, table_error_msg, table_count

"""
def add_table_info(full_json_data, vlm_enable, client,model_name,output_path,folder_name, table_kv = True,table_desc = True, table_html = True):
    table_error_msg = ""
    if table_kv or table_desc or table_html:

        def build_table_error_json(reason):
                err_dict = {"type": "table"} # 表格固定有 type
                if table_kv:
                    # 正常是 list[dict]，报错也给个 list[dict]
                    err_dict["key_value"] = [{"error": "数据提取失败", "details": reason}]
                if table_desc:
                    err_dict["description"] = f"表格分析失败: {reason}"
                if table_html:
                    err_dict["table_html"] = block.get("table_html", "") # 失败则保留原html或报错信息
                return err_dict

        #table_start_time=time.perf_counter()
        #print(f"表格处理选项为{table_config}，开始处理表格...")
        table_count=0
        stop_processing_table = False
        final_table_error = ""
        table_jobs = []
        for block_index,block in enumerate(full_json_data["output"]):
            if block["type"] == "table":

                if stop_processing_table:
                    block["llm_process"] = build_table_error_json(f"处理中断: {final_table_error}")
                    table_count += 1
                    continue
                table_html=""
                table_title=""
                for sub_block_index , sub_block in enumerate(block["blocks"]):
                    
                    if sub_block["type"] == "table_body":
                        try:
                            table_path=sub_block["lines"][0]["spans"][0]["image_path"]
                            if vlm_enable:
                                table_path=Path(output_path)/folder_name/'vlm'/'images'/table_path
                            else:
                                table_path=Path(output_path)/folder_name/'auto'/'images'/table_path
                            table_jobs.append([sub_block["lines"][0]["spans"][0]["html"], table_path])
                            table_html=sub_block["lines"][0]["spans"][0]["html"]
                            table_count+=1
                        except (IndexError, KeyError, TypeError):
                            table_html=""
                            continue
                    elif sub_block["type"] == "table_caption":
                        try:
                            table_title=sub_block["lines"][0]["spans"][0]["content"]
                        except (IndexError, KeyError, TypeError):
                            table_title = ""
                if not table_html:
                    print(f"[WARN] 表格 {block_index} 缺少 HTML 内容，跳过 LLM 处理")
                    
                    continue
                try:
                    result = table_extract(
                        table_html_input=table_html,
                        title=table_title,
                        table_kv=table_kv,
                        table_desc=table_desc,
                        table_html=table_html,
                        client=client,
                        model_name=model_name
                        ),
                    block["llm_process"] = result
                except Exception as e:
                    # 3. 捕获 raise 抛出的错误，启动熔断
                    stop_processing_table = True
                    final_table_error = str(e)
                    table_error_msg = final_table_error
                    block["llm_process"] = build_table_error_json(f"处理中断: {final_table_error}")
                    print(f"表格处理熔断：第 {table_count} 个表格出错: {final_table_error}")
                
        print(f"已处理{table_count}张表格")
        
        if 'html' in table_config:#如果有html参数，保存excel文件
            excel_output_dir=Path(output_path)/folder_name/('vlm' if vlm_enable else 'auto')/'tables_excel'
            excel_output_dir.mkdir(parents=True,exist_ok=True)
            for table_html, table_path in table_jobs:
                table_name=Path(table_path).stem+'.xlsx'
                excel_output_path=excel_output_dir/table_name
                html_to_excel_openpyxl(table_html,str(excel_output_path))
        
        print(f"已处理{table_count}张表格")
        #table_time_end=time.perf_counter()
    else:
        print("表格处理选项为空，跳过表格处理步骤。")
        #table_start_time=0
        #table_time_end=0
        table_count=0
    return full_json_data, table_error_msg,table_count
"""