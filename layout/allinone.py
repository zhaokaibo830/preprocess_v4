from pdf2imgs import pdf_to_images
from deletelines import clean_folder_without_lines
from get_index_list import get_page_index_list
from deletepageindex import delete_specific_pages
from model_outputjson import ImageTextExtractor
from jsonchangefinal import json_change_format
from specific_json import load_and_process_json
import os
from pathlib import Path
import json
CONFIG = {
    # LLM API 配置
    "LLM_API_KEY": "sk-734ae048099b49b5b4c7981559765228",
    "LLM_BASE_URL": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "LLM_MODEL": "qwen-vl-max",

    # 文件路径配置
    "INPUT_PATH": "./test",
    "OUTPUT_PATH": "./test_json",
}

#单独处理红头文件信息，并转换json格式
def post_process(pdf_path,images_output_path,original_json_path,api_key,base_url,model_name,output_path,file_name,folder_name,vlm_enable,red_title,connection_timeout,process_timeout):
    if red_title:
        # step1：将文档pdf按页转png
        pdf_to_images(pdf_path,images_output_path)
        # 基于视觉模型判断红线，将不包含线段的图片删除
        clean_folder_without_lines(images_output_path)
        # 根据json获取包含图表的页码，删除这些页
        index_list = get_page_index_list(original_json_path)
        delete_specific_pages(images_output_path,index_list)

        #基于多模态分析筛选后的page

        # 多模态提取的红头文件json
        json_temp_path=output_path/folder_name/('vlm' if vlm_enable else 'auto')/f'{file_name}_redtitle.json'
        config={
            "LLM_API_KEY": api_key,
            "LLM_BASE_URL": base_url,
            "LLM_MODEL": model_name,
            "INPUT_PATH":images_output_path,
            "OUTPUT_PATH":json_temp_path,
            "CONNECTION_TIMEOUT": connection_timeout,
            "PROCESS_TIMEOUT": process_timeout
        }
        extractor = ImageTextExtractor(config)
        results ,error_msg = extractor.process_all_images()#红头文件提取结果
        #输出红头文件json和processed_with_level.json，将二者合并
        json_final=json_change_format(json_temp_path,original_json_path)#将上述结果写入full_json_data

        json_level_redtitle_path=output_path/folder_name/('vlm' if vlm_enable else 'auto')/f'{file_name}_level_redtitle.json'
        with open(json_level_redtitle_path,'w',encoding='utf-8') as f:
            json.dump(json_final,f,ensure_ascii=False,indent=2)

        #将json转为甲方要求的格式，存到f"{file_name}_partitions.json"
        json_return_path=output_path/folder_name/('vlm' if vlm_enable else 'auto')/f"{file_name}_partitions.json"
        load_and_process_json(json_final,json_return_path)#对full_json_data进行格式转换，写入f"{file_name}_partitions.json"
        return error_msg
    else:
        error_msg = None
        #跳过红头文件处理阶段，将红头文件处理结果设为空字典
        json_temp_path=output_path/folder_name/('vlm' if vlm_enable else 'auto')/f'{file_name}_redtitle.json'
        json_data={}
        with open(json_temp_path,'w',encoding='utf-8') as f:
            json.dump(json_data,f,ensure_ascii=False,indent=2)
        json_final=json_change_format(json_temp_path,original_json_path)
        json_level_redtitle_path=output_path/folder_name/('vlm' if vlm_enable else 'auto')/f'{file_name}_level_redtitle.json'
        with open(json_level_redtitle_path,'w',encoding='utf-8') as f:
            json.dump(json_final,f,ensure_ascii=False,indent=2)
        json_return_path=output_path/folder_name/('vlm' if vlm_enable else 'auto')/f"{file_name}_partitions.json"
        load_and_process_json(json_final,json_return_path)
        return error_msg
#只处理红头文件标题，不修改json格式
def post_process_2(pdf_path,images_output_path,original_json_path,api_key,base_url,model_name,output_path,file_name,folder_name,vlm_enable,red_title,connection_timeout,process_timeout):
    if red_title:
        pdf_to_images(pdf_path,images_output_path)
        clean_folder_without_lines(images_output_path)
        index_list=get_page_index_list(original_json_path)
        delete_specific_pages(images_output_path,index_list)

        json_temp_path=output_path/folder_name/('vlm' if vlm_enable else 'auto')/f'{file_name}_redtitle.json'

        config={
            "LLM_API_KEY": api_key,
            "LLM_BASE_URL": base_url,
            "LLM_MODEL": model_name,
            "INPUT_PATH":images_output_path,
            "OUTPUT_PATH":json_temp_path,
            "CONNECTION_TIMEOUT": connection_timeout,
            "PROCESS_TIMEOUT": process_timeout

        }
        extractor = ImageTextExtractor(config)
        results,error_msg = extractor.process_all_images()
        json_final=json_change_format(json_temp_path,original_json_path)

        #在processed_with_level的基础上加入红头文件处理结果，存入f'{file_name}_level_redtitle.json'
        json_level_redtitle_path=output_path/folder_name/('vlm' if vlm_enable else 'auto')/f'{file_name}_level_redtitle.json'
        with open(json_level_redtitle_path,'w',encoding='utf-8') as f:
            json.dump(json_final,f,ensure_ascii=False,indent=2)
        #json_return_path=output_path/folder_name/('vlm' if vlm_enable else 'auto')/f"{file_name}_partitions.json"
        #load_and_process_json(json_final,json_return_path)
        return error_msg
    else:
        error_msg = None
        json_temp_path=output_path/folder_name/('vlm' if vlm_enable else 'auto')/f'{file_name}_redtitle.json'
        json_data={}
        with open(json_temp_path,'w',encoding='utf-8') as f:
            json.dump(json_data,f,ensure_ascii=False,indent=2)
        json_final=json_change_format(json_temp_path,original_json_path)
        json_level_redtitle_path=output_path/folder_name/('vlm' if vlm_enable else 'auto')/f'{file_name}_level_redtitle.json'
        with open(json_level_redtitle_path,'w',encoding='utf-8') as f:
            json.dump(json_final,f,ensure_ascii=False,indent=2)
        #json_return_path=output_path/folder_name/('vlm' if vlm_enable else 'auto')/f"{file_name}_partitions.json"
        #load_and_process_json(json_final,json_return_path)
        return error_msg

if __name__=="__main__":
    pdf_path="../data/doc/公司-国网陕电人资〔2021〕36号-国网陕西省电力有限公司关于各层级组织机构融合情况的报告.pdf"
    output_path="./test"
    json_path="./listtest.json"
    #step1:pdf转img
    pdf_to_images(pdf_path,output_path)
    #step2：利用视觉模型删除没有线的页码
    clean_folder_without_lines(output_path)
    #step3：删除包含表格或图片的页码
    index_list=get_page_index_list(json_path)
    delete_specific_pages(output_path,index_list)
    # step4:多模态提取特定文字
    extractor = ImageTextExtractor(CONFIG)
    results = extractor.process_all_images()
    #step5:写入提取结果并转json格式
    json_final=json_change_format('./test_json/extracted_texts.json','./listtest.json')
    with open('./test_json/output1.json','w',encoding='utf-8') as f:
        json.dump(json_final,f,ensure_ascii=False,indent=2)
    load_and_process_json('./test_json/output1.json','./test_json/output2.json')
     
    #step5：修改格式