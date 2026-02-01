import os
import fitz  # PyMuPDF
from PIL import Image
import argparse

def pdf_to_images(pdf_path, output_folder, dpi=300):
    """
    将PDF转换为图片
    
    参数:
        pdf_path: PDF文件路径
        output_folder: 输出图片的文件夹
        dpi: 图片分辨率，默认300
    """
    # 确保输出文件夹存在
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    # 打开PDF文件
    pdf_document = fitz.open(pdf_path)
    
    # 获取PDF文件名（不含扩展名）
    pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
    
    # 逐页转换
    for page_num in range(len(pdf_document)):
        page = pdf_document.load_page(page_num)
        
        # 设置缩放比例以获得高分辨率
        zoom = dpi / 72  # 72是默认的DPI
        mat = fitz.Matrix(zoom, zoom)
        
        # 渲染页面为图片
        pix = page.get_pixmap(matrix=mat, alpha=False)
        
        # 保存图片
        img_path = os.path.join(output_folder, f"{pdf_name}_page_{page_num + 1}.png")
        pix.save(img_path)
        
        print(f"已保存: {img_path}")
    print(f"\n转换完成！共转换了 {len(pdf_document)} 页。")
    pdf_document.close()
    
    print(f"图片保存在: {os.path.abspath(output_folder)}")

def pdf_to_images_pil(pdf_path, output_folder, format='PNG', dpi=300):
    """
    使用PIL（需要pdf2image库）转换PDF为图片
    安装: pip install pdf2image pillow
    """
    try:
        from pdf2image import convert_from_path
    except ImportError:
        print("请先安装 pdf2image: pip install pdf2image")
        return
    
    # 确保输出文件夹存在
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    # 获取PDF文件名（不含扩展名）
    pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
    
    # 转换PDF为图片列表
    images = convert_from_path(pdf_path, dpi=dpi)
    
    # 保存每张图片
    for i, image in enumerate(images):
        img_path = os.path.join(output_folder, f"{pdf_name}_page_{i + 1}.{format.lower()}")
        image.save(img_path, format.upper())
        print(f"已保存: {img_path}")
    
    print(f"\n转换完成！共转换了 {len(images)} 页。")
    print(f"图片保存在: {os.path.abspath(output_folder)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='将PDF转换为图片')
    parser.add_argument('pdf_path', help='PDF文件路径')
    parser.add_argument('-o', '--output', default='output_images', help='输出文件夹路径')
    parser.add_argument('--dpi', type=int, default=300, help='图片分辨率（默认300）')
    parser.add_argument('--method', choices=['pymupdf', 'pdf2image'], default='pymupdf', help='转换方法')
    parser.add_argument('--format', default='PNG', choices=['PNG', 'JPEG', 'JPG', 'TIFF'], help='输出图片格式')
    
    args = parser.parse_args()
    
    if args.method == 'pymupdf':
        pdf_to_images(args.pdf_path, args.output, args.dpi)
    else:
        pdf_to_images_pil(args.pdf_path, args.output, args.format, args.dpi)