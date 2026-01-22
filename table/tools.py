import json
import io
  # 需要安装: pip install Pillow
from openai import OpenAI
from openai import APIConnectionError, APIError, RateLimitError
    
def table_extract(table_html: str, config, api_key: str, base_url: str, model_name: str) -> dict:
    # ==========================================
    # 第一步：从html表格中提取数据
    # ========================================== 
    def safe_json_parse(json_str):
        try:
            if "json"  in json_str:
                json_str=json_str.replace("json","")
            if "'''" in json_str:
                json_str = json_str.replace("'''", "")
            if "\n" in json_str:
                json_str=json_str.replace("\n","")
            #print("--------------------------------")
            #print(json_str)
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
            return json_str
    # ==========================================
    # 第二步：创建调用API的函数
    # ========================================== 
    def make_api_call(client, table_content, prompt, model):
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": table_content + "\n" + prompt},
                ],
                extra_body={"enable_thinking": False}
            )
            return completion.choices[0].message.content
        except APIConnectionError as e:
            print(f"处理表格时API连接错误: {e}")
            return {"error": "API连接失败", "details": str(e)}
        except RateLimitError as e:
            print(f"处理表格时API速率限制错误: {e}")
            return {"error": "处理表格时API请求超过速率限制", "details": str(e)}
        except APIError as e:
            print(f"处理表格时API错误: {e}")
            return {"error": "处理表格时API请求失败", "details": str(e)}
        except Exception as e:
            print(f"处理表格时未知错误: {e}")
            return {"error": "处理表格时未知错误", "details": str(e)}

    # 初始化客户端
    try:
        client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )
    except Exception as e:
        print(f"处理表格时OpenAI客户端初始化失败: {e}")
        return {
            "key_value": {"error": "处理表格时客户端初始化失败", "details": str(e)},
            "description": {"error": "处理表格时客户端初始化失败", "details": str(e)}
        }
    # ==========================================
    # 第三步：构建prompt
    # ========================================== 
    prompt_kv= """
    给定内容是一个以HTML格式呈现的表格，请详细分析该表格的内容，并将其转化为键值对（key-value）的形式，最终输出为JSON格式。请确保不遗漏HTML中的任何一个单元格数据，每一个键（key）或值（value）应当对应表格中的某个单元格，不能将多个单元格的数据拼接成一个值。示例如下：

输入的HTML表格内容如下：
<table><tr><td rowspan=2 colspan=1>序号</td><td rowspan=1 colspan=3>学生信息</td></tr><tr><td rowspan=1 colspan=1>姓名</td><td rowspan=1 colspan=1>年龄</td><td rowspan=1 colspan=1>家庭地址</td></tr><tr><td rowspan=1 colspan=1>1</td><td rowspan=1 colspan=1>张三</td><td rowspan=1 colspan=1>23</td><td rowspan=1 colspan=1>北京</td></tr><tr><td rowspan=1 colspan=1>2</td><td rowspan=1 colspan=1>李四</td><td rowspan=1 colspan=1>12</td><td rowspan=1 colspan=1>上海</td></tr></table>
以上HTML表格内容转化为JSON格式。最终输出的JSON格式如下：
[{"序号":"1","学生信息":{"姓名":"张三","年龄":"23","家庭地址":"北京"}},{"序号":"2","学生信息":{"姓名":"李四","年龄":"12","家庭地址":"上海"}}]

要避免出现同一个dict里面出现相同的key，例如如下类似例子要避免出现：
[{"时段/h":"1","频率/Hz":"45.7857","时段/h":"17","频率/Hz":"46.9250"},{"时段/h":"10","频率/Hz":"47.4718","时段/h":"18","频率/Hz":"46.9588"}]

请按照这个格式输出JSON，不需要其他多余的解释，HTML中的每一个数据都要体现出来不能遗漏,每一个键（key）或值（value）应当对应表格中的某个单元格，不能将多个单元格的数据拼接成一个值,相同的key不能出现在同一个dict里面且确保输出的JSON是有效且可以解析的。

    """
    prompt_desc= (
        "你是一个数据分析技术员，请仔细分析该以HTML格式呈现的表格的内容，分析并描述该表格传达的信息，需注意以下要点\n"
        "1. 用简明的语言说明这是一张什么什么表格，如‘这是一张xx公司的员工工资表’，‘这是一张学生成绩表’\n"
        "2. 如果表格内容以数据为主，需要分析表格中如最大值，最小值等能反映数据特点的信息。\n"
        "3. 如果表格内容中涉及文字信息，则应对文字信息和数据进行简要描述。\n"
    )

    # 调用API获取键值对结果
    def kv_api_call():
        return make_api_call(client, table_html, prompt_kv, model_name)
    
    # 调用API获取描述结果
    def desc_api_call():
        return make_api_call(client, table_html, prompt_desc, model_name)

    
    # ==========================================
    # 第四步：创建if分支识别传入config
    # ==========================================   
    result = {}
    result["type"] = "table"
    #判断config中包含的功能，更新result并返回
    if "kv"in config and "desc"and "html" in config:
        #判断kv中的功能，更新result并返回
        keyvalue_result=kv_api_call()
        if isinstance(keyvalue_result, dict) and "error" in keyvalue_result:
            result["key_value"] = keyvalue_result
        else:
            result["key_value"] = safe_json_parse(keyvalue_result)
        #判断desc中的功能，更新result并返回
        result["description"]=desc_api_call()
        result["table_html"]=table_html
        return result
    elif "kv"in config and "desc" in config:
         #判断kv中的功能，更新result并返回
        keyvalue_result=kv_api_call()
        if isinstance(keyvalue_result, dict) and "error" in keyvalue_result:
            result["key_value"] = keyvalue_result
        else:
            result["key_value"] = safe_json_parse(keyvalue_result)
        #判断desc中的功能，更新result并返回
        result["description"]=desc_api_call()
        return result
    elif "desc"in config and "html" in config:
        description=desc_api_call()
        result["description"]=description
        result["table_html"]=table_html
        return result
    elif "kv"in config and "html" in config:
         #判断kv中的功能，更新result并返回
        keyvalue_result=kv_api_call()
        if isinstance(keyvalue_result, dict) and "error" in keyvalue_result:
            result["key_value"] = keyvalue_result
        else:
            result["key_value"] = safe_json_parse(keyvalue_result)
        result["table_html"]=table_html
        return result
    elif "kv"in config:
         #判断kv中的功能，更新result并返回
        keyvalue_result=kv_api_call()
        if isinstance(keyvalue_result, dict) and "error" in keyvalue_result:
            result["key_value"] = keyvalue_result
        else:
            result["key_value"] = safe_json_parse(keyvalue_result)
        return result
    elif "desc"in config:
        description=desc_api_call()
        result["description"]=description
        return result
    elif "html"in config:
        result["table_html"]=table_html
        return result


if __name__ == "__main__":
    # 配置参数
    API_KEY = "sk-46af479b8d7b4a1489ff47b084831a0c"  # 替换为你的真实 Key
    BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    MODEL = "qwen3-vl-8b-instruct"
    table_html = "<table><tr><th>岗位名称</th><th>占比</th></tr><tr><td>监理员</td><td>41%</td></tr><tr><td>资料员</td><td>13%</td></tr><tr><td>总监理工程师</td><td>7%</td></tr><tr><td>总监代表</td><td>8%</td></tr><tr><td>专业监理工程师</td><td>18%</td></tr><tr><td>安全监理工程师</td><td>13%</td></tr></table>"
    config='desc'  # 可选 'kv', 'desc', 'html' 或它们的组合，如 'kv_desc_html'

    # 运行函数
    result = table_extract(table_html, config, API_KEY, BASE_URL, MODEL)
    print(result)
  
  
