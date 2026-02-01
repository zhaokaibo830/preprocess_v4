import cv2
import numpy as np
import os
import sys
import shutil

class LineDetector:
    """线条检测器 - 检测长度超过图片一半的线条（不区分颜色）"""
    
    def __init__(self, 
                 min_line_area=100,       # 最小线条面积阈值
                 min_length_ratio=0.5,    # 最小线条长度与图片长度的比例
                 min_aspect_ratio=5,      # 最小长宽比（线条的特征）
                 line_width_range=(2, 20)): # 线宽范围
        
        self.min_line_area = min_line_area
        self.min_length_ratio = min_length_ratio
        self.min_aspect_ratio = min_aspect_ratio
        self.line_width_range = line_width_range
    
    def detect_lines(self, image_path):
        """
        检测图片中是否有长度超过一半的线条（不区分颜色）
        
        Args:
            image_path: 图片文件路径
            
        Returns:
            dict: 检测结果
        """
        # 读取图片
        img = cv2.imread(image_path)
        if img is None:
            return {
                "image_path": image_path,
                "error": "无法读取图片",
                "has_lines": False,
                "image_width": 0,
                "image_height": 0,
                "min_required_length": 0
            }
        
        # 获取图片尺寸
        height, width = img.shape[:2]
        image_length = max(height, width)
        min_required_length = image_length * self.min_length_ratio
        
        # 转换为灰度图
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 使用Otsu自动阈值（适应不同亮度的图片）
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # 形态学操作：先开运算去除小噪点（小文字）
        kernel_open = np.ones((2, 2), np.uint8)
        cleaned = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_open)
        
        # 再闭运算连接可能的断线
        kernel_close = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel_close)
        
        # 如果像素太少，直接返回False
        if np.sum(mask) < self.min_line_area:
            return {
                "image_path": image_path,
                "image_width": width,
                "image_height": height,
                "image_length": image_length,
                "min_required_length": int(min_required_length),
                "has_lines": False
            }
        
        # 方法1：轮廓检测（主要方法）
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            area = cv2.contourArea(contour)
            
            # 跳过太小的轮廓（可能是小文字或噪点）
            if area < 300:
                continue
                
            # 获取轮廓的外接矩形
            x, y, w, h = cv2.boundingRect(contour)
            
            # 计算轮廓的长度（取较长边）
            contour_length = max(w, h)
            
            # 计算长宽比
            if min(w, h) > 0:
                aspect_ratio = max(w, h) / min(w, h)
            else:
                aspect_ratio = 0
            
            # 计算线宽
            line_width = min(w, h)
            
            # 判断是否为线条：
            # 1. 长度必须超过要求
            # 2. 长宽比要大（细长）
            # 3. 线宽要在合理范围内
            if (contour_length >= min_required_length and
                aspect_ratio >= self.min_aspect_ratio and
                self.line_width_range[0] <= line_width <= self.line_width_range[1]):
                
                # 进一步验证：通过形状特征排除文字
                # 计算轮廓的填充度
                rect_area = w * h
                if rect_area > 0:
                    solidity = area / rect_area
                else:
                    solidity = 0
                
                # 计算轮廓的紧凑性
                perimeter = cv2.arcLength(contour, True)
                if perimeter > 0:
                    compactness = 4 * np.pi * area / (perimeter * perimeter)
                else:
                    compactness = 0
                
                # 排除可能是文字的情况：
                # 文字通常面积较小、填充度较低、紧凑性较高
                is_likely_text = (
                    area < 1000 and           # 面积太小
                    solidity < 0.5 and        # 填充度低（笔画不连续）
                    compactness > 0.2         # 紧凑性较高
                )
                
                if not is_likely_text:
                    # 找到符合条件的线条
                    return {
                        "image_path": image_path,
                        "image_width": width,
                        "image_height": height,
                        "image_length": image_length,
                        "min_required_length": int(min_required_length),
                        "has_lines": True,
                        "line_info": {
                            "length": contour_length,
                            "width": line_width,
                            "aspect_ratio": aspect_ratio,
                            "area": area
                        }
                    }
        
        # 方法2：霍夫变换检测直线（备选方法）
        has_line_hough = self.detect_with_hough(img, min_required_length)
        
        if has_line_hough:
            return {
                "image_path": image_path,
                "image_width": width,
                "image_height": height,
                "image_length": image_length,
                "min_required_length": int(min_required_length),
                "has_lines": True,
                "line_info": {"method": "hough_transform"}
            }
        
        # 没有检测到符合条件的线条
        return {
            "image_path": image_path,
            "image_width": width,
            "image_height": height,
            "image_length": image_length,
            "min_required_length": int(min_required_length),
            "has_lines": False
        }
    
    def detect_with_hough(self, img, min_required_length):
        """使用霍夫变换检测直线"""
        # 转换为灰度
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 使用Canny边缘检测
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        
        # 使用霍夫变换检测直线
        lines = cv2.HoughLinesP(
            edges, 1, np.pi/180,
            threshold=30,
            minLineLength=min_required_length,
            maxLineGap=20
        )
        
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                line_length = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
                
                if line_length >= min_required_length:
                    # 检查线宽
                    line_width = self.estimate_line_thickness(edges, x1, y1, x2, y2)
                    if self.line_width_range[0] <= line_width <= self.line_width_range[1]:
                        return True
        
        return False
    
    def estimate_line_thickness(self, edges, x1, y1, x2, y2, search_distance=5):
        """估计线条的厚度"""
        # 计算线条角度
        dx = x2 - x1
        dy = y2 - y1
        length = np.sqrt(dx*dx + dy*dy)
        
        if length < 10:
            return 0
        
        # 归一化方向向量
        nx = dx / length
        ny = dy / length
        
        # 垂直方向向量
        vx = -ny
        vy = nx
        
        # 在线条路径上采样点检查厚度
        thickness_sum = 0
        sample_points = 10
        thickness_count = 0
        
        for i in range(sample_points + 1):
            t = i / sample_points
            px = int(x1 + dx * t)
            py = int(y1 + dy * t)
            
            if 0 <= px < edges.shape[1] and 0 <= py < edges.shape[0]:
                local_thickness = 0
                for d in range(-search_distance, search_distance + 1):
                    offset_x = int(px + vx * d)
                    offset_y = int(py + vy * d)
                    
                    if 0 <= offset_x < edges.shape[1] and 0 <= offset_y < edges.shape[0]:
                        if edges[offset_y, offset_x] > 0:
                            local_thickness += 1
                
                thickness_sum += local_thickness
                thickness_count += 1
        
        if thickness_count > 0:
            return thickness_sum / thickness_count
        return 0


