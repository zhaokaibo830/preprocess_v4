# red_title_process.py
import os
import json
import tempfile
from typing import Dict, List, Any, Optional
import fitz  # PyMuPDF

# 导入各个功能模块
from pdfchangeimage import pdf_to_images_memory
from deletelines import process_images_in_memory
from deletepageindex import delete_page_index_images_memory
from model_outputjson import ImageTextExtractor
from jsonchangefinal import update_json_in_memory

def red_title_process(
    input_file: str,  # PDF文件路径
    images_output_path: str,  # 图片输出路径
    json_data: Any,  # 要修改的JSON数据（Python对象）
    client: Any,  # 模型客户端
    delete_pages: List[int] = None  # 要删除的页码列表
) -> Dict[str, Any]:
    """
    红头文件处理接口函数
    
    Args:
        input_file: 输入的PDF文件路径
        images_output_path: PDF转图片存放的路径
        json_data: 要修改的JSON数据（Python对象，通常是dict或list）
        client: 模型客户端
        delete_pages: 要删除的页码列表，例如 [1, 2, 3] 删除第1,2,3页
    
    Returns:
        处理结果字典，包含修改后的JSON数据和统计信息
    """
    
    print("=" * 60)
    print("开始红头文件处理流程")
    print("=" * 60)
    
    result = {
        "success": False,
        "modified_json": None,
        "stats": {},
        "error": None
    }
    
    try:
        # 检查输入文件是否存在
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"PDF文件不存在: {input_file}")
        
        # 步骤1: PDF转图片
        print("\n【步骤1】PDF转图片")
        print("-" * 40)
        try:
            image_files = pdf_to_images_memory(input_file, images_output_path)
            print(f"成功转换 {len(image_files)} 张图片")
        except Exception as e:
            raise Exception(f"PDF转图片失败: {e}")
        
        # 如果没有转换出图片，提前返回
        if not image_files:
            raise Exception("没有转换出任何图片")
        
        # 步骤2: 删除没有线条的图片
        print("\n【步骤2】删除没有线条的图片")
        print("-" * 40)
        try:
            line_filtered_images = process_images_in_memory(images_output_path)
            print(f"过滤后剩余 {len(line_filtered_images)} 张图片")
        except Exception as e:
            print(f"线条过滤出错: {e}，继续使用原始图片")
            line_filtered_images = image_files
        
        # 步骤3: 删除指定页码的图片
        print("\n【步骤3】删除指定页码的图片")
        print("-" * 40)
        if delete_pages:
            print(f"将要删除的页码: {delete_pages}")
            try:
                page_filtered_images = delete_page_index_images_memory(
                    images_output_path, 
                    page_numbers=delete_pages
                )
            except Exception as e:
                print(f"页码删除出错: {e}，继续使用线条过滤后的图片")
                page_filtered_images = line_filtered_images
        else:
            print("未指定要删除的页码，跳过此步骤")
            page_filtered_images = line_filtered_images
        
        print(f"删除页码后剩余 {len(page_filtered_images)} 张图片")
        
        # 如果没有图片剩余，提前返回
        if not page_filtered_images:
            raise Exception("没有剩余的图片可以处理")
        
        # 步骤4: 使用多模态模型提取JSON
        print("\n【步骤4】使用多模态模型提取JSON")
        print("-" * 40)
        try:
            extractor = ImageTextExtractor(config=None, client=client)
            extracted_json = extractor.process_images_in_memory(
                images_output_path, 
                page_filtered_images
            )
            print(f"成功提取JSON数据")
        except Exception as e:
            print(f"模型提取失败: {e}")
            extracted_json = {"results": [], "metadata": {"total_text_items": 0}}
        
        # 步骤5: 修改原始JSON
        print("\n【步骤5】修改原始JSON")
        print("-" * 40)
        try:
            modified_json = update_json_in_memory(json_data, extracted_json)
            print("成功修改JSON数据")
        except Exception as e:
            raise Exception(f"修改JSON失败: {e}")
        
        # 统计信息
        result["success"] = True
        result["modified_json"] = modified_json
        result["stats"] = {
            "total_images": len(image_files),
            "after_line_filter": len(line_filtered_images),
            "after_page_filter": len(page_filtered_images),
            "deleted_pages": delete_pages if delete_pages else [],
            "extracted_items": len(extracted_json.get("results", [])) if extracted_json else 0,
            "modified_count": sum(1 for r in extracted_json.get("results", []) if r.get("classified_items")) if extracted_json else 0
        }
        
        print("\n" + "=" * 60)
        print("处理完成！")
        print("=" * 60)
        
    except Exception as e:
        result["error"] = str(e)
        print(f"\n❌ 处理失败: {e}")
        import traceback
        traceback.print_exc()
    
    return result


# 便捷函数：直接处理PDF文件
def process_pdf_red_title(
    pdf_path: str,
    json_data: Any,
    client: Any,
    delete_pages: List[int] = None,
    output_dir: str = "./temp_images"
) -> Dict[str, Any]:
    """
    便捷函数：直接处理PDF文件
    
    Args:
        pdf_path: PDF文件路径
        json_data: 原始JSON数据
        client: 模型客户端
        delete_pages: 要删除的页码列表
        output_dir: 临时图片输出目录
    
    Returns:
        处理结果
    """
    return red_title_process(
        input_file=pdf_path,
        images_output_path=output_dir,
        json_data=json_data,
        client=client,
        delete_pages=delete_pages
    )