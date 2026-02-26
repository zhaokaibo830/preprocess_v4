from pathlib import Path
import os
from utils.filePathRearrange import path_rearrange

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


def mineru_layout(input_file,output_path:Path,request_id,output_path_temp:Path,folder_name,vlm_enable):
    output_path.mkdir(parents=True, exist_ok=True)
    output_path_temp.mkdir(parents=True, exist_ok=True)
    task_temp_path = Path(cfg['output_path_temp']).resolve() / request_id
    task_temp_path.mkdir(parents=True, exist_ok=True)
    call_mineru_api(input_file, task_temp_path, 'vlm-lmdeploy-engine' if vlm_enable else 'pipeline')
    path_rearrange(task_temp_path, output_path, folder_name)