# ====================== 主程序 ======================

def process_single_image(input_path, delete_if_no_lines=False):
    """处理单张图片"""
    if not os.path.exists(input_path):
        print(f"错误：文件不存在 - {input_path}")
        return
    
    detector = LineDetector(
        min_line_area=800,
        min_length_ratio=0.5,
        min_aspect_ratio=5,
        line_width_range=(2, 20)
    )
    
    result = detector.detect_lines(input_path)
    
    print(f"\n图片信息：")
    print(f"图片尺寸：{result['image_width']} x {result['image_height']}")
    print(f"图片长度（较长边）：{result['image_length']} 像素")
    print(f"要求的最小线条长度：{result['min_required_length']} 像素")
    
    print(f"\n检测结果（长度超过一半的线条）：")
    print(f"包含符合条件的线条：{'是' if result['has_lines'] else '否'}")
    
    if result.get('line_info'):
        print(f"\n线条信息：")
        for key, value in result['line_info'].items():
            print(f"  {key}: {value}")
    
    # 如果没检测到线条且设置了删除选项
    if delete_if_no_lines and not result['has_lines']:
        try:
            os.remove(input_path)
            print(f"\n⚠️ 已删除无线条图片：{os.path.basename(input_path)}")
        except Exception as e:
            print(f"\n❌ 删除文件失败：{e}")


