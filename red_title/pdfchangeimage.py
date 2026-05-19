# pdfchangeimage.py
import os
import fitz  # PyMuPDF
from typing import List

def pdf_to_images_memory(pdf_path: str, output_folder: str, dpi: int = 300) -> List[str]:
    """
    将PDF转换为图片，返回图片文件路径列表
    
    参数:
        pdf_path: PDF文件路径
        output_folder: 输出图片的文件夹
        dpi: 图片分辨率，默认300
    
    返回:
        生成的图片文件路径列表
    """
    # 确保输出文件夹存在
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    # 打开PDF文件
    pdf_document = fitz.open(pdf_path)
    
    # 获取PDF文件名（不含扩展名）
    pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
    
    # 获取总页数（在关闭文档前获取）
    total_pages = len(pdf_document)
    
    image_files = []
    
    # 逐页转换
    for page_num in range(total_pages):
        try:
            page = pdf_document.load_page(page_num)
            
            # 设置缩放比例以获得高分辨率
            zoom = dpi / 72  # 72是默认的DPI
            mat = fitz.Matrix(zoom, zoom)
            
            # 渲染页面为图片
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            # 保存图片
            img_path = os.path.join(output_folder, f"{pdf_name}_page_{page_num + 1}.png")
            pix.save(img_path)
            image_files.append(img_path)
            
            print(f"已保存: {img_path}")
            
        except Exception as e:
            print(f"转换第 {page_num + 1} 页时出错: {e}")
    
    # 完成后关闭PDF文档
    pdf_document.close()
    
    print(f"\n转换完成！共转换了 {total_pages} 页。")
    
    return image_files