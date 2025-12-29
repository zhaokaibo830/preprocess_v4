import json
import sys

import yaml


from images_tables.image.tools import analyze_image_content
from images_tables.table.tools import table_extract
from format.formatTransform import format
from layout.outputjs import merge_blocks
from layout.output_pipeline import merge_blocks_pipeline
from titles.get_title import *
from pathlib import Path
import subprocess
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
import uuid, os, json, shutil
from fastapi import HTTPException 
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse
from fastapi.responses import StreamingResponse
from images_tables.image.tools_async import analyze_image_content_async
from images_tables.table.tools_async import table_extract_async
import asyncio
from titles.title_process import *
import zipfile
import io
import time
from fastapi import Request
from urllib.parse import quote
app = FastAPI(
    docs_url=None,
    redoc_url=None
    )

@app.middleware("http")
async def add_process_time(request: Request, call_next):
    start = time.time()
    response = await call_next(request)     # 这里会执行你的 preprocess 函数
    cost = time.time() - start
    print(f"[{request.method}] {request.url.path} 耗时: {cost:.2f}s")
    return response

app.mount("/static", StaticFiles(directory="static"), name="static")
@app.get("/docs", include_in_schema=False)
def custom_docs():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title="文档解析服务",
        swagger_js_url="/static/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger-ui.css",
    )
AVALIABLE_FORMATS=["pdf","docx","doc","wps","odt","pptx","ppt","ofd","md","ceb","jpg","jpeg","png","txt"]

with open("config.yaml",'r',encoding='utf-8') as file:
    cfg = yaml.safe_load(file)

