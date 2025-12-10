from pathlib import Path
import subprocess
import sys
import os
import pypandoc
import img2pdf
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
#sys.path.append('/data/preprocessv4/format/')
sys.path.insert(0, os.path.dirname(__file__))
from EasyOFD.easyofd.ofd import OFD
import base64

def register_font(name, path):
    if os.path.exists(path):
        pdfmetrics.registerFont(TTFont(name, path))
        print(f"registered font {name} -> {path}")
    else:
        print(f"font file not found: {path}")


def office_to_pdf(
        src: str | Path,
        dst_dir: str | Path | None = None,
        *,
        timeout: int = 60
) -> Path:
    
    src = Path(src).expanduser().resolve()
    if not src.exists():
        raise FileNotFoundError(src)
    #dst_dir = Path(dst_dir or src.parent).expanduser().resolve()
    #dst_dir.mkdir(parents=True, exist_ok=True)
    dst_dir=src.parent
    soffice = {
        "win32": r"C:\Program Files\LibreOffice\program\soffice.exe",
        "darwin": "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    }.get(sys.platform, "soffice")  # Linux һ������ PATH

    cmd = [
        "xvfb-run",
        "-a",
        soffice,
        "--headless",              
        "--convert-to", "pdf",      
        "--outdir", str(dst_dir),  
        "--norestore", 
        str(src)
    ]

    try:
        subprocess.run(cmd, check=True, timeout=timeout, capture_output=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"LibreOffice转换失败: {e.stderr.decode(errors='ignore')}") from e

    return (dst_dir / src.stem).with_suffix(".pdf")

def odt_to_pdf(src: str | Path, dst_dir: str | Path | None = None) -> Path:
    src = Path(src).expanduser().resolve()
    if src.suffix.lower() != ".odt":
        raise ValueError("���ṩ .odt �ļ�")

    dst_dir = Path(dst_dir or src.parent).expanduser().resolve()
    soffice = {
        "win32": r"C:\Program Files\LibreOffice\program\soffice.exe",
        "darwin": "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    }.get(sys.platform, "soffice")

    cmd = [
        "xvfb-run",
        "-a",
        soffice,
        "--headless",              
        "--convert-to", "pdf",      
        "--outdir", str(dst_dir),  
        "--norestore", 
        str(src)
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"LibreOffice转换失败: {e.stderr.decode(errors='ignore')}") from e
    return (dst_dir / src.stem).with_suffix(".pdf")

def md_2_pdf(src:str | Path,dst_dir: str| Path | None=None)-> Path:
    src=Path(src).expanduser().resolve()
    if src.suffix.lower()!='.md':
        print("输入文件格式错误")
    dst_dir = src.parent
    input_file=src
    output_file= (dst_dir/src.stem).with_suffix(".pdf")
    pypandoc.convert_file(
        input_file,
        'pdf',
        outputfile=output_file,
        extra_args=[
            '--standalone',
            '--pdf-engine=xelatex'
        ]
    )
    return output_file

def ofd_2_pdf(src: str |Path,dst_dir : str | Path | None=None)->Path:
    #ofd自身问题，转换到pdf后发票的盖章无法保留
    src=Path(src).expanduser().resolve()
    if src.suffix.lower()!='.ofd':
        print("输入格式错误")
    file_prefix = os.path.splitext(os.path.split(src)[1])[0]
    with open(src,"rb") as f:
        ofdb64 = str(base64.b64encode(f.read()), "utf-8")
    ofd = OFD()  
    ofd.read(ofdb64, save_xml=True, xml_name=f"{file_prefix}_xml")
    pdf_bytes = ofd.to_pdf()
    dst_dir=src.parent                                                             
    output_file=(dst_dir/src.stem).with_suffix(".pdf")
    with open(output_file, "wb") as f:
        f.write(pdf_bytes)
    return output_file

def ceb_2_pdf(src: str | Path,dst_dir : str | Path | None=None)->Path:
    src=Path(src).expanduser().resolve()
    if src.suffix.lower()!='.ceb':
        print("输入格式错误")
    dst_dir=src.parent    
    #dst_dir=(Path)(dst_dir)
    pdf_file=(dst_dir/src.stem).with_suffix(".pdf")
    ceb_parent_path=os.path.dirname(__file__)
    ceb_path=Path(ceb_parent_path)/'ceb2pdf-master'/'64'/'ceb2pdf.exe'
    cmd=["wine",str(ceb_path),src,pdf_file]
    result = subprocess.run(cmd, capture_output=True, text=True,encoding='gbk')
    if result.returncode != 0:
        # 把 wine 报错抛出去，方便定位
        raise RuntimeError(f"ceb2pdf 转换失败: {result.stderr}")
    if not pdf_file.exists():
        raise RuntimeError("转换后 PDF 文件未生成")

    #print("��׼�����", result.stdout)
    #print("���������", result.stderr)
    #print("�˳��룺", result.returncode)
    return pdf_file


def image_2_pdf(src: str |Path,dst_dir : str | Path | None=None)->Path:
    """
    Pillow�ȹ��߿���֧�ְ�jpg,jpeg,pngת����pdf
    """
    src=Path(src).expanduser().resolve()
    format=src.suffix.lower()
    print("format")
    print(format)
    #if format!=".png" or format!=".jpg" or format!=".jpeg":
    #    print("ͼƬ��ʽ����ȷ")
    dst_dir=src.parent
    output_file=(dst_dir/src.stem).with_suffix(".pdf")
    with open(output_file, "wb") as f:
        f.write(img2pdf.convert(str(src)))
    return output_file

def txt_2_pdf(src: str |Path,dst_dir : str | Path | None=None)->Path:
    
    src=Path(src).expanduser().resolve()
    if src.suffix.lower()!='.txt':
        print("���ṩtxt�ļ�")
    dst_dir=src.parent
    output_file= (dst_dir/src.stem).with_suffix(".pdf")
    c = canvas.Canvas(str(output_file), pagesize=A4)
    width, height = A4
    y = height - 50

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

    with open(src, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                y -= 18
                continue
            c.setFont("STSong-Light", 12)
            c.drawString(50, y, line)
            y -= 18
            if y < 50:
                c.showPage()
                c.setFont("STSong-Light", 12)
                y = height - 50

    c.save()
    return output_file



def format(input_path:Path):
    suffix = Path(str(input_path)).suffix.lower()     
    print("输入文件 :", input_path)
    print("文件类型 :", suffix[1:])
    suffix_wo_point=suffix[1:]
    #print("suffix:  ",suffix_wo_point)
    options={"docx":0, "doc":1,"wps":2,"odt":3,"pptx":4,"ppt":5,"ofd":6,"md":7,"ceb":8,"jpg":9,"jpeg":10,"png":11,"txt":12}
    option=options[suffix_wo_point]
    print("option:",option)
    if option==0 or option==1 or option==2 or option==4 or option==5:
        pdf = office_to_pdf(input_path, None)
        print("输出PDF:", pdf)
    elif option==3:
        pdf = odt_to_pdf(input_path,  None)
        print("输出PDF:", pdf)
    elif option==6:
        pdf=ofd_2_pdf(input_path,None)
        print("输出 PDF:", pdf)
    elif option==7:
        pdf=md_2_pdf(input_path, None)
        print("输出 PDF:", pdf)
    elif option==8:
        pdf=ceb_2_pdf(input_path, None)
        print("输出PDF:", pdf)
    elif option==9 or option==10 or option==11:
        pdf=image_2_pdf(input_path,  None)
        print("输出PDF:", pdf)
    elif option==12:
        pdf=txt_2_pdf(input_path,None)
        print("输出PDF:", pdf)  
    pdf=Path(pdf).resolve()
    return pdf