def process_folder(input_folder, delete_no_lines=False, backup_folder=None):
    """
    处理文件夹中的所有图片
    
    Args:
        input_folder: 输入文件夹路径
        delete_no_lines: 是否删除无线条的图片
        backup_folder: 备份文件夹路径（可选）
    """
    if not os.path.exists(input_folder):
        print(f"错误：文件夹不存在 - {input_folder}")
        return
    
    # 支持的图片格式
    image_extensions = ['.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif']
    
    # 获取所有图片文件
    image_files = []
    for file in os.listdir(input_folder):
        if any(file.lower().endswith(ext) for ext in image_extensions):
            image_files.append(os.path.join(input_folder, file))
    
    if not image_files:
        print(f"在文件夹中未找到图片文件：{input_folder}")
        return
    
    print(f"找到 {len(image_files)} 个图片文件")
    
    # 创建备份文件夹（如果需要）
    if delete_no_lines and backup_folder:
        os.makedirs(backup_folder, exist_ok=True)
        print(f"备份文件夹：{backup_folder}")
    
    detector = LineDetector(
        min_line_area=800,
        min_length_ratio=0.5,
        min_aspect_ratio=5,
        line_width_range=(2, 20)
    )
    
    line_count = 0
    deleted_count = 0
    backed_up_count = 0
    
    print("\n开始检测长度超过图片一半的线条...")
    if delete_no_lines:
        print("⚠️ 注意：将删除没有线条的图片！")
    
    for i, image_path in enumerate(image_files, 1):
        print(f"\n[{i}/{len(image_files)}] 处理：{os.path.basename(image_path)}")
        
        result = detector.detect_lines(image_path)
        
        if result.get('error'):
            print(f"  错误：{result['error']}")
            continue
        
        # 打印图片信息
        print(f"  尺寸：{result['image_width']} x {result['image_height']}")
        print(f"  要求线长：≥ {result['min_required_length']} 像素")
        
        if result['has_lines']:
            line_count += 1
            print("  ✓ 包含长度超半的线条")
            if result.get('line_info'):
                info = result['line_info']
                if 'length' in info:
                    print(f"    线条长度：{info['length']:.0f} 像素，宽度：{info['width']:.1f} 像素")
        else:
            print("  ✗ 不包含长度超半的线条")
            
            # 删除无线条的图片
            if delete_no_lines:
                try:
                    # 如果需要备份，先复制到备份文件夹
                    if backup_folder:
                        backup_path = os.path.join(backup_folder, os.path.basename(image_path))
                        shutil.copy2(image_path, backup_path)
                        backed_up_count += 1
                        print(f"    已备份到：{backup_path}")
                    
                    # 删除原文件
                    os.remove(image_path)
                    deleted_count += 1
                    print(f"    ⚠️ 已删除该图片")
                except Exception as e:
                    print(f"    ❌ 删除失败：{e}")
    
    # 打印统计结果
    print("\n" + "="*60)
    print("检测完成！统计结果（长度超过图片一半的线条）：")
    print("="*60)
    print(f"总图片数：{len(image_files)}")
    print(f"包含超长线条的图片数：{line_count}")
    print(f"不含超长线条的图片数：{len(image_files) - line_count}")
    
    if delete_no_lines:
        print(f"\n清理结果：")
        print(f"已删除无线条图片数：{deleted_count}")
        if backup_folder:
            print(f"已备份图片数：{backed_up_count}")
            print(f"备份位置：{backup_folder}")
        
        # 检查剩余文件
        remaining_files = [f for f in os.listdir(input_folder) 
                          if any(f.lower().endswith(ext) for ext in image_extensions)]
        print(f"文件夹剩余图片数：{len(remaining_files)}")


def main():
    """主函数：处理命令行参数"""
    print("="*60)
    print("图片超长线条检测工具")
    print("功能：检测图片中长度超过图片一半的线条（不区分颜色）")
    print("      可选择删除无线条的图片")
    print("参数说明：长度指图片较长边的尺寸，线条长度需超过此值的一半")
    print("="*60)
    
    # 如果提供了命令行参数
    if len(sys.argv) > 1:
        input_path = sys.argv[1]
        # 检查是否包含删除选项
        delete_no_lines = len(sys.argv) > 2 and sys.argv[2].lower() in ['-d', '--delete', 'delete']
        backup_folder = None
        if len(sys.argv) > 3 and sys.argv[2].lower() in ['-b', '--backup']:
            backup_folder = sys.argv[3]
            delete_no_lines = True
    else:
        # 如果没有命令行参数，提示用户输入
        input_path = input("请输入图片路径或文件夹路径：").strip()
        
        # 询问是否删除无线条的图片
        delete_choice = input("是否删除没有线条的图片？(y/n, 默认n): ").strip().lower()
        delete_no_lines = delete_choice == 'y' or delete_choice == 'yes'
        
        # 如果需要备份
        backup_folder = None
        if delete_no_lines:
            backup_choice = input("是否备份要删除的图片？(y/n, 默认n): ").strip().lower()
            if backup_choice == 'y' or backup_choice == 'yes':
                backup_folder = input("请输入备份文件夹路径（默认：原文件夹_backup）: ").strip()
                if not backup_folder:
                    backup_folder = input_path + "_backup" if os.path.isfile(input_path) else os.path.join(input_path, "backup")
    
    # 去除可能的引号
    input_path = input_path.strip('"').strip("'")
    
    if not input_path:
        print("错误：未提供输入路径")
        return
    
    # 检查路径是否存在
    if not os.path.exists(input_path):
        print(f"错误：路径不存在 - {input_path}")
        return
    
    # 判断是文件还是文件夹
    if os.path.isfile(input_path):
        print(f"检测单个文件：{input_path}")
        process_single_image(input_path, delete_if_no_lines=delete_no_lines)
    elif os.path.isdir(input_path):
        print(f"检测文件夹：{input_path}")
        if delete_no_lines:
            print("⚠️ 警告：将删除没有线条的图片！")
            confirm = input("确认继续？(y/n): ").strip().lower()
            if confirm != 'y' and confirm != 'yes':
                print("操作已取消")
                return
        
        process_folder(input_path, delete_no_lines=delete_no_lines, backup_folder=backup_folder)
    else:
        print(f"错误：无效的路径类型 - {input_path}")


