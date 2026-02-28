from pathlib import Path
from tools import analyze_image_content
def add_image_info(full_json_data, vlm_enable, client, model_name, image_class=True, image_desc=True, image_html=True):
    image_error_msg = ""
    if  image_class or image_desc or image_html:

        def build_consistent_error_json(reason):
                err_dict = {}
                if image_class:
                    err_dict["type"] = "error"
                if image_desc:
                    err_dict["desc"] = f"处理失败/已跳过: {reason}。本内容由AI生成，内容仅供参考。"
                if image_html:
                    err_dict["html"] = f"<table><tr><td>错误信息：{reason}</td></tr></table>"
                return err_dict

        #img_time_start=time.perf_counter()
        #img_jobs = []
        #print(f"图片处理选项为{image_config}，开始处理图片...")
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
                    result = analyze_image_content(img_path,img_title,
                        image_class,
                        image_desc,
                        image_html,
                        client,
                        model_name
                    ),
                    block["llm_process"] = result
                except Exception as e:
                    stop_processing = True  # 触发熔断
                    final_error_info = str(e)  # 记录错误信息
                    image_error_msg = final_error_info
                    block["llm_process"] = build_consistent_error_json(final_error_info)
                    print(f"!!! 严重错误：处理第 {image_count} 张图片时发生异常，已启动熔断 !!!")
                    print(f"错误详情: {final_error_info}")
                
        print(f"已处理{image_count}张图片")          
        #img_end_time=time.perf_counter()
    else:
        print("图片处理选项为空，跳过图片处理步骤。")
        #img_start_time=0
        #img_end_time=
        image_count = 0
    return full_json_data, image_error_msg, image_count