# preprocessV4

## 格式转换

目前支持的格式有：
1. docx、doc、wps、pptx和odt等office系列文件。使用linux下的libreoffice实现格式转换,需要装完整版，否则无法处理部分格式文件
2. txt格式。基于reportlab实现
3. jpg，jpeg和png。基于img2pdf实现
4. md。基于pypandoc实现，需要下载'--pdf-engine=xelatex'作为渲染引擎
5. ofd。基于github项目easyofd实现。https://github.com/renoyuan/easyofd。这里注册字体用的1宋体文件在项目文件夹下，但注册字体时的路径是硬编码，后续需要修改
6. ceb。通过wine运行windows平台的ceb2pdf实现