#OUTPUT_PATH="./data/output"
@app.post("/api/preprocessv4")
async def preprocess(file: UploadFile = File(...),img_enable: bool = Form(True),   # 开关 1
    table_enable: bool = Form(True),vlm_enable: bool = Form(True)):

    #加载cfg
    try:
        file_name = file.filename
        save_path = "./data/doc"
        if not os.path.exists(save_path):
            os.makedirs(save_path)
        save_filepath = os.path.join(save_path, file_name)
        with open(save_filepath, "wb") as f:
            f.write(file.file.read())
    except AttributeError:
        return JSONResponse(content={"error": "文件上传出错"})

    input_file=save_filepath
    file_format=Path(input_file).suffix
    file_format=file_format[1:]
    file_name=Path(input_file).stem
    if file_format in AVALIABLE_FORMATS:
        if file_format!="pdf":
            input_file=format(input_file)#返回路径也是绝对路径

    else:
        raise HTTPException(
        status_code=400,
        detail=f"不支持的文件格式：{file_format}"
    )

    #版面识别
    output_path=cfg['output_path']
    output_path=Path(output_path).resolve()
    if vlm_enable:
        cmd=[
            'mineru',
            '-p', str(input_file),
            '-o', str(output_path),
            '--backend', 'vlm-lmdeploy-engine',
            '--cache-max-entry-count','0.8',
            '--device', 'cuda',
            '--source', 'local',
            '--max-batch-size','8'
        ]
    else:
        cmd=[
            'mineru',
            '-p', str(input_file),
            '-o', str(output_path),
            '--backend', 'pipeline',
            '--cache-max-entry-count','0.8',
            '--device', 'cuda',
            '--source', 'local',
            '--max-batch-size','8'
        ]
    """
    cmd = [
    'mineru',
    '-p', str(input_file),
    '-o', str(output_path),
    '--backend', 'vlm-transformers',
    '--device', 'cuda',
    '--source', 'local'
    ]
    """
    subprocess.run(cmd, check=True)
    middle_json_name = f'{file_name}_middle.json'
    target_json = output_path / file_name / 'vlm' / middle_json_name
    # 读取JSON文件
    with open(target_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 处理数据
    if vlm_enable:
        processed_data = merge_blocks(data)
    else:
        processed_data = merge_blocks_pipeline(data)


    output_data = {"output": processed_data["pdf_info"]}
    #output_data.setdefault("metadata", {})
    #output_data['metadata']['name']=file_name
    # 保存到新文件
    final_json_name=f'{file_name}_middle_final.json'
    final_json_path=output_path / file_name / 'vlm' / final_json_name
    with open(final_json_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print("处理完成，已保存到 demo0_middle_final.json")

    


    print("--- Structure Processor Started ---")

    try:
        # 1. 加载
        full_json_data = load_json_data(final_json_path)

        # 2. 递归获取节点 (Task 1: 深入 blocks)
        all_process_nodes = get_all_nodes_recursive(full_json_data)

        # 3. 提取上下文
        full_context = extract_all_text_context_from_nodes(all_process_nodes)

    except Exception as e:
        print(f"Startup Failed: {e}")
        sys.exit(1)

    # 4. LLM 处理 (含干扰项剔除逻辑)
    title_level_map = process_titles_with_llm(all_process_nodes, full_context,cfg['LLM']['title_model']['LLM_API_KEY'],cfg['LLM']['title_model']['LLM_BASE_URL'],cfg['LLM']['title_model']['LLM_MODEL'])

    print("3. Assigning levels to ALL nodes (Task 2)...")

    total_processed = 0

    for node in all_process_nodes:
        total_processed += 1
        node_type = node.get("type")

        assigned_level = 0 # 默认 level 0 (非 title 元素)

        if node_type == "title":
            original_text = extract_text_content(node)
            key = filter_string(original_text)
            if key in title_level_map:
                assigned_level = title_level_map[key]
            else:
                # 如果 LLM 没有返回该标题的层级（可能是漏了，或者是太短的干扰项）
                # 策略：默认为 0，防止其作为错误的父节点干扰后续结构
                # 或者：如果看起来像干扰项，也可以设为 1。这里保守设为 0。
                assigned_level = 0

                # 插入 level 字段
        insert_level_field(node, assigned_level)

    print(f"   Assigned levels to {total_processed} nodes.")

    print("4. Building Structure (Father/Child Nodes) (Task 3)...")
    # 这一步依赖于 level。由于我们将干扰项设为了 Level 1 (或其他 Level)，
    # 只要正文也是 Level 1，这里的逻辑会自动将它们视为“兄弟”而不是“父子”。
    build_structure_relationships(all_process_nodes)

    # 5. 保存
    #save_json_data(full_json_data, )
    #print(f"--- Task Complete. Result saved to: {CONFIG['OUTPUT_JSON_PATH']} ---")

    base_dir = Path(output_path) / file_name / 'vlm'
    base_name = file_name
    md_output_path = os.path.join(base_dir, f"{base_name}_titles_only.md")

    export_structure_to_markdown(all_process_nodes, md_output_path)

    
    
    


    #根据输出的processed_with_levels.json选出图片和表格进行处理，顺便把处理结果加入json文件中
    #processed_with_levels.json的结构：output；pages(包括page size，page index和result)；result通过type确定为image，在image中确定图片本体和caption


    if img_enable:
        count=0
        img_jobs=[]
        for page_index,page in enumerate(full_json_data["output"]):
            for block_index, block in enumerate(page["result"]):
                if block["type"]=="image":
                    for sub_block_index,sub_block in enumerate(block["blocks"]):
                        if sub_block["type"]=="image_body":
                            img_path=sub_block["lines"][0]["spans"][0]["image_path"]
                            img_path=Path(output_path)/f'{file_name}'/'vlm'/'images'/img_path
                            img_jobs.append((page_index,block_index,sub_block_index,img_path))
                            #result=analyze_image_content(img_path,cfg['LLM']['img']['API_KEY'],cfg['LLM']['img']['BASE_URL'],cfg['LLM']['img']['MODEL'])
                            #print(result)
                            #full_json_data["output"][page_index]["result"][block_index]["description"]=result
                            count+=1
        print(f"已收集{count}张图片")
        img_results=await asyncio.gather(*[analyze_image_content_async(str(path),           # 注意转 str
                                          cfg['LLM']['img']['API_KEY'],
                                          cfg['LLM']['img']['BASE_URL'],
                                          cfg['LLM']['img']['MODEL'])
              for _, _, _, path in img_jobs])
        for (p_idx, b_idx, sb_idx, _), desc in zip(img_jobs, img_results):
            full_json_data["output"][p_idx]["result"][b_idx]["description"] = desc
        print(f"已处理{count}张图片")
        '''
        ToprocessList=[]
        for index,entity in enumerate(content_list_data):
            if entity["type"]=="image":
        #获取到的imgPath是"images/6c2408db7ca86b33b1381477e4952284f03f1d5c67986f2d00f4ce80dca594ac.jpg"
        #实际应该是data/output/filename/vlm/images/.......               
                img_path=Path(output_path)/f'{file_name}'/'vlm'/entity["img_path"]
                ToprocessList.append(img_path)
        
        #vlm处理图片
        for index,img in enumerate(ToprocessList):
            result=analyze_image_content(img,cfg['LLM']['img']['API_KEY'],cfg['LLM']['img']['BASE_URL'],cfg['LLM']['img']['MODEL'])

            #保存result
        '''



    if table_enable:
        count_table=0
        table_jobs=[]
        for page_index,page in enumerate(full_json_data["output"]):
            for block_index, block in enumerate(page["result"]):
                if block["type"]=="table":
                    for sub_block_index,sub_block in enumerate(block["blocks"]):
                        if sub_block["type"]=="table_body":
                            try:
                                table_html=sub_block["lines"][0]["spans"][0]["html"]
                            except (IndexError, KeyError, TypeError):
                        # 这里可以打印日志，告诉你到底哪一层断了
                                print(f"[WARN] page={page_index} block={block_index} 取不到 html，已跳过")
                                continue
                            #table_html=sub_block["lines"][0]["spans"][0]["html"]
                            print(f"收集到表格 HTML：{table_html}")  # 打印前30个字符预览
                            table_jobs.append((page_index,block_index,sub_block_index,table_html))
                            #result=table_extract(table_html,cfg['LLM']['table']['API_KEY'],cfg['LLM']['table']['BASE_URL'],cfg['LLM']['table']['MODEL'] )
                            #print(result)
                            #full_json_data["output"][page_index]["result"][block_index]["description"]=result
                            count_table+=1
        print(f"已收集{count_table}个表格")
        table_results=await asyncio.gather(*[table_extract_async(table_html,           # 注意转 str
                                          cfg['LLM']['table']['API_KEY'],
                                          cfg['LLM']['table']['BASE_URL'],
                                          cfg['LLM']['table']['MODEL'])
              for _, _, _, table_html in table_jobs])
        for (p_idx, b_idx, sb_idx, _), desc in zip(table_jobs, table_results):
            full_json_data["output"][p_idx]["result"][b_idx]["description"] = desc
        print(f"已处理{count_table}个表格")
        """
        ToprocessTableList=[]
        for index,entity in enumerate(content_list_data):
            if entity["type"]=="table":
                ToprocessTableList.append(entity["table_body"])
            
        for index,table in enumerate(ToprocessTableList):
            result=table_extract(table,cfg['LLM']['table']['API_KEY'],cfg['LLM']['table']['BASE_URL'],cfg['LLM']['table']['MODEL'] )

            #保存table分析结果
        """
    level_json_name=f'{file_name}_processed_with_levels.json'
    level_json_path=output_path / file_name / 'vlm' / level_json_name
    save_json_data(full_json_data, str(level_json_path))
    print(f"已保存{level_json_name}到{level_json_path}")
    pdf_view=output_path/file_name/'vlm'/f"{file_name}_layout.pdf"
    files_to_send=[
        Path(level_json_path),
        Path(md_output_path),
        Path(pdf_view)
    ]
    zip_buffer=io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in files_to_send:
            zf.write(f, arcname=f.name)   # arcname 决定 zip 里的路径
    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers = {
            "Content-Disposition": f"attachment; filename*=utf-8''{quote(file_name)}_result.zip"}
    )
if __name__=="__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8003)









