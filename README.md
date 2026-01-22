# preprocessV4

## 格式转换

目前支持的格式有：
1. docx、doc、wps、pptx和odt等office系列文件。使用linux下的libreoffice实现格式转换,需要装完整版，否则无法处理部分格式文件
2. txt格式。基于reportlab实现
3. jpg，jpeg和png。基于img2pdf实现
4. md。基于pypandoc实现，需要下载'--pdf-engine=xelatex'作为渲染引擎
5. ofd。基于github项目easyofd实现。https://github.com/renoyuan/easyofd。这里注册字体用的1宋体文件在项目文件夹下，但注册字体时的路径是硬编码，后续需要修改
6. ceb。通过wine运行windows平台的ceb2pdf实现

## 多级标题处理
### 注意事项
该程序直接将输入写死了，在使用时注意修改文件为自己目录中对应的文件地址


#### LLM API 配置

    "LLM_API_KEY": "***",
    "LLM_BASE_URL": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "LLM_MODEL": "qwen3-14b",
    # 文件路径配置
    "INPUT_JSON_PATH": "xxxx.json",
    "OUTPUT_JSON_PATH": "processed_with_levels.json",

### 代码大致原理
 原来的逻辑是直接将所有文本抽离分割成文本块，然后喂给大模型让其识别标题。但是MinerU更新之后识别标题的能力增强了很多，在输出的中间json里直接包含了标题字段，而原来的方法可能会有标题错漏的风险  
 当前代码逻辑是以MinerU输出的中间json为基准，识别其中包含的所有title字段的内容，并将原文本抽离作为上下文一并交给大模型进行标题的识别
    让大模型有一个上下文参考从而提高准确性并降低误检率

## preprocessv4.1

* 增加MinerU配置文件，提升运行速度
* 用户界面提供VLM和pipeline两种处理方式
* 优化标题处理、输出新增纯标题的md文件
* json的标题字段中增加父子节点
* 优化表格处理
* 并发处理图表信息
* 返回json、标题markdown和minerU的版面检测pdf

## mineruv4.2

* 在系统中启动一个mineru的fastapi服务，在preprocess系统中调用该服务，这样mineru的模型权重只在第一次加载，后面会常驻在内存中
* 为了能让mineru的api服务输出layout文件，必须在mineru的源代码中将fastapi.py的f_draw_layout_bbox改为True（原始代码中是硬编码为False的），因此启动容器后也得去做修改
* 简化mineru的json输出，移除page层级
* 针对红头文件做了标题处理优化
* 优化了图表的处理逻辑，图片支持类别、描述和html，表格支持html、kv和描述，用户可根据需要任意选取输出字段
* 当用户选取了表格的html字段后，会将表格的html转为excel文件并返回，便于可视化判断表格信息解析的准确性
* 将文档中的图片和表格上传到一个minio中，minio的路径等信息也在config.yaml中配置,minio中的文件夹名是开始处理文件的时间+文件名

**为确保程序正常运行，output_path_temp: ./data/temp必须存在，例如data/temp,并且要保证这个文件夹为空，不能放入任何文件**
