import json
import sys
print(sys.path)
import yaml
import os
from images_tables.image.tools import analyze_image_content
from images_tables.table.tools import table_extract
from format.formatTransform import format
from layout.outputjs import merge_blocks
from layout.output_pipeline import merge_blocks_pipeline
from layout.changeJson import *
import pathlib
from pathlib import Path
#layout_path = Path(__file__).parent / "layout"
#sys.path.insert(0, str(layout_path))
#sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import subprocess
from fastapi import FastAPI, UploadFile, File, Form ,Query
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
import uuid
import httpx
from layout.mineru_call import call_mineru_api, mineru_layout
from interface.interface1 import interface1_json
from interface.interface2 import interface2_json
from interface.test_interface import test_interface_json
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
async def preprocess_v4(
    file: UploadFile = File(...),
    vlm_enable: bool = Form(True),
    red_title_enable:bool = Form(True),
    img_select: List[str] = Form([]),
    table_select: List[str] = Form([])
):

    # 1. 调用核心逻辑
    request_id = str(uuid.uuid4())
    status_code = 200
    status_message = "SUCCESS"
    return_json_partitions = []
    title_error_msg = ""
    image_error_msg = ""
    table_error_msg = ""
    red_title_error_msg = ""
    try:
        res = await core_analyze_pipeline(file, vlm_enable, img_select, table_select, request_id)
        
        output_path=res['output_path']
        folder_name=res["folder_name"]
        file_name=res["file_name"]
        timestamp=res["timestamp"]
        image_config=res["image_config"]
        table_config=res["table_config"]
        input_file=res["input_file"]
        image_number=res["image_number"]
        table_number=res["table_number"]
        image_error_msg=res["image_error_msg"]
        table_error_msg=res["table_error_msg"]
        title_error_msg=res["title_error_msg"]
        # 2. 存储逻辑：上传 MinIO
        images_path = Path(res['output_path']) / res["folder_name"] / res["sub_type"] / 'images'
        store_images(images_path, res["file_name"], res["timestamp"], cfg['MinIO']['IP'],cfg['MinIO']['ACCESS_KEY'],cfg['MinIO']['SECRET_KEY'],cfg['MinIO']['BUCKET_NAME'])

        full_json_data=res['full_json_data']

        for block_index,block in enumerate(full_json_data["output"]):
            if block["type"]=="image":
                for sub_block_index,sub_block in enumerate(block["blocks"]):
                    if sub_block["type"]=="image_body":
                        try:
                            img_path=sub_block["lines"][0]["spans"][0]["image_path"]
                            img_path=f"http://{cfg['MinIO']['IP']}/{cfg['MinIO']['BUCKET_NAME']}/{timestamp}_{file_name}/{img_path}"
                            full_json_data["output"][block_index]["blocks"][sub_block_index]["lines"][0]["spans"][0]["image_path"]=img_path
                        except (IndexError, KeyError, TypeError):
                            print(f"[WARN] block={block_index} 取不到图片，已跳过")
                            continue

            elif block["type"]=="table":
                for sub_block_index,sub_block in enumerate(block["blocks"]):
                    if sub_block["type"]=="table_body":
                        try:
                            table_path=sub_block["lines"][0]["spans"][0]["image_path"]
                            table_path=f"http://{cfg['MinIO']['IP']}/{cfg['MinIO']['BUCKET_NAME']}/{timestamp}_{file_name}/{table_path}"
                            full_json_data["output"][block_index]["blocks"][sub_block_index]["lines"][0]["spans"][0]["image_path"]=table_path
                        except (IndexError, KeyError, TypeError):
                            print(f"[WARN] block={block_index} 取不到表格，已跳过")
                            continue
        
        # 保存接口2输出的JSON 
        level_json_name = f'{file_name}_processed_with_levels.json'

        if vlm_enable:
            level_json_path = output_path / folder_name / 'vlm' / level_json_name
        else:
            level_json_path = output_path / folder_name / 'auto' / level_json_name

        save_json_data(full_json_data, str(level_json_path))


        images_output_path=output_path/folder_name/('vlm' if vlm_enable else 'auto')/"page_images"
        images_output_path.mkdir(parents=True, exist_ok=True)

        red_title_error_msg = post_process(input_file,images_output_path,level_json_path,cfg['LLM']['red_title']['API_KEY'],cfg['LLM']['red_title']['BASE_URL'],cfg['LLM']['red_title']['MODEL'],output_path,file_name,folder_name,vlm_enable,red_title_enable,cfg['LLM']['red_title']['connection_timeout'],cfg['LLM']['red_title']['process_timeout']) or ""
        #post_process_2(input_file,images_output_path,level_json_path,cfg['LLM']['red_title']['API_KEY'],cfg['LLM']['red_title']['BASE_URL'],cfg['LLM']['red_title']['MODEL'],output_path,file_name,folder_name,vlm_enable,red_title_enable)
        level_json_path = output_path / folder_name / ('vlm' if vlm_enable else 'auto') / f'{file_name}_level_redtitle.json'
        partitions_json_path=output_path / folder_name/('vlm' if vlm_enable else 'auto')/f"{file_name}_partitions.json"
        with open(partitions_json_path,'r',encoding='utf-8') as f:
            return_json_partitions=json.load(f)
    
    except FileNotFoundError as e:
        status_code = 404
        status_message = f"FILE_NOT_FOUND: {str(e)}"
    except PermissionError as e:
        status_code = 403
        status_message = f"PERMISSION_DENIED: {str(e)}"
    except ValueError as e:
        status_code = 400
        status_message = f"BAD_REQUEST: {str(e)}"
    except Exception as e:
        status_code = 500
        status_message = f"INTERNAL_ERROR: {str(e)}"
    if status_code == 200:
        extra_errors = []
        if image_error_msg:
            extra_errors.append(f"图片提取异常: {image_error_msg}")
            status_code = 500  # 部分成功
        if table_error_msg:
            extra_errors.append(f"表格提取异常: {table_error_msg}")
            status_code = 500  # 部分成功
        if red_title_error_msg: 
            extra_errors.append(f"红头处理异常: {red_title_error_msg}")
            status_code = 500  # 部分成功
        if title_error_msg: 
            extra_errors.append(f"标题层级分析异常: {title_error_msg}")
            status_code = 500  # 部分成功
        if extra_errors:
            status_message = "核心流程成功，大模型调用出错: " + " | ".join(extra_errors)
    return_json={
        "status_code": status_code,
        "status_message": status_message,
        "partitions": return_json_partitions if status_code == 200 else []
    }
    return_json_level={
        "status_code": status_code,
        "status_message": status_message,
        "full_json_data": full_json_data if status_code == 200 else {}
    }
    save_json_data(return_json_level, level_json_path)
    if status_code == 200:
        return_json_path=output_path/folder_name/('vlm' if vlm_enable else 'auto')/f"{file_name}_return.json"
        with open(return_json_path,'w',encoding='utf-8') as f:
            json.dump(return_json,f,ensure_ascii=False,indent=2)
        
        if vlm_enable:
            pdf_view = output_path / folder_name / 'vlm' / f"{file_name}_layout.pdf"
            md_output_path = output_path / folder_name / 'vlm' / f"{file_name}_titles_only.md"
        else:
            pdf_view = output_path / folder_name / 'auto' / f"{file_name}_layout.pdf"
            md_output_path = output_path / folder_name / 'auto' / f"{file_name}_titles_only.md"

        if vlm_enable and 'html' in table_config:
            excel_output_dir = output_path / folder_name / 'vlm' / 'tables_excel'
        elif (not vlm_enable) and 'html' in table_config:
            excel_output_dir = output_path / folder_name / 'auto' / 'tables_excel'

        if 'html' in table_config:
            files_to_send = [return_json_path, md_output_path, pdf_view, excel_output_dir,level_json_path]
        else:
            files_to_send = [return_json_path, md_output_path, pdf_view,level_json_path]

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for f in files_to_send:
                if f.is_dir():
                    for root, _, files in os.walk(f):
                        for file in files:
                            file_path = Path(root) / file
                            arcname = file_path.relative_to(output_path / folder_name / ('vlm' if vlm_enable else 'auto'))
                            zf.write(file_path, arcname=arcname)
                else:
                    zf.write(f, arcname=f.name)
        zip_buffer.seek(0)

        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename*=utf-8''{quote(folder_name)}_result.zip"}
        )
    else:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=status_code,
            content=return_json
        )

