import datetime
import os
import pathlib
from pathlib import Path
import sys
parent_path = Path(__file__).parent.parent 
sys.path.insert(0, str(parent_path))
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
AVALIABLE_FORMATS = ["pdf", "docx", "doc", "wps", "odt", "pptx", "ppt", "ofd", "md", "ceb", "jpg", "jpeg", "png", "txt"]

async def interface1_json(save_filepath,vlm_enable,red_title_enable,image_class,image_desc,image_html,table_kv,table_desc,table_html,cfg,request_id):

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

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
    """
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
    """
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
        json_data = await mineru_layout(save_filepath,output_path,request_id,output_path_temp,folder_name,vlm_enable,file_name)
        print("mineru服务调用完成，开始后续处理...")
        #print(f"mineru服务返回的初始json数据: {json_data}")
        json_data, title_error_info = title_process(
            title_client,#大模型client
            cfg['title_model']['MODEL'],
            json_data,#json数据，避免io
            output_path,
            file_name,
            folder_name,
            vlm_enable
        )
        #print(f"标题层级分析完成，json数据: {json_data}")
        json_data , image_error_msg, image_count = add_image_info(json_data, vlm_enable, image_client,cfg['image_model']['MODEL'], output_path, folder_name, image_class, image_desc, image_html)

        json_data, table_error_info, table_count= add_table_info(json_data, vlm_enable, table_client,cfg['table_model']['MODEL'], output_path, folder_name, table_kv, table_desc, table_html)
        
        #上传图片到minio
        remove_equations(json_data,output_path,folder_name,vlm_enable)
        images_path = output_path / folder_name / ('vlm' if vlm_enable else 'auto') / 'images'
        store_images(images_path, file_name, timestamp, cfg['MinIO']['IP'],cfg['MinIO']['ACCESS_KEY'],cfg['MinIO']['SECRET_KEY'],cfg['MinIO']['BUCKET_NAME'])
        json_data = changeImagesPath(json_data, output_path, folder_name, vlm_enable, cfg, timestamp, file_name)
        with open('../../test.json', 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=4)
        #红头文件处理
        images_output_path=output_path/folder_name/('vlm' if vlm_enable else 'auto')/"page_images"
        images_output_path.mkdir(parents=True, exist_ok=True)
        """
        if red_title_enable:
            #红头文件信息提取
            #返回加入红头文件信息的json和红头处理的错误信息，如果没有错误则为空字符串
            json_data, red_title_error_msg = red_title_process(
                save_filepath,#pdf文件路径
                images_output_path,#pdf转图片的保存路径
                json_data,#待处理的完整json数据
                red_title_client,#已创建好的大模型client
                cfg['red_title_model']['MODEL'] # 大模型model name
                )

        #将json格式转换为甲方指定格式
        json_data = convert_json_format(json_data)
        """
    except FileNotFoundError as e:
        status_code = 404
        status_message = f"FILE_NOT_FOUND: {str(e)}"
    """
    except PermissionError as e:
        status_code = 403
        status_message = f"PERMISSION_DENIED: {str(e)}"
    except ValueError as e:
        status_code = 400
        status_message = f"BAD_REQUEST: {str(e)}"
    except Exception as e:
        status_code = 500
        status_message = f"INTERNAL_ERROR: {str(e)}"
    """
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
    return_json={
        "status_code": status_code,
        "status_message": status_message,
        "partitions": json_data if status_code == 200 else []
    }
    return return_json
