# model_outputjson.py
import os
import base64
import json
import re
from typing import Dict, List, Any, Optional

class ImageTextExtractor:
    def __init__(self, config: Optional[Dict] = None, client: Any = None, model_name: str = "qwen-vl-plus"):
        """
        初始化提取器
        
        Args:
            config: 配置字典（可选）
            client: 模型客户端（包含连接信息）
            model_name: 要使用的模型名称，默认 "qwen-vl-plus"
        """
        self.client = client
        self.model_name = model_name  # 保存模型名称
        self.config = config or {}
        
        print(f"初始化 ImageTextExtractor，使用模型: {self.model_name}")
    
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

            # 构建消息
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
            
            print(f"  调用模型 {self.model_name} 分析图片...")
            
            # 使用传入的client和model_name调用模型
            response = self.client.chat.completions.create(
                model=self.model_name,  # 使用保存的模型名称
                messages=messages,
                max_tokens=2000,
                temperature=0.1  # 降低随机性，使输出更稳定
            )
            
            result = response.choices[0].message.content.strip()
            print(f"  分析完成，结果长度: {len(result)}")
            return result
                
        except Exception as e:
            print(f"分析图片 {image_path} 时出错: {str(e)}")
            return f"错误: {str(e)}"
    
    def parse_numbered_text(self, text: str) -> List[str]:
        """解析带有序号的文本，返回文本列表"""
        if not text or text.startswith('错误:'):
            return []
        
        items = []
        lines = text.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 匹配数字序号开头的行
            match = re.match(r'^\s*(\d+)[\.、:：]?\s*(.*)', line)
            if match:
                items.append(match.group(2).strip())
            else:
                # 如果没有序号，整行作为一个项目
                items.append(line)
        
        return items
    
    def classify_single_item(self, text: str) -> str:
        """对单条文本内容进行类别判断"""
        try:
            prompt = f"""请分析以下文本片段，判断其属于什么类型：

文本内容："{text}"

只能从以下类型中选择最合适的一个：
1. 版头（红线页面的图片都选版头）
2. 版记（黑线页面的图片都选版记）

请只返回类型名称（"版头"或"版记"），不要添加任何解释说明。

类型："""
            
            messages = [
                {"role": "user", "content": prompt}
            ]
            
            print(f"    分类文本片段，使用模型 {self.model_name}...")
            
            # 使用保存的模型名称
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=50,
                temperature=0.1
            )
            
            item_type = response.choices[0].message.content.strip()
            # 清理可能的额外字符
            item_type = item_type.replace('类型：', '').replace('类型:', '').replace('"', '').strip()
            
            # 确保返回的是"版头"或"版记"
            if "版头" in item_type:
                return "版头"
            elif "版记" in item_type:
                return "版记"
            else:
                print(f"    无法识别的类型: {item_type}，默认为其他内容")
                return "其他内容"
                
        except Exception as e:
            print(f"分类文本片段时出错: {str(e)}")
            return "其他内容"
    
    def process_images_in_memory(self, folder_path: str, image_files: List[str]) -> Dict:
        """
        处理图片并返回提取的JSON数据
        
        Args:
            folder_path: 图片文件夹路径
            image_files: 要处理的图片文件列表
        
        Returns:
            提取的JSON数据
        """
        print(f"\n开始处理 {len(image_files)} 张图片，使用模型: {self.model_name}")
        
        all_results = []
        successful_count = 0
        total_items = 0
        
        for idx, image_path in enumerate(image_files, 1):
            print(f"\n处理图片 [{idx}/{len(image_files)}]: {os.path.basename(image_path)}")
            
            # 提取文字
            extracted_text = self.analyze_image(image_path)
            
            # 分类
            classified_items = []
            if (not extracted_text.startswith('错误:') and 
                extracted_text != "未提取到文字内容" and
                extracted_text.strip() != ""):
                
                print(f"  解析文本内容...")
                text_items = self.parse_numbered_text(extracted_text)
                print(f"  解析出 {len(text_items)} 个文本片段")
                
                for i, item in enumerate(text_items, 1):
                    print(f"    片段 {i}: {item[:50]}..." if len(item) > 50 else f"    片段 {i}: {item}")
                    item_type = self.classify_single_item(item)
                    classified_items.append({
                        "content": item,
                        "type": item_type
                    })
                
                if classified_items:
                    successful_count += 1
                    total_items += len(classified_items)
            
            result = {
                "image_name": os.path.basename(image_path),
                "extracted_text": extracted_text,
                "classified_items": classified_items
            }
            all_results.append(result)
        
        # 构建JSON数据
        json_data = {
            "metadata": {
                "model_used": self.model_name,
                "total_images_processed": len(all_results),
                "successful_extractions": successful_count,
                "total_text_items": total_items
            },
            "results": all_results
        }
        
        print(f"\n提取完成:")
        print(f"  - 使用模型: {self.model_name}")
        print(f"  - 成功提取: {successful_count}/{len(all_results)} 张图片")
        print(f"  - 总文本项: {total_items}")
        
        return json_data


# 便捷函数：快速创建提取器
def create_extractor(client: Any, model_name: str = "qwen-vl-plus") -> ImageTextExtractor:
    """
    快速创建ImageTextExtractor实例
    
    Args:
        client: OpenAI客户端
        model_name: 模型名称
    
    Returns:
        ImageTextExtractor实例
    """
    return ImageTextExtractor(client=client, model_name=model_name)