import os
import glob
import argparse

def delete_specific_pages(folder_path, page_numbers):
    """
    删除指定页码结尾的图片文件
    
    Args:
        folder_path (str): 图片文件夹路径
        page_numbers (list): 要删除的页码列表
    """
    if not os.path.exists(folder_path):
        print(f"错误：文件夹 '{folder_path}' 不存在")
        return
    
    # 确保输入是字符串列表
    page_strs = [str(page) for page in page_numbers]
    
    deleted_files = []
    failed_files = []
    
    # 遍历所有png文件
    for file_path in glob.glob(os.path.join(folder_path, "*.png")):
        filename = os.path.basename(file_path)
        
        # 检查文件名是否以指定页码结尾
        for page_str in page_strs:
            # 处理不同的文件名格式
            if filename.endswith(f"_{page_str}.png"):
                try:
                    os.remove(file_path)
                    deleted_files.append(filename)
                    break  # 如果已经删除，跳出内部循环
                except Exception as e:
                    failed_files.append((filename, str(e)))
                    break
    
    # 输出结果
    print(f"扫描完成，共处理 {len(deleted_files) + len(failed_files)} 个匹配文件")
    
    if deleted_files:
        print(f"\n成功删除 {len(deleted_files)} 个文件:")
        for filename in deleted_files:
            print(f"  - {filename}")
    
    if failed_files:
        print(f"\n删除失败 {len(failed_files)} 个文件:")
        for filename, error in failed_files:
            print(f"  - {filename}: {error}")

def main():
    parser = argparse.ArgumentParser(description="删除指定页码结尾的图片文件")
    parser.add_argument("pages", nargs="+", type=int, 
                       help="要删除的页码（可指定多个，用空格分隔）")
    parser.add_argument("--folder", "-f", default="./output", 
                       help="图片文件夹路径，默认为 ./output")
    
    args = parser.parse_args()
    
    print(f"正在扫描文件夹: {args.folder}")
    print(f"要删除的页码: {args.pages}")
    
    # 确认操作
    confirm = input(f"\n确认要删除这些页码的文件吗？(y/n): ")
    if confirm.lower() in ['y', 'yes', '是']:
        delete_specific_pages(args.folder, args.pages)
    else:
        print("操作已取消")

if __name__ == "__main__":
    main()