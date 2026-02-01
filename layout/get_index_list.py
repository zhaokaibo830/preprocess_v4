import os
from pathlib import Path
import json

def get_page_index_list(json_path)->set:
    with open(json_path,encoding='utf-8') as f:
        json_data=json.load(f)
    result=set()
    for block_index,block in enumerate(json_data["output"]):
        if block["type"]=="table" or block["type"]=="image":
            result.add(block["page_idx"]+1)
    return result

if __name__=="__main__":
    json_path="./listtest.json"

    result=get_page_index_list(json_path)
    print(result)