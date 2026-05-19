from pathlib import Path
import shutil
def path_rearrange(task_temp_path: Path, output_path: Path, folder_name: str):
    uuid_dirs = [d for d in task_temp_path.iterdir() if d.is_dir()]
    if len(uuid_dirs)>0:
        # Step 1: 找 temp 下唯一 uuid 目录
        
        if len(uuid_dirs) != 1:
            raise RuntimeError(
                f"output_path_temp 下目录数量异常: {[d.name for d in uuid_dirs]}"
            )

        uuid_dir = uuid_dirs[0]

        # Step 2: 找 uuid 目录下唯一结果目录（如 29）
        result_dirs = [d for d in uuid_dir.iterdir() if d.is_dir()]
        if len(result_dirs) != 1:
            raise RuntimeError(
                f"{uuid_dir} 下结果目录数量异常: {[d.name for d in result_dirs]}"
            )

        result_dir = result_dirs[0]

        # Step 3: 移动结果目录到最终 output_path
        target_dir = output_path / folder_name
        if target_dir.exists():
            shutil.rmtree(target_dir)

        shutil.move(str(result_dir), str(target_dir))

        print(f"mineru 输出已移动至: {target_dir}")
    shutil.rmtree(task_temp_path)