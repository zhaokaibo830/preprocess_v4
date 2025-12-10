import json
from pathlib import Path

from images_tables.image.tools import analyze_image_content
from images_tables.table.tools import table_extract

path="./processed_with_levels.json"
with open(path,'r',encoding="utf-8") as file:
      full_json_data=json.load(file)

print("以获取json数据")
output_path='./data/output'
file_name='test'
count=0
for page_index,page in enumerate(full_json_data["output"]):
    for block_index, block in enumerate(page["result"]):
        if block["type"]=="image":
            for sub_block_index,sub_block in enumerate(block["blocks"]):
                if sub_block["type"]=="image_body":
                    img_path=sub_block["lines"][0]["spans"][0]["image_path"]
                    img_path=Path(output_path)/f'{file_name}'/'vlm'/'images'/img_path
                    result=analyze_image_content(img_path,'sk-1fdbb0e4ce3943bab4b300ca867c1315','https://dashscope.aliyuncs.com/compatible-mode/v1','qwen3-vl-8b-instruct')
                    print(result)
                    full_json_data["output"][page_index]["result"][block_index]["description"]=result
                    count+=1
print(f"已处理{count}张图片")

count_table=0
for page_index,page in enumerate(full_json_data["output"]):
    for block_index, block in enumerate(page["result"]):
        if block["type"]=="table":
            for sub_block_index,sub_block in enumerate(block["blocks"]):
                if sub_block["type"]=="table_body":
                    #img_path=sub_block["lines"][0]["spans"][0]["image_path"]
                    #img_path=Path(output_path)/f'{file_name}'/'vlm'/'images'/img_path\
                    table_html=sub_block["lines"][0]["spans"][0]["html"]
                    result=table_extract(table_html,'sk-1fdbb0e4ce3943bab4b300ca867c1315','https://dashscope.aliyuncs.com/compatible-mode/v1','qwen3-14b')
                    print(result)
                    full_json_data["output"][page_index]["result"][block_index]["description"]=result
                    count+=1
print(f"已处理{count}个表格")
with open("./testoutput.json",'w',encoding='utf-8') as file:
    json.dump(full_json_data,file, ensure_ascii=False, indent=2)