@app.post("/api/v1/xidian/preprocess_required")
async def return_json_only(
    file: UploadFile = File(...),
    vlm_enable: bool = Query(True),
    red_title_enable: bool = Query(True),
    img_class: bool = Query(True),
    img_desc: bool = Query(True),
    img_html: bool = Query(True),
    table_kv: bool = Query(True),
    table_desc: bool = Query(True),
    table_html: bool = Query(True)
):
    #将上传文件保存到本地
    try:
        file_name = file.filename
        save_path = "../data/doc"
        if not os.path.exists(save_path):
            os.makedirs(save_path)
        save_filepath = os.path.join(save_path, file_name)
        with open(save_filepath, "wb") as f:
            f.write(file.file.read())
    except AttributeError:
        return JSONResponse(content={"error": "文件上传出错"})
    # 1. 调用核心逻辑
    print(f"接口1调用参数: vlm_enable={vlm_enable}, red_title_enable={red_title_enable}, img_class={img_class}, img_desc={img_desc}, img_html={img_html}, table_kv={table_kv}, table_desc={table_desc}, table_html={table_html}")
    request_id = str(uuid.uuid4())
    print(f"接口1调用 request_id: {request_id}")
    print("正在调用接口1核心逻辑...")
    result = await interface1_json(save_filepath, vlm_enable, red_title_enable, img_class, img_desc, img_html, table_kv, table_desc, table_html, cfg, request_id)
    print("接口1核心逻辑调用完成")
    return result


