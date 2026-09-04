import json
import sys
print(sys.path)
import urllib
import yaml
import os
from images_tables.image.tools import analyze_image_content_async
from images_tables.table.tools import table_extract_async
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
from utils.json_to_md import json_to_markdown,custom_json_to_markdown
import os
from minio import Minio
from minio.error import S3Error
from fastapi.responses import StreamingResponse
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

# ================================================================
# MinIO 客户端（用于图片代理）
# ================================================================
minio_client = Minio(
    endpoint=os.getenv("MINIO_ENDPOINT", "60.204.211.83:10000"),
    access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
    secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin123"),
    secure=False,  # MinIO 走 HTTP（10000 端口）
)

_IMG_MIME_MAP = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg",
    "png": "image/png",  "gif":  "image/gif",
    "webp": "image/webp", "bmp": "image/bmp",
    "svg": "image/svg+xml", "tiff": "image/tiff", "tif": "image/tiff",
    "ico": "image/x-icon",
}

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

"""
# ================================================================
# MinIO 图片代理接口
# ================================================================
@app.get(
    "/api/v1/image-proxy/{bucket}/{object_path:path}",
    summary="MinIO 图片代理",
    description="代理拉取 MinIO 鉴权图片，避免暴露密钥给前端"
)
async def proxy_minio_image(bucket: str, object_path: str):
    
    URL 映射示例：
        原始 MinIO:  http://60.204.211.83:10000/preprocess/xxx/abc.jpg
        代理路径:    /api/v1/image-proxy/preprocess/xxx/abc.jpg
    
    # 路径安全检查
    if ".." in object_path or ".." in bucket:
        raise HTTPException(400, "非法路径")

    # 从 MinIO 拉取对象
    try:
        resp = minio_client.get_object(bucket, object_path)
    except S3Error as e:
        raise HTTPException(404, f"图片不存在或无权访问: {e}")
    except Exception as e:
        print(f"[ERROR] MinIO 访问失败: {e}")
        raise HTTPException(500, f"MinIO 访问失败: {e}")

    # 根据扩展名推断 Content-Type
    ext = object_path.rsplit(".", 1)[-1].lower() if "." in object_path else ""
    mime = _IMG_MIME_MAP.get(ext, "application/octet-stream")

    # 流式返回 + 主动释放连接
    def stream():
        try:
            for chunk in resp.stream(32 * 1024):
                yield chunk
        finally:
            resp.close()
            resp.release_conn()

    return StreamingResponse(
        stream(),
        media_type=mime,
        headers={
            "Cache-Control": "public, max-age=3600",  # 浏览器缓存 1 小时
        },
    )
"""
MINIO_WEB_BASE = "http://10.208.127.189:29101"
@app.get("/api/v1/image-proxy/{bucket}/{object_path:path}")
async def proxy_minio_image(bucket: str, object_path: str):
    if ".." in object_path or ".." in bucket:
        raise HTTPException(400, "非法路径")

    url = f"{MINIO_WEB_BASE}/{bucket}/{object_path}"

    async with httpx.AsyncClient(follow_redirects=True) as client:
        resp = await client.get(url, timeout=30)

    if resp.status_code != 200:
        raise HTTPException(resp.status_code, "图片获取失败")

    ext = object_path.rsplit(".", 1)[-1].lower() if "." in object_path else ""
    mime = _IMG_MIME_MAP.get(ext, "application/octet-stream")

    return StreamingResponse(
        iter([resp.content]),
        media_type=mime,
        headers={"Cache-Control": "public, max-age=3600"},
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
    table_html: bool = Query(True, description="是否生成表格HTML结构"),
    phase_return: bool = Query(False, description="是否分阶段返回结果")
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
    
    if not phase_return:
        result, folder_name= await interface1_json(save_filepath, vlm_enable, red_title_enable, img_class, img_desc, img_html, table_kv, table_desc, table_html, cfg, request_id)
        print("接口1核心逻辑调用完成")
        return result
    
    return StreamingResponse(
        interface1_stream(save_filepath, vlm_enable, red_title_enable, img_class, img_desc, img_html, table_kv, table_desc, table_html, cfg, request_id),
        media_type="text/event-stream"
    )
    
async def interface1_stream(save_filepath, vlm_enable, red_title_enable, img_class, img_desc, img_html, table_kv, table_desc, table_html, cfg, request_id):
    """
    异步生成器，用于分阶段返回interface1的处理结果。
    """
    queue = asyncio.Queue()

    async def callback(stage, data):
        await queue.put({
            "stage": stage,
            "data": data
        })

    task = asyncio.create_task(
        interface1_json(
            save_filepath,
            vlm_enable,
            red_title_enable,
            img_class,
            img_desc,
            img_html,
            table_kv,
            table_desc,
            table_html,
            cfg,
            request_id,
            progress_callback=callback
        )
    )

    while True:

        item = await queue.get()

        yield (
            f"event: {item['stage']}\n"
            f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
        )
        
        if item['stage'] == "final":
            break

    await task


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
            #response_model=BaseResponse,
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
    result,folder_name=await interface2_json(save_filepath, vlm_enable, red_title_enable, img_class, img_desc, img_html, table_kv, table_desc, table_html, cfg, request_id)
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
    description="处理文档，返回预览内容和下载标识"
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

    返回 JSON 响应，包含预览内容和 request_id，前端用 request_id 调用下载接口。
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

        save_filename = f"{safe_name}"

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

            result ,folder_name= await interface1_json(
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

            #output_json_name = f"{request_id}_{Path(safe_name).stem}_standard.json"
            #output_md_name = f"{request_id}_{Path(safe_name).stem}_standard.md"

        elif json_mode == "custom":

            result ,folder_name= await interface2_json(
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

            #output_json_name = f"{request_id}_{Path(safe_name).stem}_custom.json"
            #output_md_name = f"{request_id}_{Path(safe_name).stem}_custom.md"

        else:

            raise HTTPException(
                status_code=400,
                detail="json_mode 仅支持 standard/custom"
            )

        # =====================================================
        # 7. 保存 JSON 文件，并读取已生成的 MD 文件
        # =====================================================

        #output_dir = Path("../data/web_result")
        #output_dir.mkdir(parents=True, exist_ok=True)
        output_dir=cfg['output_path']
        file_name = Path(safe_name).stem
        output_json_path = Path(output_dir) / folder_name / ('vlm' if vlm_enable else 'auto') / f"{file_name}_result.json"
        # MD 文件由 interface1_json / interface2_json 已经生成好了
        # 它的原始路径（不带 request_id 前缀）：
        output_md_path = Path(output_dir) / folder_name / ('vlm' if vlm_enable else 'auto') / f"{file_name}_result.md"

        

        # 保存 JSON
        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        # 读取 MD 内容（用于前端预览）
        if json_mode == "standard":
            md_content = json_to_markdown(result)
        elif json_mode == "custom":
            md_content = custom_json_to_markdown(result)
        #if output_md_path.exists():
        #    with open(output_md_path, "r", encoding="utf-8") as f:
        #        md_content = f.read()
        print(f"MD 内容预览:\n{md_content[:500]}...")  # 打印前 500 字符预览
        with open(output_md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        # =====================================================
        # 8. 构建预览内容并返回
        # =====================================================

        # JSON 预览：读取前 300 行（大文件只展示片段）
        MAX_PREVIEW_LINES = 1000000000
        with open(output_json_path, "r", encoding="utf-8") as f:
            preview_lines = []
            for i, line in enumerate(f):
                if i >= MAX_PREVIEW_LINES:
                    break
                preview_lines.append(line)

        json_preview = "".join(preview_lines)
        json_truncated = len(preview_lines) >= MAX_PREVIEW_LINES
        pdf_filename = f"{file_name}_layout.pdf"
        return JSONResponse({
            "status": "success",
            "request_id": request_id,

            # 文件名（前端显示用）
            "json_filename": f"{file_name}_result.json",
            "md_filename": f"{file_name}_result.md",
            "pdf_filename": pdf_filename,
            # JSON 预览（片段）
            "json_preview": json_preview,
            "json_truncated": json_truncated,

            # MD 预览（全量，md 一般不大）
            "md_content": md_content,
            "folder_name": folder_name,
            "vlm_enable": vlm_enable,
            "save_filename": save_filename
        })

    except HTTPException as e:

        raise e

    except Exception as e:

        print(f"[ERROR] preprocess_web: {str(e)}")

        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "status_code": 500,
                "status_message": str(e),
            }
        )


# ================================================================
# 下载接口
# ================================================================

@app.get(
    "/api/v1/xidian/download/{folder_name}/{vlm_mode}/{filename}",
    summary="下载结果文件",
)
async def download_result(folder_name: str, vlm_mode: str, filename: str):
    # 1. 参数校验
    if vlm_mode not in ("vlm", "auto"):
        raise HTTPException(400, "vlm_mode 仅支持 vlm / auto")

    if ".." in folder_name or ".." in filename:
        raise HTTPException(400, "非法路径")

    # 2. 构建路径并检查存在性
    file_path = Path(cfg['output_path']) / folder_name / vlm_mode / filename

    if not file_path.exists():
        raise HTTPException(404, "文件不存在")

    # 3. 核心修复：对所有文件名进行 URL 编码
    # quote() 会将中文、空格等特殊字符转换为 %XX 格式，确保符合 HTTP Header 的 ASCII 要求
    encoded_filename = urllib.parse.quote(filename)

    suffix = file_path.suffix.lower()

    # 4. 根据后缀决定 Media-Type 和 展示方式 (inline/attachment)
    if suffix == ".pdf":
        media_type = "application/pdf"
        # PDF 通常希望直接在浏览器预览，所以用 inline
        disposition = f"inline; filename*=UTF-8''{encoded_filename}"
        
    elif suffix == ".json":
        media_type = "application/json"
        # JSON 通常直接下载，所以用 attachment
        disposition = f"attachment; filename*=UTF-8''{encoded_filename}"
        
    else: 
        # 处理 .md 以及其他所有未知类型
        # Markdown 浏览器通常无法直接渲染，建议作为附件下载
        media_type = "text/markdown" 
        disposition = f"attachment; filename*=UTF-8''{encoded_filename}"

    # 5. 统一返回响应
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=filename,  # 这里传原始文件名给 FastAPI 内部使用（可选）
        headers={
            "Content-Disposition": disposition
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("run:app", host="0.0.0.0", port=8007,workers=cfg['workers'])