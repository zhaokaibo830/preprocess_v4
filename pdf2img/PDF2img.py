import fitz  # 导入 pymupdf

def convert_pdf_to_img(pdf_path, output_folder):
    # 打开 PDF 文件
    doc = fitz.open(pdf_path)
    
    for page_index in range(len(doc)):
        page = doc[page_index]
        
        # 设置缩放倍数，dpi=300 对应 matrix = (300/72, 300/72)
        # 72 是 PDF 的默认 DPI
        zoom = 2  # 缩放 2 倍，通常足够清晰
        mat = fitz.Matrix(zoom, zoom)
        
        # 渲染为图片
        pix = page.get_pixmap(matrix=mat, alpha=False)
        
        # 保存
        pix.save(f"{output_folder}/page_{page_index}.png")
    
    doc.close()

if __name__=="__main__":
    convert_pdf_to_img('../data/doc/demo0.pdf','./test')