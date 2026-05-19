from pathlib import Path
import os
from utils.filePathRearrange import path_rearrange
from layout.outputjs import merge_blocks
from layout.output_pipeline import merge_blocks_pipeline
from layout.changeJson import *
import httpx
# 调用mineru服务
async def call_mineru_api(input_file_path, output_dir, backend):
    print("calling mineru service...")
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
            # 异步发送请求，此时 8000 服务可以去干别的事
            print("发送请求到mineru服务...")
            response = await client.post("http://127.0.0.1:8000/file_parse", files=files, data=data)
            print("收到mineru服务响应")
            return response.json()


#布局处理函数，负责布局分析，文件路径管理，调用mineru服务，以及后续的json格式处理
async def mineru_layout(input_file,output_path,request_id,output_path_temp,folder_name,vlm_enable,file_name):
    output_path.mkdir(parents=True, exist_ok=True)
    output_path_temp.mkdir(parents=True, exist_ok=True)
    task_temp_path = Path(output_path_temp) / request_id
    task_temp_path.mkdir(parents=True, exist_ok=True)
    print(f"临时路径: {task_temp_path}")
    print("开始调用mineru服务进行布局分析...")
    await call_mineru_api(input_file, task_temp_path, 'vlm-lmdeploy-engine' if vlm_enable else 'pipeline')
    print("mineru服务调用完成，开始路径整理...")
    path_rearrange(task_temp_path, output_path, folder_name)

    middle_json_name = f'{file_name}_middle.json'
    if vlm_enable:
        target_json = output_path / folder_name / 'vlm' / middle_json_name
    else:
        target_json = output_path / folder_name / 'auto' / middle_json_name
    with open(target_json, "r", encoding="utf-8") as f:
        json_data = json.load(f)

    if vlm_enable:
        processed_data = merge_blocks(json_data)
    else:
        processed_data = merge_blocks_pipeline(json_data)

    output_data = {"output": processed_data["pdf_info"]}
    output_data = modify_json_structure_complete(output_data)

    return output_data

if __name__ == "__main__":
    #import argparse
    #parser = argparse.ArgumentParser(description="调用mineru服务进行布局分析")
    #parser.add_argument("input_file", type=str, help="输入文件路径")
    #parser.add_argument("output_dir", type=str, help="输出目录路径")
    #parser.add_argument("--vlm_enable", action="store_true", help="是否启用VLM模式")
    #args = parser.parse_args()

    import asyncio
    asyncio.run(call_mineru_api("/home/bestwish/preprocessTest/test428/files/verify.pdf", "/home/bestwish/data/output", 'vlm-lmdeploy-engine' ))
    #result = asyncio.run(mineru_layout(args.input_file, args.output_dir, "test_request_id", Path("/home/bestwish/data/temp"), "/home/bestwish/data/output", True, Path(args.input_file).stem))
    print(json.dumps(result, ensure_ascii=False, indent=4))