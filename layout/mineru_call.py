from pathlib import Path
import os
from utils.filePathRearrange import path_rearrange
from layout.outputjs import merge_blocks
from layout.output_pipeline import merge_blocks_pipeline
from layout.changeJson import *

# 调用mineru服务
def call_mineru_api(input_file_path, output_dir, backend):
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


#布局处理函数，负责布局分析，文件路径管理，调用mineru服务，以及后续的json格式处理
def mineru_layout(input_file,output_path:Path,request_id,output_path_temp:Path,folder_name,vlm_enable,file_name):
    output_path.mkdir(parents=True, exist_ok=True)
    output_path_temp.mkdir(parents=True, exist_ok=True)
    task_temp_path = Path(cfg['output_path_temp']).resolve() / request_id
    task_temp_path.mkdir(parents=True, exist_ok=True)

    call_mineru_api(input_file, task_temp_path, 'vlm-lmdeploy-engine' if vlm_enable else 'pipeline')

    path_rearrange(task_temp_path, output_path, folder_name)

    middle_json_name = f'{file_name}_middle.json'
    if vlm_enable:
        target_json = output_path / folder_name / 'vlm' / middle_json_name
    else:
        target_json = output_path / folder_name / 'auto' / middle_json_name
    with open(target_json, "r", encoding="utf-8") as f:
        json_data = json.load(f)

    if vlm_enable:
        processed_data = merge_blocks(data)
    else:
        processed_data = merge_blocks_pipeline(data)

    output_data = {"output": processed_data["pdf_info"]}
    output_data = modify_json_structure_complete(output_data)

    return output_data