@app.post("/api/v1/xidian/preprocess_required_test")
async def return_json_only(
    file: UploadFile = File(...),
    vlm_enable: bool = Query(True),
    red_title_enable: bool = Query(True),
    img_class: bool = Query(True),
    img_desc: bool = Query(True),
    img_html: bool = Query(True),
    table_kv: bool = Query(True),
    table_desc: bool = Query(True),
    table_html: bool = Query(True)
):
    # 1. 调用核心逻辑
    #start_time=time.perf_counter()
    try:
        file_name = file.filename
        save_path = "../data/doc"
        if not os.path.exists(save_path):
            os.makedirs(save_path)
        save_filepath = os.path.join(save_path, file_name)
        with open(save_filepath, "wb") as f:
            f.write(file.file.read())
    except AttributeError:
        return JSONResponse(content={"error": "文件上传出错"})
    request_id = str(uuid.uuid4())
    result =await test_interface_json(save_filepath, vlm_enable, red_title_enable, img_class, img_desc, img_html, table_kv, table_desc, table_html, cfg, request_id)
    return result



@app.post("/api/v1/xidian/preprocess_custom")
async def return_json_with_custom_format(
    file: UploadFile = File(...),
    vlm_enable: bool = Query(True),
    red_title_enable: bool = Query(True),
    img_class: bool = Query(True),
    img_desc: bool = Query(True),
    img_html: bool = Query(True),
    table_kv: bool = Query(True),
    table_desc: bool = Query(True),
    table_html: bool = Query(True)
):

    # 1. 调用核心逻辑
    request_id = str(uuid.uuid4())
    try:
        file_name = file.filename
        save_path = "../data/doc"
        if not os.path.exists(save_path):
            os.makedirs(save_path)
        save_filepath = os.path.join(save_path, file_name)
        with open(save_filepath, "wb") as f:
            f.write(file.file.read())
    except AttributeError:
        return JSONResponse(content={"error": "文件上传出错"})
    result =await interface2_json(save_filepath, vlm_enable, red_title_enable, img_class, img_desc, img_html, table_kv, table_desc, table_html, cfg, request_id)
    return result 

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("run:app", host="0.0.0.0", port=8003,workers=cfg['workers'])