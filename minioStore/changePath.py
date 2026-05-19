from pathlib import Path

def changeImagesPath(full_json_data, output_path, folder_name, vlm_enable,cfg, timestamp, file_name):
    """
    将full_json_data中图片路径从原来的路径修改为新的路径
    """
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
    return full_json_data