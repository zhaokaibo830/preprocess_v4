# 多级标题处理
## 注意事项
该程序直接将输入写死了，在使用时注意修改文件为自己目录中对应的文件地址


### LLM API 配置

    "LLM_API_KEY": "sk-92d983e317d24d2da8ef19ddd2359008",
    "LLM_BASE_URL": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "LLM_MODEL": "qwen3-14b",
    # 文件路径配置
    "INPUT_JSON_PATH": "xxxx.json",
    "OUTPUT_JSON_PATH": "processed_with_levels.json",

## 代码大致原理
 原来的逻辑是直接将所有文本抽离分割成文本块，然后喂给大模型让其识别标题。但是MinerU更新之后识别标题的能力增强了很多，在输出的中间json里直接包含了标题字段，而原来的方法可能会有标题错漏的风险  
 当前代码逻辑是以MinerU输出的中间json为基准，识别其中包含的所有title字段的内容，并将原文本抽离作为上下文一并交给大模型进行标题的识别
    让大模型有一个上下文参考从而提高准确性并降低误检率