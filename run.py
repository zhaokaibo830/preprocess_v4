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
from pydantic import BaseModel, Field
from typing import List, Dict, Any
MAX_CONCURRENT = 5
semaphore = asyncio.Semaphore(MAX_CONCURRENT)

class BaseResponse(BaseModel):
    status_code: int = Field(..., description="状态码，200表示成功")
    status_message: str = Field(..., description="状态信息")
    partitions: List[Dict[str, Any]] = Field(
        ..., 
        description="解析后的文档结构数据",
        example=[{"type": "text", "content": "示例内容"}]
    )

class TestResponse(BaseResponse):
    time: float = Field(..., description="总耗时（秒）", example=1.23)
    layout_time: float = Field(..., description="布局分析耗时")
    title_time: float = Field(..., description="标题识别耗时")
    image_time: float = Field(..., description="图片处理耗时")
    table_time: float = Field(..., description="表格处理耗时")
    red_title_time: float = Field(..., description="红标题识别耗时")
    image_number: int = Field(..., description="图片数量")
    table_number: int = Field(..., description="表格数量")

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



@app.post("/api/v1/xidian/preprocess_required",
            response_model=BaseResponse,
            summary="标准处理接口",
            description="上传文件进行处理，返回标准格式的处理结果"
)
async def return_json_only(
    file: UploadFile = File(...),
    vlm_enable: bool = Query(True, description="是否启用视觉语言模型（VLM）"),
    red_title_enable: bool = Query(True, description="是否识别红头标题"),
    img_class: bool = Query(True, description="是否进行图片分类"),
    img_desc: bool = Query(True, description="是否生成图片描述"),
    img_html: bool = Query(True, description="是否生成图片HTML结构"),
    table_kv: bool = Query(True, description="是否提取表格键值对"),
    table_desc: bool = Query(True, description="是否生成表格描述"),
    table_html: bool = Query(True, description="是否生成表格HTML结构")
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


@app.post(
    "/api/v1/xidian/preprocess_required_test",
    response_model=TestResponse,
    summary="批量性能测试",
    description="上传待处理文件，返回标准格式处理结果和性能测试信息"
    )
async def return_json_only(
    file: UploadFile = File(...),
    vlm_enable: bool = Query(True, description="是否启用视觉语言模型（VLM）"),
    red_title_enable: bool = Query(True, description="是否识别红头标题"),
    img_class: bool = Query(True, description="是否进行图片分类"),
    img_desc: bool = Query(True, description="是否生成图片描述"),
    img_html: bool = Query(True, description="是否生成图片HTML结构"),
    table_kv: bool = Query(True, description="是否提取表格键值对"),
    table_desc: bool = Query(True, description="是否生成表格描述"),
    table_html: bool = Query(True, description="是否生成表格HTML结构")
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



@app.post("/api/v1/xidian/preprocess_custom",
            response_model=BaseResponse,
            summary="自定义格式处理结果",
            description="上传待处理文件，返回自定义格式的处理结果"
            )
async def return_json_with_custom_format(
    file: UploadFile = File(...),
    vlm_enable: bool = Query(True, description="是否启用视觉语言模型（VLM）"),
    red_title_enable: bool = Query(True, description="是否识别红头标题"),
    img_class: bool = Query(True, description="是否进行图片分类"),
    img_desc: bool = Query(True, description="是否生成图片描述"),
    img_html: bool = Query(True, description="是否生成图片HTML结构"),
    table_kv: bool = Query(True, description="是否提取表格键值对"),
    table_desc: bool = Query(True, description="是否生成表格描述"),
    table_html: bool = Query(True, description="是否生成表格HTML结构")
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

@app.get("/portal", include_in_schema=False)
async def index():
    """
    前端首页
    """
    return FileResponse("static/index.html")


@app.post(
    "/api/v1/xidian/preprocess_web",
    summary="前端页面统一接口",
    description="供前端页面调用，自动下载JSON结果"
)
async def preprocess_web(
    file: UploadFile = File(...),

    # 前端模式
    json_mode: str = Form(...),

    # 通用配置
    vlm_enable: bool = Form(True),
    red_title_enable: bool = Form(True),

    # 多选项
    img_select: List[str] = Form([]),
    table_select: List[str] = Form([])
):
    """
    前端统一接口：

    json_mode:
        standard -> interface1_json
        custom   -> interface2_json
    """

    try:

        # =====================================================
        # 1. 文件检查
        # =====================================================

        if not file.filename:
            raise HTTPException(status_code=400, detail="文件名为空")

        safe_name = Path(file.filename).name

        ext = safe_name.split(".")[-1].lower()

        if ext not in AVALIABLE_FORMATS:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件格式: {ext}"
            )

        # =====================================================
        # 2. 保存上传文件
        # =====================================================

        request_id = str(uuid.uuid4())

        save_dir = Path("../data/doc")
        save_dir.mkdir(parents=True, exist_ok=True)

        save_filename = f"{request_id}_{safe_name}"

        save_path = save_dir / save_filename

        with open(save_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # =====================================================
        # 3. 解析图片配置
        # =====================================================

        img_class = "class" in img_select
        img_desc = "description" in img_select
        img_html = "html" in img_select

        # =====================================================
        # 4. 解析表格配置
        # =====================================================

        table_kv = "key-value" in table_select
        table_desc = "description" in table_select
        table_html = "html" in table_select

        # =====================================================
        # 5. 打印日志
        # =====================================================

        print("=" * 80)
        print(f"[WEB] request_id = {request_id}")
        print(f"[WEB] json_mode = {json_mode}")
        print(f"[WEB] file_name = {safe_name}")

        print(
            f"[WEB] vlm_enable={vlm_enable}, "
            f"red_title_enable={red_title_enable}"
        )

        print(
            f"[WEB] img_class={img_class}, "
            f"img_desc={img_desc}, "
            f"img_html={img_html}"
        )

        print(
            f"[WEB] table_kv={table_kv}, "
            f"table_desc={table_desc}, "
            f"table_html={table_html}"
        )

        print("=" * 80)

        # =====================================================
        # 6. 调用已有接口逻辑
        # =====================================================

        if json_mode == "standard":

            result = await interface1_json(
                str(save_path),
                vlm_enable,
                red_title_enable,
                img_class,
                img_desc,
                img_html,
                table_kv,
                table_desc,
                table_html,
                cfg,
                request_id
            )

            output_json_name = f"{Path(safe_name).stem}_standard.json"

        elif json_mode == "custom":

            result = await interface2_json(
                str(save_path),
                vlm_enable,
                red_title_enable,
                img_class,
                img_desc,
                img_html,
                table_kv,
                table_desc,
                table_html,
                cfg,
                request_id
            )

            output_json_name = f"{Path(safe_name).stem}_custom.json"

        else:

            raise HTTPException(
                status_code=400,
                detail="json_mode 仅支持 standard/custom"
            )

        # =====================================================
        # 7. 保存JSON文件
        # =====================================================

        output_dir = Path("../data/web_result")
        output_dir.mkdir(parents=True, exist_ok=True)

        output_json_path = output_dir / output_json_name

        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(
                result,
                f,
                ensure_ascii=False,
                indent=2
            )

        # =====================================================
        # 8. 返回JSON文件下载
        # =====================================================

        return FileResponse(
            path=str(output_json_path),
            media_type="application/json",
            filename=output_json_name
        )

    except HTTPException as e:

        raise e

    except Exception as e:

        print(f"[ERROR] preprocess_web: {str(e)}")

        return JSONResponse(
            status_code=500,
            content={
                "status_code": 500,
                "status_message": str(e),
                "partitions": []
            }
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("run:app", host="0.0.0.0", port=8003,workers=cfg['workers'])