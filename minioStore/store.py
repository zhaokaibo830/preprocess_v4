import datetime
import os
from minio import Minio
import requests
from pathlib import Path
# 1. 初始化 Minio 客户端
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

if __name__ == "__main__":
    images_path="/home/bestwish/preprocess_v4/data/output/demo0/vlm/images"
    file_name="demo0"
    timestamp=datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    store_images(images_path,file_name,timestamp,"60.204.211.83:10000","minioadmin","minioadmin123","preprocess")
    