# ====================== 命令行使用说明 ======================

def print_usage():
    """打印使用说明"""
    print("使用说明：")
    print("  1. 检测单张图片：")
    print("     python line_detector.py image.jpg")
    print("     python line_detector.py image.jpg --delete  # 删除无线条图片")
    print("")
    print("  2. 检测文件夹：")
    print("     python line_detector.py folder/")
    print("     python line_detector.py folder/ --delete    # 删除无线条图片")
    print("     python line_detector.py folder/ --backup backup_folder/  # 备份后删除")
    print("")
    print("  3. 交互模式：")
    print("     python line_detector.py")


# ====================== 快速使用函数 ======================

def quick_check_lines(image_path, min_length_ratio=0.5):
    """
    快速检查图片是否有长度超过一半的线条
    
    Args:
        image_path: 图片路径
        min_length_ratio: 最小长度比例
        
    Returns:
        bool: 是否包含符合条件的线条
    """
    detector = LineDetector(min_length_ratio=min_length_ratio)
    result = detector.detect_lines(image_path)
    return result['has_lines']


def clean_folder_without_lines(folder_path, backup_path=None):
    """
    清理文件夹中没有线条的图片
    
    Args:
        folder_path: 要清理的文件夹
        backup_path: 备份路径（可选）
    
    Returns:
        tuple: (剩余图片数, 删除图片数, 备份图片数)
    """
    if not os.path.exists(folder_path):
        print(f"文件夹不存在: {folder_path}")
        return 0, 0, 0
    
    # 创建备份文件夹
    if backup_path:
        os.makedirs(backup_path, exist_ok=True)
    
    detector = LineDetector()
    image_extensions = ['.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif']
    
    deleted_count = 0
    backed_up_count = 0
    
    for filename in os.listdir(folder_path):
        if any(filename.lower().endswith(ext) for ext in image_extensions):
            image_path = os.path.join(folder_path, filename)
            
            # 检测是否有线条
            result = detector.detect_lines(image_path)
            
            if not result['has_lines']:
                # 备份
                if backup_path:
                    shutil.copy2(image_path, os.path.join(backup_path, filename))
                    backed_up_count += 1
                
                # 删除
                try:
                    os.remove(image_path)
                    deleted_count += 1
                    print(f"已删除: {filename}")
                except Exception as e:
                    print(f"删除失败 {filename}: {e}")
    
    # 统计剩余文件
    remaining_files = [f for f in os.listdir(folder_path) 
                      if any(f.lower().endswith(ext) for ext in image_extensions)]
    
    print(f"清理完成: 剩余{len(remaining_files)}张，删除{deleted_count}张")
    if backup_path:
        print(f"备份: {backed_up_count}张到 {backup_path}")
    
    return len(remaining_files), deleted_count, backed_up_count


if __name__ == "__main__":
    # 使用示例：
    # python line_detector.py "图片路径"
    # python line_detector.py "文件夹路径"
    # python line_detector.py "文件夹路径" --delete
    # python line_detector.py "文件夹路径" --backup "备份路径"
    
    main()