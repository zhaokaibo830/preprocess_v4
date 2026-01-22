import json
import sys
import yaml
from images_tables.image.tools import analyze_image_content
from images_tables.table.tools import table_extract
from format.formatTransform import format
from layout.outputjs import merge_blocks
from layout.output_pipeline import merge_blocks_pipeline
from layout.changeJson import *
from titles.get_title import *
import pathlib
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
from images_tables.table.tools_async import analyze_table_content_async
import asyncio
#from titles.title_process import *
from titles.title2 import title_process
import zipfile
import io
import time
from fastapi import Request
from urllib.parse import quote
from typing import List
from minioStore.store import store_images
import datetime
from images_tables.table.html2excel import html_to_excel_openpyxl
import shutil
MAX_CONCURRENT = 5
semaphore = asyncio.Semaphore(MAX_CONCURRENT)

app = FastAPI(docs_url=None, redoc_url=None)

@app.middleware("http")
async def add_process_time(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
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

AVALIABLE_FORMATS = ["pdf", "docx", "doc", "wps", "odt", "pptx", "ppt", "ofd", "md", "ceb", "jpg", "jpeg", "png", "txt"]

with open("config.yaml", 'r', encoding='utf-8') as file:
    cfg = yaml.safe_load(file)

@app.post("/api/preprocessv4")
async def preprocess(
    file: UploadFile = File(...),
    vlm_enable: bool = Form(True),
    img_select: List[str] = Form([]),
    table_select: List[str] = Form([]),
):

    print("vlm_enable:", vlm_enable)
    #print(img_select, table_select)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
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

    input_file = save_filepath
    file_format = Path(input_file).suffix[1:]
    file_name = Path(input_file).stem
    if file_format in AVALIABLE_FORMATS:
        if file_format != "pdf":
            input_file = format(input_file)
    else:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式：{file_format}")

    output_path = Path(cfg['output_path']).resolve()
    output_path_temp = Path(cfg['output_path_temp']).resolve()
    #output_path.mkdir(parents=True, exist_ok=True)
    output_path_temp.mkdir(parents=True, exist_ok=True)
    if vlm_enable:
        """
        cmd = [
            'mineru', '-p', str(input_file), '-o', str(output_path_temp),
            '--backend', 'vlm-lmdeploy-engine',
            '--cache-max-entry-count', '0.8',
            '--device', 'cuda', '--source', 'local',
            '--max-batch-size', '8'
        ]
        """
        cmd = [
            'curl',
            '-X', 'POST',
            'http://127.0.0.1:8000/file_parse',
            '-F', f'files=@{input_file}',
            '-F', f'output_dir={output_path_temp}',
            '-F', 'backend=vlm-lmdeploy-engine',
            '-F', 'parse_method=auto',
            '-F', 'table_enable=true',
            '-F', 'formula_enable=true',
            '-F', 'return_content_list=true',
            '-F', 'return_images=true',
            '-F', 'return_md=true',
            '-F', 'return_layout_pdf=true',
            '-F', 'return_middle_json=true',
            '-F', 'return_model_output=true',
            
        ]
    else:
        """
        cmd = [
            'mineru', '-p', str(input_file), '-o', str(output_path),
            '--backend', 'pipeline',
            '--cache-max-entry-count', '0.8',
            '--device', 'cuda', '--source', 'local',
            '--max-batch-size', '8'
        ]
        """
        cmd=[
            'curl',
            '-X', 'POST',
            'http://127.0.0.1:8000/file_parse',
            '-F', f'files=@{input_file}',
            '-F', f'output_dir={output_path_temp}',
            '-F', 'backend=pipeline',
            '-F', 'parse_method=auto',
            '-F', 'table_enable=true',
            '-F', 'formula_enable=true',
            '-F', 'return_content_list=true',
            '-F', 'return_images=true',
            '-F', 'return_md=true',
            '-F', 'return_layout_pdf=true',
            '-F', 'return_middle_json=true',
            '-F', 'return_model_output=true',

        ]
    subprocess.run(cmd, check=True ,stdout=subprocess.DEVNULL)

    if vlm_enable:
        # Step 1: 找 temp 下唯一 uuid 目录
        uuid_dirs = [d for d in output_path_temp.iterdir() if d.is_dir()]
        if len(uuid_dirs) != 1:
            raise RuntimeError(
                f"output_path_temp 下目录数量异常: {[d.name for d in uuid_dirs]}"
            )

        uuid_dir = uuid_dirs[0]

        # Step 2: 找 uuid 目录下唯一结果目录（如 29）
        result_dirs = [d for d in uuid_dir.iterdir() if d.is_dir()]
        if len(result_dirs) != 1:
            raise RuntimeError(
                f"{uuid_dir} 下结果目录数量异常: {[d.name for d in result_dirs]}"
            )

        result_dir = result_dirs[0]

        # Step 3: 移动结果目录到最终 output_path
        target_dir = output_path / result_dir.name
        if target_dir.exists():
            shutil.rmtree(target_dir)

        shutil.move(str(result_dir), str(target_dir))

        # Step 4: 清空 temp 目录
        shutil.rmtree(output_path_temp)
        output_path_temp.mkdir(parents=True, exist_ok=True)

        print(f"mineru 输出已移动至: {target_dir}")


    middle_json_name = f'{file_name}_middle.json'
    if vlm_enable:
        target_json = output_path / file_name / 'vlm' / middle_json_name
    else:
        target_json = output_path / file_name / 'auto' / middle_json_name
    with open(target_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    if vlm_enable:
        processed_data = merge_blocks(data)
    else:
        processed_data = merge_blocks_pipeline(data)

    output_data = {"output": processed_data["pdf_info"]}
    output_data = modify_json_structure_complete(output_data)

    final_json_name = f'{file_name}_middle_final.json'
    if vlm_enable:
        final_json_path = output_path / file_name / 'vlm' / final_json_name
    else:
        final_json_path = output_path / file_name / 'auto' / final_json_name
    with open(final_json_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    print(f"处理完成，已保存到 {final_json_path}")

    #final_json_path是版面识别的最终结果

    final_json_path = Path(final_json_path).absolute()

    full_json_data = title_process(
        final_json_path,
        cfg['LLM']['title_model']['LLM_BASE_URL'],
        cfg['LLM']['title_model']['LLM_API_KEY'],
        cfg['LLM']['title_model']['LLM_MODEL'],
        output_path,
        file_name,
        vlm_enable=vlm_enable
    )

    # 图片配置
    image_config, table_config = [], []

    if "class" in img_select:
        image_config.append("cls")
    if "description" in img_select:
        image_config.append("desc")
    if "html" in img_select:
        image_config.append("html")
    if "key-value" in table_select:
        table_config.append("kv")
    if "description" in table_select:
        table_config.append("desc")
    if "html" in table_select:
        table_config.append("html")

    # 转换为逗号分隔的字符串
    image_config = ','.join(image_config)
    table_config = ','.join(table_config)

    print("图片配置：", image_config)
    print("表格配置：", table_config)

    # 处理图片
    
    if  image_config:
        image_count = 0
        img_jobs = []
        print(f"图片处理选项为{image_config}，开始处理图片...")
        for block_index,block in enumerate(full_json_data["output"]):
            if block["type"]=="image":
                for sub_block_index,sub_block in enumerate(block["blocks"]):
                    if sub_block["type"]=="image_body":
                        img_path=sub_block["lines"][0]["spans"][0]["image_path"]
                        if vlm_enable:
                            img_path=Path(output_path)/file_name/'vlm'/'images'/img_path
                        else:
                            img_path=Path(output_path)/file_name/'auto'/'images'/img_path
                        
                        img_jobs.append((block_index,sub_block_index,img_path))
                        image_count+=1 
        print(f"已收集{image_count}张图片")
        img_results = await asyncio.gather(
            *[analyze_image_content_async(str(path), image_config,
                                        cfg['LLM']['img']['API_KEY'],
                                        cfg['LLM']['img']['BASE_URL'],
                                        cfg['LLM']['img']['MODEL'],semaphore)
            for _, _, path in img_jobs]
        )
        for ( b_idx, sb_idx, _), desc in zip(img_jobs, img_results):
            full_json_data["output"][b_idx]["llm_process"] = desc
        print(f"已处理{image_count}张图片")
    else:
        print("图片处理选项为空，跳过图片处理步骤。")
    
    if table_config:
        print(f"表格处理选项为{table_config}，开始处理表格...")
        table_count = 0
        table_jobs = []
        for block_index,block in enumerate(full_json_data["output"]):
            if block["type"]=="table":
                for sub_block_index,sub_block in enumerate(block["blocks"]):
                    if sub_block["type"]=="table_body":
                        try:

                            table_path=sub_block["lines"][0]["spans"][0]["image_path"]
                            
                            if vlm_enable:
                                table_path=Path(output_path)/file_name/'vlm'/'images'/table_path
                            else:
                                table_path=Path(output_path)/file_name/'auto'/'images'/table_path
                            table_html=sub_block["lines"][0]["spans"][0]["html"]
                        except (IndexError, KeyError, TypeError):
                            print(f"[WARN] block={block_index} 取不到表格，已跳过")
                            continue
                        #print(f"收集到表格图片：{table_html[:30]}...")
                        table_jobs.append((block_index,sub_block_index,table_path,table_html))
                        table_count+=1
        print(f"已收集{table_count}个表格")

        table_results = await asyncio.gather(
            *[analyze_table_content_async(
                str(path),
                html,
                table_config,
                cfg['LLM']['img']['API_KEY'],
                cfg['LLM']['img']['BASE_URL'],
                cfg['LLM']['img']['MODEL'],
                semaphore  # 传入信号量
            ) for _, _, path, html in table_jobs]
        )
        
        # 将结果写回原数据结构
        for (b_idx, sb_idx, _, _), result in zip(table_jobs, table_results):
            full_json_data["output"][b_idx]["llm_process"] = result
            #print(f"Block {b_idx}, Sub-block {sb_idx}: {result}")
        
        if 'html' in table_config:#如果有html参数，保存excel文件
            excel_output_dir=Path(output_path)/file_name/('vlm' if vlm_enable else 'auto')/'tables_excel'
            excel_output_dir.mkdir(parents=True,exist_ok=True)
            for _,_,table_path,table_html in table_jobs:
                table_name=Path(table_path).stem+'.xlsx'
                excel_output_path=excel_output_dir/table_name
                html_to_excel_openpyxl(table_html,str(excel_output_path))

        print(f"已处理{table_count}张表格")
    else:
        print("表格处理选项为空，跳过表格处理步骤。")


    eq_path=output_path / file_name / ('vlm' if vlm_enable else 'auto')/'equation_images'
    eq_path.mkdir(parents=True,exist_ok=True)
    for block_index, block in enumerate(full_json_data["output"]):
        if block["type"] == "interline_equation":
            img_path = block["lines"][0]["spans"][0]["image_path"]
            img_path=Path(output_path)/file_name/('vlm' if vlm_enable else 'auto')/'images'/img_path
            if img_path.exists():
                shutil.move(str(img_path), str(output_path / file_name / 'vlm' if vlm_enable else 'auto'/'equation_images' / img_path.name))
        

    if vlm_enable:
        images_path=Path(output_path)/file_name/'vlm'/'images'
    else:
        images_path=Path(output_path)/file_name/'auto'/'images'
        
    store_images(images_path,file_name,timestamp,cfg['MinIO']['IP'],cfg['MinIO']['ACCESS_KEY'],cfg['MinIO']['SECRET_KEY'],cfg['MinIO']['BUCKET_NAME'])
    # 准备返回的 zip 包


    #修改图片和表格的路径为 MinIO 路径
    for block_index,block in enumerate(full_json_data["output"]):
        if block["type"]=="image":
            for sub_block_index,sub_block in enumerate(block["blocks"]):
                if sub_block["type"]=="image_body":
                    try:
                        img_path=sub_block["lines"][0]["spans"][0]["image_path"]
                        img_path=f"{cfg['MinIO']['IP']}/{cfg['MinIO']['BUCKET_NAME']}/{timestamp}_{file_name}/{img_path}"
                        full_json_data["output"][block_index]["blocks"][sub_block_index]["lines"][0]["spans"][0]["image_path"]=img_path
                    except (IndexError, KeyError, TypeError):
                        print(f"[WARN] block={block_index} 取不到图片，已跳过")
                        continue

        elif block["type"]=="table":
            for sub_block_index,sub_block in enumerate(block["blocks"]):
                if sub_block["type"]=="table_body":
                    try:
                        table_path=sub_block["lines"][0]["spans"][0]["image_path"]
                        table_path=f"{cfg['MinIO']['IP']}/{cfg['MinIO']['BUCKET_NAME']}/{timestamp}_{file_name}/{table_path}"
                        full_json_data["output"][block_index]["blocks"][sub_block_index]["lines"][0]["spans"][0]["image_path"]=table_path
                    except (IndexError, KeyError, TypeError):
                        print(f"[WARN] block={block_index} 取不到表格，已跳过")
                        continue

    # 保存最终 JSON
    level_json_name = f'{file_name}_processed_with_levels.json'
    if vlm_enable:
        level_json_path = output_path / file_name / 'vlm' / level_json_name
    else:
        level_json_path = output_path / file_name / 'auto' / level_json_name
    #level_json_path = output_path / file_name / 'vlm' / level_json_name
    save_json_data(full_json_data, str(level_json_path))
    print(f"已保存{level_json_name}到{level_json_path}")

    # 准备返回的 zip 包
    if vlm_enable:
        pdf_view = output_path / file_name / 'vlm' / f"{file_name}_layout.pdf"
        md_output_path = output_path / file_name / 'vlm' / f"{file_name}_titles_only.md"
    else:
        pdf_view = output_path / file_name / 'auto' / f"{file_name}_layout.pdf"
        md_output_path = output_path / file_name / 'auto' / f"{file_name}_titles_only.md"

    if vlm_enable and 'html' in table_config:
        excel_output_dir = output_path / file_name / 'vlm' / 'tables_excel'
    elif (not vlm_enable) and 'html' in table_config:
        excel_output_dir = output_path / file_name / 'auto' / 'tables_excel'

    if 'html' in table_config:
        files_to_send = [level_json_path, md_output_path, pdf_view, excel_output_dir]
    else:
        files_to_send = [level_json_path, md_output_path, pdf_view]

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in files_to_send:
            if f.is_dir():
                for root, _, files in os.walk(f):
                    for file in files:
                        file_path = Path(root) / file
                        arcname = file_path.relative_to(output_path / file_name / ('vlm' if vlm_enable else 'auto'))
                        zf.write(file_path, arcname=arcname)
            else:
                zf.write(f, arcname=f.name)
    zip_buffer.seek(0)
    


    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename*=utf-8''{quote(file_name)}_result.zip"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)