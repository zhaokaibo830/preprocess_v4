import os
import base64
import glob
import json
import re
import requests
from typing import Dict, List


class ImageTextExtractor:
    def __init__(self, config: Dict):
        self.api_key = config["LLM_API_KEY"]
        self.base_url = config["LLM_BASE_URL"]
        self.model = config["LLM_MODEL"]
        self.input_path = config["INPUT_PATH"]
        self.output_path = config["OUTPUT_PATH"]
        
        # 创建输出目录
        #os.makedirs(self.output_path, exist_ok=True)
        
        # 设置请求头
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
    def build_error_json(self, status: str, error_msg: str) -> Dict:
        """
        统一构建错误或跳过状态下的结果字典。
        status: "failed" (触发错误的那个图片) 或 "skipped" (熔断后被跳过的图片)
        """
        return {
            "image_name": "N/A",  # 或者在调用处传入文件名
            "extracted_text": f"错误: [{status}] {error_msg}",
            "classified_items": []  # 确保即便失败，这个列表也存在，防止下游遍历报错
        }
    def encode_image_to_base64(self, image_path: str) -> str:
        """将图片编码为base64字符串"""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def analyze_image(self, image_path: str) -> str:
        """使用多模态模型分析图片并提取文本"""
        try:
            # 读取并编码图片
            base64_image = self.encode_image_to_base64(image_path)
            
            # 构建提示词
            prompt = """请严格按照以下步骤分析图片：

第一步：线条检测和区域定义：
1. 检查是否有红色水平线（红色、水平）
2. 检查是否有两条平行的黑色水平线（黑色、水平、平行）

第二步：精确提取规则：
情况A（有红色水平线时）：
  - 识别红色水平线的Y轴位置
  - 只提取红色水平线上方的文字（若用几个空格符隔开，则判定为不同的文字）
  - 不提取红色水平线本身或下方的任何文字

情况B（有两条黑色水平线时）：
  - 识别第一条黑线（上黑线）和第二条黑线（下黑线）的Y轴位置
  - 只提取**两条黑线之间**的文字
  - **不提取**第一条黑线上方或第二条黑线下方的文字

情况C（都没有时）：
  - 返回"未提取到文字内容"

第三步：文字格式：
- 如果有多段不同的文本（若用几个空格符隔开，则判定为不同的文字），用数字序号分开：1. 2. 3.
- 只返回提取到的文字，不要添加说明

重要限制：
1. 红线规则：严格只提取红线上方，红线本身和下方都忽略
2. 黑线规则：严格只提取两条黑线之间，黑线上方和下方都忽略
3. 确保准确性：仔细判断文字相对于线条的位置


现在请分析这张图片。"""

            # 构建请求数据
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ]
            
            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": 2000
            }
            
            # 发送请求
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=(5,60)
            )
            
            response.raise_for_status()
            result = response.json()
            
            # 提取响应内容
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"].strip()
            else:
                return "未提取到文字内容"
                
        except Exception as e:
            print(f"分析图片 {image_path} 时出错: {str(e)}")
            raise RuntimeError(f"OCR分析阶段失败: {str(e)}")
    
    def parse_numbered_text(self, text: str) -> List[str]:
        """解析带有序号的文本，返回文本列表"""
        # 使用正则表达式匹配数字序号开头的行
        pattern = r'^\s*\d+[\.、:：]?\s*(.*)$'
        
        lines = text.strip().split('\n')
        items = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # 尝试匹配序号
            match = re.match(r'^\s*(\d+)[\.、:：]?\s*(.*)', line)
            if match:
                items.append(match.group(2).strip())
            else:
                # 如果没有序号但是有内容，也加入
                items.append(line)
        
        return items
    
    def classify_single_item(self, text: str) -> str:
        """对单条文本内容进行类别判断"""
        try:
            # 构建分类提示词
            prompt = f"""请分析以下文本片段，判断其属于什么类型：

文本内容："{text}"

只能以下类型中选择最合适的一个：
1. 发文机关标志
2. 密级和保密期限
3. 份号
4. 紧急程度
5. 成文日期
6. 抄送机关
7. 印发机关
8. 印发日期
9. 其他内容
10. 负责人签名

请只返回类型名称，不要添加任何文本内容，解释或说明。

类型："""
            
            messages = [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            
            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": 100
            }
            
            # 发送请求
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=(5, 30)
            )
            
            response.raise_for_status()
            result = response.json()
            
            # 提取类型
            if "choices" in result and len(result["choices"]) > 0:
                item_type = result["choices"][0]["message"]["content"].strip()
                # 清理可能的额外字符
                item_type = item_type.replace('类型：', '').replace('类型:', '').strip()
                return item_type
            else:
                return "其他内容"
                
        except Exception as e:
            print(f"分类文本片段时出错: {str(e)}")
            raise RuntimeError(f"文本分类阶段失败: {str(e)}")
    
    def classify_text_items(self, text_items: List[str]) -> List[Dict[str, str]]:
        """对多条文本内容进行批量类别判断"""
        if not text_items:
            return []
        
        # 如果只有1-3条，逐条分类
        if len(text_items) <= 3:
            classified_items = []
            for item in text_items:
                item_type = self.classify_single_item(item)
                classified_items.append({
                    "content": item,
                    "type": item_type
                })
            return classified_items
        
        # 如果有多条，批量分类
        try:
            # 构建批量分类提示词
            items_text = "\n".join([f"{i+1}. {item}" for i, item in enumerate(text_items)])
            
            prompt = f"""请分析以下文本片段，为每个片段判断其类型：

文本片段：
{items_text}

只能以下类型中选择最合适的类型：
1. 发文机关标志
2. 密级和保密期限
3. 份号
4. 紧急程度
5. 成文日期
6. 抄送机关
7. 印发机关
8. 印发日期
9. 其他内容
10. 负责人签名

请按以下格式返回结果：
1. 类型名称
2. 类型名称
...
n. 类型名称

只返回类型名称列表，不要添加任何文本内容，解释或说明。"""
            
            messages = [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            
            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": 300
            }
            
            # 发送请求
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=(20,180)
            )
            
            response.raise_for_status()
            result = response.json()
            
            # 提取类型列表
            if "choices" in result and len(result["choices"]) > 0:
                type_text = result["choices"][0]["message"]["content"].strip()
                
                # 解析类型列表
                type_lines = type_text.strip().split('\n')
                types = []
                
                for line in type_lines:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # 尝试提取类型名称
                    match = re.match(r'^\s*\d+[\.、:：]?\s*(.*)', line)
                    if match:
                        types.append(match.group(1).strip())
                    else:
                        types.append(line)
                
                # 确保类型数量与文本项数量一致
                if len(types) == len(text_items):
                    classified_items = []
                    for i in range(len(text_items)):
                        classified_items.append({
                            "content": text_items[i],
                            "type": types[i]
                        })
                    return classified_items
                else:
                    # 如果不匹配，回退到逐条分类
                    print(f"类型数量不匹配，回退到逐条分类")
                    return self._fallback_classify(text_items)
            else:
                return self._fallback_classify(text_items)
                
        except Exception as e:
            print(f"批量分类时出错: {str(e)}")
            return self._fallback_classify(text_items)
    
    def _fallback_classify(self, text_items: List[str]) -> List[Dict[str, str]]:
        """回退方法：逐条分类"""
        classified_items = []
        for item in text_items:
            item_type = self.classify_single_item(item)
            classified_items.append({
                "content": item,
                "type": item_type
            })
        return classified_items
    
    def process_single_image(self, image_path: str) -> Dict:
        """处理单张图片"""
        print(f"正在处理: {image_path}")
        
        # 提取文字
        extracted_text = self.analyze_image(image_path)
        
        # 初始化分类结果
        classified_items = []
        
        # 如果成功提取到文字，进行类别判断
        if (not extracted_text.startswith('错误:') and 
            extracted_text != "未提取到文字内容" and
            extracted_text.strip() != ""):
            
            print(f"  正在进行文本解析和分类...")
            
            # 解析带有序号的文本
            text_items = self.parse_numbered_text(extracted_text)
            
            # 进行批量分类
            classified_items = self.classify_text_items(text_items)
            
            # 显示分类结果
            for i, item in enumerate(classified_items, 1):
                print(f"  第{i}条: {item['content']} -> {item['type']}")
        
        # 构建结果
        result = {
            "image_name": os.path.basename(image_path),
            "extracted_text": extracted_text,
            "classified_items": classified_items
        }
        
        return result
    
    def save_results_to_json(self, results: List[Dict], filename: str = "extracted_texts.json"):
        """将结果保存为JSON文件（唯一的输出文件）"""
        output_file = self.output_path
        
        # 统计信息
        total_count = len(results)
        error_count = sum(1 for r in results if r['extracted_text'].startswith('错误:'))
        empty_count = sum(1 for r in results if r['extracted_text'] == "未提取到文字内容")
        success_count = sum(1 for r in results if r['classified_items'])
        
        # 类型统计
        type_count = {}
        total_items = 0
        successful_results = []
        
        for result in results:
            if result['classified_items']:
                successful_results.append(result)
                for item in result['classified_items']:
                    item_type = item['type']
                    type_count[item_type] = type_count.get(item_type, 0) + 1
                    total_items += 1
        
        # 构建完整的JSON数据结构
        json_data = {
            "metadata": {
                "total_images_processed": total_count,
                "successful_extractions": success_count,
                "no_content_images": empty_count,
                "error_images": error_count,
                "total_text_items": total_items,
                "type_statistics": type_count
            },
            "results": []
        }
        
        # 添加每个图片的结果
        for result in results:
            image_result = {
                "image_name": result['image_name'],
                "status": "success" if result['classified_items'] else (
                    "error" if result['extracted_text'].startswith('错误:') else "no_content"
                ),
                "extracted_text": result['extracted_text'],
                "items": result['classified_items']
            }
            json_data["results"].append(image_result)
        
        # 保存JSON文件
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        
        return output_file
    
    def process_all_images(self):
        """处理输入目录中的所有图片"""
        # 支持的图片格式
        image_extensions = ['*.png', '*.jpg', '*.jpeg', '*.bmp', '*.gif']
        image_files = []
        
        # 收集所有图片文件
        for ext in image_extensions:
            image_files.extend(glob.glob(os.path.join(self.input_path, ext)))
        
        if not image_files:
            print(f"在 {self.input_path} 中没有找到图片文件")
        
        print(f"找到 {len(image_files)} 张图片，开始处理...")
        
        all_results = []
        successful_results = []
        stop_processing = False
        final_error = None
        for image_file in image_files:
            if stop_processing:
            # 已经熔断，直接生成空结构
                all_results.append(self.build_error_json("skipped", final_error))
                continue
            try:
                result = self.process_single_image(image_file)
                all_results.append(result)
            except Exception as e:
                # 终于抓到了！
                stop_processing = True
                final_error = str(e)  # 记录具体的报错信息
                all_results.append(self.build_error_json("failed", final_error))
                print(f"检测到异常，启动熔断: {final_error}")
                continue
            # 检查是否成功提取并分类
            if result['classified_items']:
                successful_results.append(result)
                print(f"✓ 完成: {result['image_name']} - ✅ 成功提取并分类 ({len(result['classified_items'])}条)")
            elif result['extracted_text'].startswith('错误:'):
                print(f"✓ 完成: {result['image_name']} - ❌ 提取失败: {result['extracted_text']}")
            else:
                print(f"✓ 完成: {result['image_name']} - ⚠️ 不符合提取条件")
            
            print("-" * 50)
        
        # 只保存为JSON文件
        json_file = self.save_results_to_json(all_results)
        
        print(f"\n处理完成！")
        print(f"结果已保存到: {json_file}")
        
        # 显示统计信息
        total_count = len(all_results)
        error_count = sum(1 for r in all_results if r['extracted_text'].startswith('错误:'))
        empty_count = sum(1 for r in all_results if r['extracted_text'] == "未提取到文字内容")
        success_count = len(successful_results)
        
        print(f"\n处理摘要:")
        print(f"总处理图片数: {total_count}")
        print(f"成功提取并分类: {success_count}")
        print(f"不符合条件: {empty_count}")
        print(f"提取失败: {error_count}")
        
        # 类型统计（从JSON数据中读取）
        type_count = {}
        total_items = 0
        for result in successful_results:
            for item in result['classified_items']:
                item_type = item['type']
                type_count[item_type] = type_count.get(item_type, 0) + 1
                total_items += 1
        
        if type_count:
            print(f"\n内容类型统计:")
            for item_type, count in sorted(type_count.items(), key=lambda x: x[1], reverse=True):
                print(f"  {item_type}: {count}条")
        
        return all_results , final_error

def main():
    """主函数"""
    print("=" * 60)
    print("图片文字提取工具")
    print("功能：")
    print("1. 有红线 → 提取红线上方文字")
    print("2. 有两条黑线 → 提取两条黑线中间文字")
    print("3. 其他情况 → 不提取内容")
    print("4. 对提取的文字逐条进行分类")
    print("5. 结果只保存为JSON格式")
    print("=" * 60)
    
    # 初始化提取器
    extractor = ImageTextExtractor(CONFIG)
    
    # 处理所有图片
    results = extractor.process_all_images()

if __name__ == "__main__":
    main()