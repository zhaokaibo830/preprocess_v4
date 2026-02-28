# deletepageindex.py
import os
import glob
from typing import List

def delete_page_index_images_memory(folder_path: str, page_numbers: List[int]) -> List[str]:
    """
    删除指定页码结尾的图片文件，返回保留的图片列表
    
    Args:
        folder_path: 图片文件夹路径
        page_numbers: 要删除的页码列表
    
    Returns:
        保留的图片文件路径列表
    """
    if not os.path.exists(folder_path):
        print(f"错误：文件夹 '{folder_path}' 不存在")
        return []
    
    # 确保输入是字符串列表
    page_strs = [str(page) for page in page_numbers]
    
    kept_images = []
    deleted_files = []
    
    # 遍历所有png文件
    for file_path in glob.glob(os.path.join(folder_path, "*.png")):
        filename = os.path.basename(file_path)
        should_delete = False
        
        # 检查文件名是否以指定页码结尾
        for page_str in page_strs:
            if filename.endswith(f"_{page_str}.png"):
                should_delete = True
                break
        
        if should_delete:
            try:
                os.remove(file_path)
                deleted_files.append(filename)
                print(f"  删除: {filename}")
            except Exception as e:
                print(f"  删除失败 {filename}: {e}")
        else:
            kept_images.append(file_path)
    
    print(f"\n页码过滤完成: 保留 {len(kept_images)} 张, 删除 {len(deleted_files)} 张")
    
    return kept_images