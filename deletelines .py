# deletelines.py
import cv2
import numpy as np
import os
import shutil
from typing import List, Dict, Any

class LineDetector:
    """线条检测器 - 检测长度超过图片一半的线条（不区分颜色）"""
    
    def __init__(self, 
                 min_line_area=100,
                 min_length_ratio=0.5,
                 min_aspect_ratio=5,
                 line_width_range=(2, 20)):
        
        self.min_line_area = min_line_area
        self.min_length_ratio = min_length_ratio
        self.min_aspect_ratio = min_aspect_ratio
        self.line_width_range = line_width_range
    
    def detect_lines(self, image_path):
        """检测图片中是否有长度超过一半的线条"""
        # 读取图片
        img = cv2.imread(image_path)
        if img is None:
            return {
                "image_path": image_path,
                "error": "无法读取图片",
                "has_lines": False,
                "image_width": 0,
                "image_height": 0
            }
        
        # 获取图片尺寸
        height, width = img.shape[:2]
        image_length = max(height, width)
        min_required_length = image_length * self.min_length_ratio
        
        # 转换为灰度图
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 使用Otsu自动阈值
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # 形态学操作
        kernel_open = np.ones((2, 2), np.uint8)
        cleaned = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_open)
        
        kernel_close = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel_close)
        
        # 轮廓检测
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < 300:
                continue
                
            x, y, w, h = cv2.boundingRect(contour)
            contour_length = max(w, h)
            
            if min(w, h) > 0:
                aspect_ratio = max(w, h) / min(w, h)
            else:
                aspect_ratio = 0
            
            line_width = min(w, h)
            
            if (contour_length >= min_required_length and
                aspect_ratio >= self.min_aspect_ratio and
                self.line_width_range[0] <= line_width <= self.line_width_range[1]):
                
                return {
                    "image_path": image_path,
                    "image_width": width,
                    "image_height": height,
                    "has_lines": True,
                    "line_info": {
                        "length": contour_length,
                        "width": line_width,
                        "aspect_ratio": aspect_ratio,
                        "area": area
                    }
                }
        
        return {
            "image_path": image_path,
            "image_width": width,
            "image_height": height,
            "has_lines": False
        }


def process_images_in_memory(folder_path: str) -> List[str]:
    """
    处理文件夹中的图片，删除没有线条的图片
    
    Args:
        folder_path: 图片文件夹路径
    
    Returns:
        保留的图片文件路径列表
    """
    if not os.path.exists(folder_path):
        print(f"错误：文件夹不存在 - {folder_path}")
        return []
    
    # 支持的图片格式
    image_extensions = ['.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif']
    
    # 获取所有图片文件
    image_files = []
    for file in os.listdir(folder_path):
        if any(file.lower().endswith(ext) for ext in image_extensions):
            image_files.append(os.path.join(folder_path, file))
    
    if not image_files:
        return []
    
    detector = LineDetector()
    kept_images = []
    deleted_count = 0
    
    print(f"开始检测 {len(image_files)} 张图片的线条...")
    
    for image_path in image_files:
        result = detector.detect_lines(image_path)
        
        if result.get('has_lines', False):
            kept_images.append(image_path)
            print(f"  ✓ 保留: {os.path.basename(image_path)} (包含线条)")
        else:
            # 删除没有线条的图片
            try:
                os.remove(image_path)
                deleted_count += 1
                print(f"  ✗ 删除: {os.path.basename(image_path)} (无线条)")
            except Exception as e:
                print(f"    删除失败: {e}")
    
    print(f"\n线条过滤完成: 保留 {len(kept_images)} 张, 删除 {deleted_count} 张")
    
    return kept_images