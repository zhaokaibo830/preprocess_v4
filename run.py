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
layout_path = Path(__file__).parent / "layout"
sys.path.insert(0, str(layout_path))
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
#from titles.title_process import *
from titles.title3 import title_process
import zipfile
import io
import time
from fastapi import Request
from urllib.parse import quote
from typing import List
from minioStore.store import store_images,store_files
import datetime
from images_tables.table.html2excel import html_to_excel_openpyxl
import shutil
import uuid
import httpx
from layout.allinone import post_process,post_process_2
MAX_CONCURRENT = 5
semaphore = asyncio.Semaphore(MAX_CONCURRENT)

async def core_analyze_pipeline(
    file: UploadFile, 
    vlm_enable: bool, 
    img_select: List[str], 
    table_select: List[str],
    request_id: str
):
    
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
    folder_name=f"{timestamp}_{file_name}"
    if file_format in AVALIABLE_FORMATS:
        if file_format != "pdf":
            input_file = format(input_file)
    else:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式：{file_format}")

    #mineru调用
    mineru_start_time=time.perf_counter()
    output_path = Path(cfg['output_path']).resolve()
    request_id = str(uuid.uuid4())
    output_path_temp = Path(cfg['output_path_temp']).resolve()
    output_path.mkdir(parents=True, exist_ok=True)
    output_path_temp.mkdir(parents=True, exist_ok=True)
    task_temp_path = Path(cfg['output_path_temp']).resolve() / request_id
    task_temp_path.mkdir(parents=True, exist_ok=True)
    await call_mineru_api(input_file, task_temp_path, 'vlm-lmdeploy-engine' if vlm_enable else 'pipeline')
    mineru_end_time=time.perf_counter()

    #输出路径重整
    uuid_dirs = [d for d in task_temp_path.iterdir() if d.is_dir()]
    if len(uuid_dirs)>0:
        # Step 1: 找 temp 下唯一 uuid 目录
        
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
        target_dir = output_path / folder_name
        if target_dir.exists():
            shutil.rmtree(target_dir)

        shutil.move(str(result_dir), str(target_dir))

        print(f"mineru 输出已移动至: {target_dir}")
    shutil.rmtree(task_temp_path)

    #json格式修改
    middle_json_name = f'{file_name}_middle.json'
    if vlm_enable:
        target_json = output_path / folder_name / 'vlm' / middle_json_name
    else:
        target_json = output_path / folder_name / 'auto' / middle_json_name
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
        final_json_path = output_path / folder_name / 'vlm' / final_json_name
    else:
        final_json_path = output_path / folder_name / 'auto' / final_json_name
    with open(final_json_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    print(f"处理完成，已保存到 {final_json_path}")

    #final_json_path是mineru版面识别的最终结果

    #标题处理
    final_json_path = Path(final_json_path).absolute()
    title_start_time=time.perf_counter()
    full_json_data = title_process(
        final_json_path,
        cfg['LLM']['title_model']['LLM_BASE_URL'],
        cfg['LLM']['title_model']['LLM_API_KEY'],
        cfg['LLM']['title_model']['LLM_MODEL'],
        output_path,
        file_name,
        folder_name,
        vlm_enable=vlm_enable
    )
    title_end_time=time.perf_counter()

    # 图表处理
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

        def build_consistent_error_json(reason):
                err_dict = {}
                if 'cls' in image_config:
                    err_dict["type"] = "error"
                if 'desc' in image_config:
                    err_dict["desc"] = f"处理失败/已跳过: {reason}。本内容由AI生成，内容仅供参考。"
                if 'html' in image_config:
                    err_dict["html"] = f"<table><tr><td>错误信息：{reason}</td></tr></table>"
                return err_dict

        img_time_start=time.perf_counter()
        #img_jobs = []
        print(f"图片处理选项为{image_config}，开始处理图片...")
        image_count = 0
        stop_processing = False  # 熔断标志
        final_error_info = ""
        for block_index,block in enumerate(full_json_data["output"]):

            if block["type"] == "image":
                image_count += 1
                if stop_processing:
                    # 记录“因之前图片出错而导致本图被跳过”的状态
                    block["llm_process"] = build_consistent_error_json(f"由于之前的错误已停止处理: {final_error_info}")
                    continue
                img_path=None
                img_title=""
                for sub_block_index , sub_block in enumerate(block["blocks"]):
                    
                    if sub_block["type"] == "image_body":
                        img_path=sub_block["lines"][0]["spans"][0]["image_path"]
                        if vlm_enable:
                            img_path=Path(output_path)/folder_name/'vlm'/'images'/img_path
                        else:
                            img_path=Path(output_path)/folder_name/'auto'/'images'/img_path
                        
                    elif sub_block["type"] == "image_caption":
                        try:
                            img_title=sub_block["lines"][0]["spans"][0]["content"]
                        except (IndexError, KeyError, TypeError):
                            img_title=""
                try:
                    result=analyze_image_content(img_path,img_title,image_config,
                                            cfg['LLM']['img']['API_KEY'],
                                            cfg['LLM']['img']['BASE_URL'],
                                            cfg['LLM']['img']['MODEL'])
                    block["llm_process"]=result
                except Exception as e:
                    stop_processing = True  # 触发熔断
                    final_error_info = str(e)  # 记录错误信息
                    block["llm_process"] = build_consistent_error_json(final_error_info)
                    print(f"!!! 严重错误：处理第 {image_count} 张图片时发生异常，已启动熔断 !!!")
                    print(f"错误详情: {final_error_info}")
                
        print(f"已处理{image_count}张图片")          
        '''
            if block["type"]=="image":
                current_sub_idx=-1
                current_img_path=None
                current_img_title=""
                for sub_block_index,sub_block in enumerate(block["blocks"]):
                    if sub_block["type"]=="image_body":
                        img_path=sub_block["lines"][0]["spans"][0]["image_path"]
                        if vlm_enable:
                            img_path=Path(output_path)/folder_name/'vlm'/'images'/img_path
                        else:
                            img_path=Path(output_path)/folder_name/'auto'/'images'/img_path
                        
                        current_sub_idx=sub_block_index
                        current_img_path=img_path
                    elif sub_block["type"]=="image_caption":
                        try:
                            current_img_title=sub_block["lines"][0]["spans"][0]["content"]
                        except (IndexError, KeyError, TypeError):
                            current_img_title=""
                if current_img_path:
                    img_jobs.append([
                        block_index,
                        current_sub_idx,
                        current_img_path,
                        current_img_title
                    ])   
                
        print(f"已收集{len(img_jobs)}张图片")

        img_results = await asyncio.gather(
            *[analyze_image_content_async(str(path),title, image_config,
                                        cfg['LLM']['img']['API_KEY'],
                                        cfg['LLM']['img']['BASE_URL'],
                                        cfg['LLM']['img']['MODEL'],semaphore)
            for _, _, path,title in img_jobs]
        )
        for ( b_idx, sb_idx, _,_), desc in zip(img_jobs, img_results):
            full_json_data["output"][b_idx]["llm_process"] = desc
        print(f"已处理{len(img_jobs)}张图片")
        '''
        img_end_time=time.perf_counter()
    else:
        print("图片处理选项为空，跳过图片处理步骤。")
        img_start_time=0
        img_end_time=0
    

    #表格处理
    
    if table_config:

        def build_table_error_json(reason):
                err_dict = {"type": "table"} # 表格固定有 type
                if 'kv' in table_config:
                    # 正常是 list[dict]，报错也给个 list[dict]
                    err_dict["key_value"] = [{"error": "数据提取失败", "details": reason}]
                if 'desc' in table_config:
                    err_dict["description"] = f"表格分析失败: {reason}"
                if 'html' in table_config:
                    err_dict["table_html"] = block.get("table_html", "") # 失败则保留原html或报错信息
                return err_dict

        table_start_time=time.perf_counter()
        print(f"表格处理选项为{table_config}，开始处理表格...")
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
                table_html=None
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
                            table_html=None
                            continue
                    elif sub_block["type"] == "table_caption":
                        try:
                            table_title=sub_block["lines"][0]["spans"][0]["content"]
                        except (IndexError, KeyError, TypeError):
                            table_title=""
                try:
                    result=table_extract(table_html,table_title,table_config,
                                        cfg['LLM']['img']['API_KEY'],
                                        cfg['LLM']['img']['BASE_URL'],
                                        cfg['LLM']['img']['MODEL'])
                    block["llm_process"]=result
                except Exception as e:
                    # 3. 捕获 raise 抛出的错误，启动熔断
                    stop_processing_table = True
                    final_table_error = str(e)
                    block["llm_process"] = build_table_error_json(f"处理中断: {final_table_error}")
                    print(f"表格处理熔断：第 {processed_count} 个表格出错: {final_table_error}")
                
        print(f"已处理{table_count}张表格")
        '''
        table_jobs = []
        for block_index,block in enumerate(full_json_data["output"]):
            if block["type"]=="table":
                current_table_html=None
                current_table_title=""
                current_sub_idx=-1
                current_table_path=None
                for sub_block_index,sub_block in enumerate(block["blocks"]):
                    if sub_block["type"]=="table_body":
                        try:
                            table_path=sub_block["lines"][0]["spans"][0]["image_path"]
                            if vlm_enable:
                                table_path=Path(output_path)/folder_name/'vlm'/'images'/table_path
                            else:
                                table_path=Path(output_path)/folder_name/'auto'/'images'/table_path
                            current_table_path=table_path
                            current_table_html=sub_block["lines"][0]["spans"][0]["html"]
                            current_sub_idx=sub_block_index
                        except (IndexError, KeyError, TypeError):
                            print(f"[WARN] block={block_index} 取不到表格，已跳过")
                            continue
                    elif sub_block["type"]=="table_caption":
                        try:
                            current_table_title=sub_block["lines"][0]["spans"][0]["content"]
                        except (IndexError, KeyError, TypeError):
                            current_table_title=""
                if current_table_html:
                    table_jobs.append(
                        [
                            block_index,
                            current_sub_idx,
                            current_table_html,
                            current_table_title,
                            table_path
                        ]
                    )

        print(f"已收集{len(table_jobs)}个表格")

        table_results = await asyncio.gather(
            *[analyze_table_content_async(
                html,
                title,
                table_config,
                cfg['LLM']['img']['API_KEY'],
                cfg['LLM']['img']['BASE_URL'],
                cfg['LLM']['img']['MODEL'],
                semaphore  # 传入信号量
            ) for _, _, html,title,_ in table_jobs]
        )
        
        # 将结果写回原数据结构
        for (b_idx, sb_idx, _, _,_), result in zip(table_jobs, table_results):
            full_json_data["output"][b_idx]["llm_process"] = result
            #print(f"Block {b_idx}, Sub-block {sb_idx}: {result}")
        '''
        if 'html' in table_config:#如果有html参数，保存excel文件
            excel_output_dir=Path(output_path)/folder_name/('vlm' if vlm_enable else 'auto')/'tables_excel'
            excel_output_dir.mkdir(parents=True,exist_ok=True)
            for table_html, table_path in table_jobs:
                table_name=Path(table_path).stem+'.xlsx'
                excel_output_path=excel_output_dir/table_name
                html_to_excel_openpyxl(table_html,str(excel_output_path))

        print(f"已处理{table_count}张表格")
        table_time_end=time.perf_counter()
    else:
        print("表格处理选项为空，跳过表格处理步骤。")
        table_start_time=0
        table_time_end=0

    

    #将公式图片从minio待上传列表中移除
    eq_path=output_path / folder_name / ('vlm' if vlm_enable else 'auto')/'equation_images'
    eq_path.mkdir(parents=True,exist_ok=True)
    for block_index, block in enumerate(full_json_data["output"]):
        if block["type"] == "interline_equation":
            img_path = block["lines"][0]["spans"][0]["image_path"]
            img_path=Path(output_path)/folder_name/('vlm' if vlm_enable else 'auto')/'images'/img_path
            if img_path.exists():
                shutil.move(str(img_path), str(output_path / folder_name / 'vlm' if vlm_enable else 'auto'/'equation_images' / img_path.name))

    return  {
        "output_path":output_path,
        "full_json_data": full_json_data, 
        "folder_name": folder_name, 
        "file_name": file_name, 
        "timestamp": timestamp,
        "sub_type": 'vlm' if vlm_enable else 'auto',
        "image_config":image_config,
        "table_config":table_config,
        "input_file":input_file,
        "table_number" : table_count,
        "image_number" : image_count,
        "layout_time" : mineru_end_time-mineru_start_time,
        "title_time" : title_end_time-title_start_time,
        "image_time" : img_end_time-img_time_start,
        "table_time" : table_time_end-table_start_time
    }  

async def call_mineru_api(input_file_path, output_dir, backend):
    async with httpx.AsyncClient(timeout=None) as client:
        with open(input_file_path, "rb") as f:
            files = {'files': f}
            data = {
                'output_dir': str(output_dir),
                'backend': backend,
                'parse_method': 'auto',
                'table_enable': 'true',
                'formula_enable': 'true',
                'return_content_list': 'true',
                'return_images': 'true',
                'return_md': 'true',
                'return_layout_pdf': 'true',
                'return_middle_json': 'true',
                'return_model_output': 'true'
            }
            # 异步发送请求，此时 8003 服务可以去干别的事
            response = await client.post("http://127.0.0.1:8000/file_parse", files=files, data=data)
            return response.json()

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
    try:
        res = await core_analyze_pipeline(file, vlm_enable, img_select, table_select, request_id)
        
        output_path=res['output_path']
        folder_name=res["folder_name"]
        file_name=res["file_name"]
        timestamp=res["timestamp"]
        image_config=res["image_config"]
        table_config=res["table_config"]
        input_file=res["input_file"]
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

        post_process(input_file,images_output_path,level_json_path,cfg['LLM']['red_title']['API_KEY'],cfg['LLM']['red_title']['BASE_URL'],cfg['LLM']['red_title']['MODEL'],output_path,file_name,folder_name,vlm_enable,red_title_enable)
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

    return_json={
        "status_code": status_code,
        "status_message": status_message,
        "partitions": return_json_partitions if status_code == 200 else []
    }
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
    # 1. 调用核心逻辑
    request_id = str(uuid.uuid4())
    status_code = 200
    status_message = "SUCCESS"
    return_json_partitions = []
    try:
        img_select, table_select = [], []

        if img_class:
            img_select.append("class")
        if img_desc:
            img_select.append("description")
        if img_html:
            img_select.append("html")
        if table_kv:
            table_select.append("key-value")
        if table_desc:
            table_select.append("description")
        if table_html:
            table_select.append("html")

        
        res = await core_analyze_pipeline(file, vlm_enable, img_select, table_select, request_id)
        
        output_path=res['output_path']
        folder_name=res["folder_name"]
        file_name=res["file_name"]
        timestamp=res["timestamp"]
        image_config=res["image_config"]
        table_config=res["table_config"]
        input_file=res["input_file"]

        # 2. 存储逻辑：将图表文件上传 MinIO
        images_path = Path(res['output_path']) / res["folder_name"] / res["sub_type"] / 'images'
        store_images(images_path, res["file_name"], res["timestamp"], cfg['MinIO']['IP'],cfg['MinIO']['ACCESS_KEY'],cfg['MinIO']['SECRET_KEY'],cfg['MinIO']['BUCKET_NAME'])
        # 修改图表的存储路径
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
        
        # 保存最终 JSON
        level_json_name = f'{file_name}_processed_with_levels.json'
        if vlm_enable:
            level_json_path = output_path / folder_name / 'vlm' / level_json_name
        else:
            level_json_path = output_path / folder_name / 'auto' / level_json_name
        save_json_data(full_json_data, str(level_json_path))

        # 红头文件处理
        images_output_path=output_path/folder_name/('vlm' if vlm_enable else 'auto')/"page_images"
        images_output_path.mkdir(parents=True, exist_ok=True)
        post_process(input_file,images_output_path,level_json_path,cfg['LLM']['red_title']['API_KEY'],cfg['LLM']['red_title']['BASE_URL'],cfg['LLM']['red_title']['MODEL'],output_path,file_name,folder_name,vlm_enable,red_title_enable)
        partitions_json_path=output_path/folder_name/('vlm' if vlm_enable else 'auto')/f"{file_name}_partitions.json"
        with open(partitions_json_path,'r',encoding='utf-8') as f:
            return_json_partitions=json.load(f)#红头文件标题处理后的json
    
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

    return_json={
        "status_code": status_code,
        "status_message": status_message,
        "partitions": return_json_partitions if status_code == 200 else []
    }
    return return_json


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
    start_time=time.perf_counter()
    request_id = str(uuid.uuid4())
    status_code = 200
    status_message = "SUCCESS"
    return_json_partitions = []
    try:
        img_select, table_select = [], []

        if img_class:
            img_select.append("class")
        if img_desc:
            img_select.append("description")
        if img_html:
            img_select.append("html")
        if table_kv:
            table_select.append("key-value")
        if table_desc:
            table_select.append("description")
        if table_html:
            table_select.append("html")
        res = await core_analyze_pipeline(file, vlm_enable, img_select, table_select, request_id)
        
        output_path=res['output_path']
        folder_name=res["folder_name"]
        file_name=res["file_name"]
        timestamp=res["timestamp"]
        image_config=res["image_config"]
        table_config=res["table_config"]
        input_file=res["input_file"]
        table_number=res["table_number"]
        image_number=res["image_number"]
        layout_time=res["layout_time"]
        title_time=res["title_time"]
        image_time=res["image_time"]
        table_time=res["table_time"]
        # 2. 存储逻辑：将图表文件上传 MinIO
        images_path = Path(res['output_path']) / res["folder_name"] / res["sub_type"] / 'images'
        store_images(images_path, res["file_name"], res["timestamp"], cfg['MinIO']['IP'],cfg['MinIO']['ACCESS_KEY'],cfg['MinIO']['SECRET_KEY'],cfg['MinIO']['BUCKET_NAME'])
        # 修改图表的存储路径
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
        
        # 保存最终 JSON
        level_json_name = f'{file_name}_processed_with_levels.json'
        if vlm_enable:
            level_json_path = output_path / folder_name / 'vlm' / level_json_name
        else:
            level_json_path = output_path / folder_name / 'auto' / level_json_name
        save_json_data(full_json_data, str(level_json_path))

        # 红头文件处理
        images_output_path=output_path/folder_name/('vlm' if vlm_enable else 'auto')/"page_images"
        images_output_path.mkdir(parents=True, exist_ok=True)
        post_process(input_file,images_output_path,level_json_path,cfg['LLM']['red_title']['API_KEY'],cfg['LLM']['red_title']['BASE_URL'],cfg['LLM']['red_title']['MODEL'],output_path,file_name,folder_name,vlm_enable,red_title_enable)
        partitions_json_path=output_path/folder_name/('vlm' if vlm_enable else 'auto')/f"{file_name}_partitions.json"
        with open(partitions_json_path,'r',encoding='utf-8') as f:
            return_json_partitions=json.load(f)#红头文件标题处理后的json
    
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
    end_time=time.perf_counter()
    return_json={
        "status_code": status_code,
        "status_message": status_message,
        "time" : end_time-start_time,
        "layout_time" : layout_time,
        "title_time" : title_time,
        "image_time" : image_time,
        "table_time" : table_time,
        "image_number" : image_number,
        "table_number" : table_number,
        "partitions": return_json_partitions if status_code == 200 else []
    }
    return return_json

@app.post("/api/v1/xidian/preprocess_custom")
async def return_json_with_zip_save(
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
    status_code = 200
    status_message = "SUCCESS"
    return_json_partitions = []
    try:
        img_select, table_select = [], []

        if img_class:
            img_select.append("class")
        if img_desc:
            img_select.append("description")
        if img_html:
            img_select.append("html")
        if table_kv:
            table_select.append("key-value")
        if table_desc:
            table_select.append("description")
        if table_html:
            table_select.append("html")
        res = await core_analyze_pipeline(file, vlm_enable, img_select, table_select, request_id)
        
        output_path=res['output_path']
        folder_name=res["folder_name"]
        file_name=res["file_name"]
        timestamp=res["timestamp"]
        image_config=res["image_config"]
        table_config=res["table_config"]
        input_file=res["input_file"]
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
        
        # 保存最终 JSON
        level_json_name = f'{file_name}_processed_with_levels.json'
        if vlm_enable:
            level_json_path = output_path / folder_name / 'vlm' / level_json_name
        else:
            level_json_path = output_path / folder_name / 'auto' / level_json_name
        #level_json_path = output_path / file_name / 'vlm' / level_json_name
        save_json_data(full_json_data, str(level_json_path))


        images_output_path=output_path/folder_name/('vlm' if vlm_enable else 'auto')/"page_images"
        images_output_path.mkdir(parents=True, exist_ok=True)
        post_process_2(input_file,images_output_path,level_json_path,cfg['LLM']['red_title']['API_KEY'],cfg['LLM']['red_title']['BASE_URL'],cfg['LLM']['red_title']['MODEL'],output_path,file_name,folder_name,vlm_enable,red_title_enable)
        partitions_json_path=output_path/folder_name/('vlm' if vlm_enable else 'auto')/f'{file_name}_level_redtitle.json'
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

    return_json = return_json_partitions if status_code == 200 else []
    return return_json  

@app.post("/api/v1/mineru/json_only")
async def mineru_json_only_endpoint(
    file: UploadFile = File(...),
    vlm_enable: bool = Form(True)
):
    """
    轻量级接口：仅返回 MinerU 解析出的原始 JSON 数据
    """
    # 1. 准备服务器内部路径（从你的配置 cfg 中读取）
    temp_root = cfg['output_path_temp']
    final_root = cfg['output_path']
    
    # 2. 保存用户上传的文件到服务器本地 (为了传给 run_mineru_analysis_service)
    input_file = Path("./data/doc") / file.filename
    input_file.parent.mkdir(parents=True, exist_ok=True)
    with open(input_file, "wb") as f:
        f.write(await file.read())

    # 3. 构造文件夹名
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = f"{timestamp}_{Path(file.filename).stem}"

    #mineru调用
    mineru_start_time=time.perf_counter()
    output_path = Path(cfg['output_path']).resolve()
    request_id = str(uuid.uuid4())
    output_path_temp = Path(cfg['output_path_temp']).resolve()
    output_path.mkdir(parents=True, exist_ok=True)
    output_path_temp.mkdir(parents=True, exist_ok=True)
    task_temp_path = Path(cfg['output_path_temp']).resolve() / request_id
    task_temp_path.mkdir(parents=True, exist_ok=True)
    await call_mineru_api(input_file, task_temp_path, 'vlm-lmdeploy-engine' if vlm_enable else 'pipeline')
    mineru_end_time=time.perf_counter()

    #输出路径重整
    uuid_dirs = [d for d in task_temp_path.iterdir() if d.is_dir()]
    if len(uuid_dirs)>0:
        # Step 1: 找 temp 下唯一 uuid 目录
        
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
        target_dir = output_path / folder_name
        if target_dir.exists():
            shutil.rmtree(target_dir)

        shutil.move(str(result_dir), str(target_dir))

        print(f"mineru 输出已移动至: {target_dir}")
    shutil.rmtree(task_temp_path)
    json_path=target_dir/("vlm" if vlm_enable else "auto")/f"{Path(file.filename).stem}_middle.json"
    with open(json_path,'r',encoding='utf-8') as f:
        json_data=json.load(f)
    return json_data

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)