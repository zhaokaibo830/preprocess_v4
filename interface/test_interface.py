import datetime
import time
import os
import pathlib
from pathlib import Path
import sys
parent_path = Path(__file__).parent.parent 
#sys.path.insert(0, str(parent_path))
from pathlib import Path
from fastapi import HTTPException, UploadFile
from fastapi.responses import JSONResponse
from format.formatTransform import format
from utils.client import *
from layout.mineru_call import mineru_layout
from titles.title_process import title_process
from images_tables.image.image_info import *
from images_tables.table.table_info import *
from utils.rm_equations import *
from minioStore.store import store_images
from minioStore.changePath import changeImagesPath
from utils.client import create_client
import json
from  utils.get_index_list import get_page_index_list
from red_title.redtitle import red_title_process
from utils.jsonchangefunction import convert_json_format
AVALIABLE_FORMATS = ["pdf", "docx", "doc", "wps", "odt", "pptx", "ppt", "ofd", "md", "ceb", "jpg", "jpeg", "png", "txt"]

async def test_interface_json(save_filepath,vlm_enable,red_title_enable,image_class,image_desc,image_html,table_kv,table_desc,table_html,cfg,request_id):

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    start_time = time.perf_counter()  # 记录开始时间
    output_path = Path(cfg['output_path']).resolve() 
    output_path_temp = Path(cfg['output_path_temp']).resolve()
    folder_name=f"{timestamp}_{Path(save_filepath).stem}"

    print(f"接口1核心逻辑参数: vlm_enable={vlm_enable}, red_title_enable={red_title_enable}, image_class={image_class}, image_desc={image_desc}, image_html={image_html}, table_kv={table_kv}, table_desc={table_desc}, table_html={table_html}")
    print("创建大模型客户端...")
    title_client = create_client(cfg['title_model']['BASE_URL'], cfg['title_model']['API_KEY'], cfg['title_model']['connection_timeout'], cfg['title_model']['process_timeout'])
    image_client = create_client(cfg['image_model']['BASE_URL'], cfg['image_model']['API_KEY'], cfg['image_model']['connection_timeout'], cfg['image_model']['process_timeout'])
    table_client = create_client(cfg['table_model']['BASE_URL'], cfg['table_model']['API_KEY'], cfg['table_model']['connection_timeout'], cfg['table_model']['process_timeout'])
    red_title_client = create_client(cfg['red_title_model']['BASE_URL'], cfg['red_title_model']['API_KEY'], cfg['red_title_model']['connection_timeout'], cfg['red_title_model']['process_timeout'])
    print("大模型客户端创建完成")
    
    status_code = 200
    status_message = "SUCCESS"
    title_error_msg = ""
    image_error_msg = ""
    table_error_msg = ""
    red_title_error_msg = ""
    try:
        #将文件转为pdf格式
        file_format = Path(save_filepath).suffix[1:]
        print(f"上传文件格式: {file_format}")
        file_name = Path(save_filepath).stem
        print(f"上传文件名: {file_name}")
        folder_name=f"{timestamp}_{file_name}"
        print(f"生成的文件夹名: {folder_name}")
        if file_format in AVALIABLE_FORMATS:
            if file_format != "pdf":
                save_filepath = format(save_filepath)
        else:
            raise HTTPException(status_code=400, detail=f"不支持的文件格式：{file_format}")
        print(f"文件已保存并转换为PDF格式，路径: {save_filepath}")
        #调用mineru服务进行布局分析，获取json数据
        print("调用mineru服务进行布局分析...")
        mineru_start_time = time.perf_counter()  # 记录mineru开始时间
        json_data = await mineru_layout(save_filepath,output_path,request_id,output_path_temp,folder_name,vlm_enable,file_name)
        mineru_time = time.perf_counter() - mineru_start_time  # 计算mineru耗时
        print("mineru服务调用完成，开始后续处理...")
        #print(f"mineru服务返回的初始json数据: {json_data}")
        title_start_time = time.perf_counter()  # 记录标题处理开始时间
        json_data, title_error_info = title_process(
            title_client,#大模型client
            cfg['title_model']['MODEL'],
            json_data,#json数据，避免io
            output_path,
            file_name,
            folder_name,
            vlm_enable
        )
        title_time = time.perf_counter() - title_start_time  # 计算标题处理耗时

        #print(f"标题层级分析完成，json数据: {json_data}")
        image_start_time = time.perf_counter()  # 记录图片处理开始时间
        json_data , image_error_msg, image_count = add_image_info(json_data, vlm_enable, image_client,cfg['image_model']['MODEL'], output_path, folder_name, image_class, image_desc, image_html)
        image_time = time.perf_counter() - image_start_time  # 计算图片处理耗时

        table_start_time = time.perf_counter()  # 记录表格处理开始时间
        json_data, table_error_info, table_count= add_table_info(json_data, vlm_enable, table_client,cfg['table_model']['MODEL'], output_path, folder_name, table_kv, table_desc, table_html)
        table_time = time.perf_counter() - table_start_time  # 计算表格处理耗时

        #上传图片到minio
        remove_equations(json_data,output_path,folder_name,vlm_enable)
        images_path = output_path / folder_name / ('vlm' if vlm_enable else 'auto') / 'images'
        store_images(images_path, file_name, timestamp, cfg['MinIO']['IP'],cfg['MinIO']['ACCESS_KEY'],cfg['MinIO']['SECRET_KEY'],cfg['MinIO']['BUCKET_NAME'])
        json_data = changeImagesPath(json_data, output_path, folder_name, vlm_enable, cfg, timestamp, file_name)

        #红头文件处理
        images_output_path=output_path/folder_name/('vlm' if vlm_enable else 'auto')/"page_images"
        images_output_path.mkdir(parents=True, exist_ok=True)
        
        if red_title_enable:
            red_title_start_time = time.perf_counter()  # 记录红头处理开始时间
            #红头文件信息提取
            #返回加入红头文件信息的json和红头处理的错误信息，如果没有错误则为空字符串
            to_delete_page_index_list = get_page_index_list(json_data)
            result = red_title_process(
                save_filepath,#pdf文件路径
                images_output_path,#pdf转图片的保存路径
                json_data,#待处理的完整json数据
                red_title_client,#已创建好的大模型client
                cfg['red_title_model']['MODEL'], # 大模型model name
                delete_pages=to_delete_page_index_list
                )
            json_data = result.get("modified_json", json_data)  # 如果处理成功，使用修改后的JSON；否则继续使用原JSON
            red_title_error_info = result.get("error", "")
            red_title_time = time.perf_counter() - red_title_start_time  # 计算红头处理耗时
        #将json格式转换为甲方指定格式
        else:
            red_title_time = 0
        json_data = convert_json_format(json_data)
        
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
    
    title_client.close()
    image_client.close()
    table_client.close()
    red_title_client.close()
    

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
    total_time = time.perf_counter() - start_time  # 计算总耗时
    return_json={

        "status_code": status_code,
        "status_message": status_message,
        "time":total_time,
        "layout_time": mineru_time,
        "title_time": title_time,
        "image_time": image_time,
        "table_time": table_time,
        "red_title_time": red_title_time,
        "image_number": image_count,
        "table_number": table_count,
        "partitions": json_data if status_code == 200 else []
    }
    return return_json
