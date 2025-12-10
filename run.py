import json
import sys

import yaml


from images_tables.image.tools import analyze_image_content
from images_tables.table.tools import table_extract
from format.formatTransform import format
from layout.outputjs import merge_blocks
from titles.get_title import *
from pathlib import Path
import subprocess
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
import uuid, os, json, shutil
from fastapi import HTTPException 
app = FastAPI()

AVALIABLE_FORMATS=["pdf","docx","doc","wps","odt","pptx","ppt","ofd","md","ceb","jpg","jpeg","png","txt"]

with open("config.yaml",'r',encoding='utf-8') as file:
    cfg = yaml.safe_load(file)

#OUTPUT_PATH="./data/output"
@app.post("/api/preprocessv4")
async def preprocess(file: UploadFile = File(...),img_enable: bool = Form(...),   # 开关 1
    table_enable: bool = Form(...) ):

    #加载cfg
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

    input_file=save_filepath
    file_format=Path(input_file).suffix
    file_format=file_format[1:]
    file_name=Path(input_file).stem
    if file_format in AVALIABLE_FORMATS:
        if file_format!="pdf":
            input_file=format(input_file)#返回路径也是绝对路径

    else:
        raise HTTPException(
        status_code=400,
        detail=f"不支持的文件格式：{file_format}"
    )

    #版面识别
    output_path=cfg['output_path']
    output_path=Path(output_path).resolve()
    cmd = [
    'mineru',
    '-p', str(input_file),
    '-o', str(output_path),
    '--backend', 'vlm-transformers',
    '--device', 'cuda',
    '--source', 'local'
    ]
    subprocess.run(cmd, check=True)
    middle_json_name = f'{file_name}_middle.json'
    target_json = output_path / file_name / 'vlm' / middle_json_name
    # 读取JSON文件
    with open(target_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 处理数据
    processed_data = merge_blocks(data)


    output_data = {"output": processed_data["pdf_info"]}
    #output_data.setdefault("metadata", {})
    #output_data['metadata']['name']=file_name
    # 保存到新文件
    final_json_name=f'{file_name}_middle_final.json'
    final_json_path=output_path / file_name / 'vlm' / final_json_name
    with open(final_json_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print("处理完成，已保存到 demo0_middle_final.json")


    #标题处理
    try:
        # 1. 加载完整的嵌套 JSON 结构
        full_json_data = load_json_data(final_json_path)
        # 2. 获取段落块的扁平列表 (引用)
        json_data_flat = flatten_json_data(full_json_data)
        # 3. 提取所有文本作为上下文
        full_context = extract_all_text_context(json_data_flat)

    except Exception as e:
        print(f"Startup Failed: {e}")
        sys.exit(1)

    # 4. 调用核心处理逻辑，传入上下文
    final_title_list = get_markdown_titles_with_level(json_data_flat, full_context,cfg['LLM']['title_model']['LLM_API_KEY'],cfg['LLM']['title_model']['LLM_BASE_URL'],cfg['LLM']['title_model']['LLM_MODEL'])


    print("3. Mapping levels and backfilling JSON data...")
    title_level = {}
    default_level = 1

    if final_title_list:
        # 建立 LLM 成功输出的标题到层级的映射
        for one_title in final_title_list:
            level = count_leading_hashes(one_title)
            clean_key = filter_string(re.sub(r'^#+\s*', '', one_title).strip())
            if clean_key:
                title_level[clean_key] = level

    match_count = 0
    fallback_count = 0
    total_title_blocks = 0

    # 5. 遍历扁平列表，对原结构进行修改 (只增加 'level' 字段)
    for para in json_data_flat:
        if para.get("type") == "title":
            total_title_blocks += 1
            original_text = extract_text_content(para)
            original_key = filter_string(original_text)

            level = title_level.get(original_key)

            if level is None:
                # 触发回退机制： LLM 过滤了该标题，或 LLM 根本没有输出
                para["level"] = default_level
                fallback_count += 1
            else:
                # 成功找到 LLM 结构化后的层级
                para["level"] = level

            match_count += 1 # 统计已处理的标题块


    print(f"   Total type='title' blocks processed: {total_title_blocks}")
    print(f"   - Successfully matched LLM output: {match_count - fallback_count}")
    print(f"   - Assigned fallback level ({default_level}): {fallback_count}")

    # 6. 保存完整的原始 JSON 结构
    level_json_name=f'{file_name}_processed_with_levels.json'
    level_json_path=output_path / file_name / 'vlm' / level_json_name
    save_json_data(full_json_data, level_json_path)
    print(f"--- Task Complete. Result saved to: {level_json_path} ---")



    #表格和图片处理
    


    #根据输出的processed_with_levels.json选出图片和表格进行处理，顺便把处理结果加入json文件中
    #processed_with_levels.json的结构：output；pages(包括page size，page index和result)；result通过type确定为image，在image中确定图片本体和caption


    if img_enable:
        count=0
        for page_index,page in enumerate(full_json_data["output"]):
            for block_index, block in enumerate(page["result"]):
                if block["type"]=="image":
                    for sub_block_index,sub_block in enumerate(block["blocks"]):
                        if sub_block["type"]=="image_body":
                            img_path=sub_block["lines"][0]["spans"][0]["image_path"]
                            img_path=Path(output_path)/f'{file_name}'/'vlm'/'images'/img_path
                            result=analyze_image_content(img_path,cfg['LLM']['img']['API_KEY'],cfg['LLM']['img']['BASE_URL'],cfg['LLM']['img']['MODEL'])
                            #print(result)
                            full_json_data["output"][page_index]["result"][block_index]["description"]=result
                            count+=1
        print(f"已处理{count}张图片")
        '''
        ToprocessList=[]
        for index,entity in enumerate(content_list_data):
            if entity["type"]=="image":
        #获取到的imgPath是"images/6c2408db7ca86b33b1381477e4952284f03f1d5c67986f2d00f4ce80dca594ac.jpg"
        #实际应该是data/output/filename/vlm/images/.......               
                img_path=Path(output_path)/f'{file_name}'/'vlm'/entity["img_path"]
                ToprocessList.append(img_path)
        
        #vlm处理图片
        for index,img in enumerate(ToprocessList):
            result=analyze_image_content(img,cfg['LLM']['img']['API_KEY'],cfg['LLM']['img']['BASE_URL'],cfg['LLM']['img']['MODEL'])

            #保存result
        '''



    if table_enable:
        count_table=0
        for page_index,page in enumerate(full_json_data["output"]):
            for block_index, block in enumerate(page["result"]):
                if block["type"]=="table":
                    for sub_block_index,sub_block in enumerate(block["blocks"]):
                        if sub_block["type"]=="table_body":
                            table_html=sub_block["lines"][0]["spans"][0]["html"]
                            result=table_extract(table_html,cfg['LLM']['table']['API_KEY'],cfg['LLM']['table']['BASE_URL'],cfg['LLM']['table']['MODEL'] )
                            print(result)
                            full_json_data["output"][page_index]["result"][block_index]["description"]=result
                            count_table+=1
        print(f"已处理{count_table}个表格")
        """
        ToprocessTableList=[]
        for index,entity in enumerate(content_list_data):
            if entity["type"]=="table":
                ToprocessTableList.append(entity["table_body"])
            
        for index,table in enumerate(ToprocessTableList):
            result=table_extract(table,cfg['LLM']['table']['API_KEY'],cfg['LLM']['table']['BASE_URL'],cfg['LLM']['table']['MODEL'] )

            #保存table分析结果
        """
    save_json_data(full_json_data, level_json_path)
    return FileResponse(
        level_json_path,
        media_type="application/json",
        filename=os.path.basename(level_json_path)
    )
if __name__=="__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)









