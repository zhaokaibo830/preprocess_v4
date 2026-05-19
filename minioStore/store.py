import datetime
import os
from minio import Minio,S3Error
import requests
from pathlib import Path
import logging
from urllib3.exceptions import MaxRetryError, NewConnectionError
# 1. 初始化 Minio 客户端
logger = logging.getLogger(__name__)
client = Minio(
    "60.204.211.83:10000",
    access_key="minioadmin",
    secret_key="minioadmin123",
    secure=False
)

# 2. 配置参数
bucket_name = "preprocess"
local_file_path = "2.png"

# 3. 生成带时间戳的对象名称
# 获取当前时间：YYYYMMDD_HHMMSS 格式
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
# 获取原始文件名 (test.txt)
file_base_name = os.path.basename(local_file_path)
# 拼接成：20231027_153045_test.txt
object_name = f"{timestamp}/{file_base_name}"

def main():
    try:
        # 4. 确保 Bucket 存在
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
            print(f"Bucket '{bucket_name}' 创建成功")

        # 5. 上传文件
        client.fput_object(bucket_name, object_name, local_file_path)
        print(f"文件上传成功！对象存储名称为: {object_name}")

        # 6. 生成下载链接 (注意：这里需与你的 Minio 服务地址一致)
        # 只有在 Bucket 设置为 Public 时，该永久链接才直接可用
        download_url = f"http://60.204.211.83:10000/{bucket_name}/{object_name}"
        print(f"下载链接: {download_url}")

        # 7. 测试下载
        download_via_url(download_url, "downloaded_test.png")

    except Exception as err:
        print(f"发生错误: {err}")

def download_via_url(url, save_path):
    print(f"正在尝试从 URL 下载...")
    try:
        r = requests.get(url)
        if r.status_code == 200:
            with open(save_path, "wb") as f:
                f.write(r.content)
            print(f"测试下载成功，已保存至: {save_path}")
        else:
            print(f"下载失败，状态码: {r.status_code} (请检查 Bucket 权限是否为 Public)")
    except Exception as e:
        print(f"下载过程中出错: {e}")

"""
def store_images(images_path,file_name,timestamp,minio_ip,minio_access_key,minio_secret_key,bucket_name):
    client = Minio(
        minio_ip,
        access_key=minio_access_key,
        secret_key=minio_secret_key,
        secure=False
    )
    object_names = []
    for image in Path(images_path).iterdir():
        image_name = image.name
        object_name = f"{timestamp}_{file_name}/{image_name}"
        client.fput_object(bucket_name, object_name, str(image))
"""
def store_images(
    images_path,
    file_name,
    timestamp,
    minio_ip,
    minio_access_key,
    minio_secret_key,
    bucket_name,
):
    """
    批量把 images_path 目录下的图片上传到 MinIO。
    任何环节出错都只跳过/返回空列表，保证主流程不崩溃。
    返回: 成功上传的 object_name 列表
    """
    # 1. 初始化客户端失败 -> 直接返回空列表
    try:
        client = Minio(
            minio_ip,
            access_key=minio_access_key,
            secret_key=minio_secret_key,
            secure=False,
        )
        # 简单探活：如果连 bucket 是否存在都探测不了，说明网络/密钥大概率有问题
        if not client.bucket_exists(bucket_name):
            logger.warning("Bucket <%s> does not exist or no permission", bucket_name)
            return []
    except (MaxRetryError, NewConnectionError, S3Error, Exception) as e:
        logger.exception("MinIO client init/health check failed: %s", e)
        return []

    # 2. 逐文件上传，单文件失败只跳过
    object_names = []
    root = Path(images_path)
    if not root.is_dir():
        logger.warning("images_path <%s> is not a valid directory", images_path)
        return []

    for image in root.iterdir():
        if not image.is_file():
            continue
        image_name = image.name
        object_name = f"{timestamp}_{file_name}/{image_name}"
        try:
            client.fput_object(bucket_name, object_name, str(image))
            object_names.append(object_name)
        except (S3Error, MaxRetryError, NewConnectionError, OSError) as e:
            # 记录后跳过，不影响后续文件
            logger.error("Upload failed for <%s>: %s", object_name, e)
            continue

    logger.info("Successfully uploaded %d/%d images", len(object_names), len(list(root.iterdir())))
    return object_names

def store_files(
    target_path,  # 可以是文件夹路径，也可以是单个文件路径
    file_name,
    timestamp,
    minio_ip,
    minio_access_key,
    minio_secret_key,
    bucket_name,
):
    # 1. 初始化客户端 (保持原样)
    # ... (省略 client 初始化逻辑) ...

    root = Path(target_path)
    object_names = []

    # 2. 判断是单个文件还是文件夹
    if root.is_file():
        # 如果是单个文件 (如 zip)
        files_to_upload = [root]
    elif root.is_dir():
        # 如果是文件夹 (如 images 目录)
        files_to_upload = [f for f in root.iterdir() if f.is_file()]
    else:
        logger.warning("Path <%s> is neither a file nor a directory", target_path)
        return []

    # 3. 循环上传
    for file_path in files_to_upload:
        # 保持你原来的目录结构命名习惯
        # 如果传的是 zip，object_name 会变成 "时间戳_文件名/xxx.zip"
        object_name = f"{timestamp}_{file_name}/{file_path.name}"
        
        try:
            client.fput_object(bucket_name, object_name, str(file_path))
            object_names.append(object_name)
        except Exception as e:
            logger.error("Upload failed for <%s>: %s", object_name, e)
            continue

    return object_names

if __name__ == "__main__":
    images_path="/home/bestwish/preprocess_v4/data/output/demo0/vlm/images"
    file_name="demo0"
    timestamp=datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    store_images(images_path,file_name,timestamp,"60.204.211.83:10000","minioadmin","minioadmin123","preprocess")
    