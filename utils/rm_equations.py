from pathlib import Path
import shutil
#删除images文件夹下的公式图片，移动到equation_images文件夹下
def remove_equations(full_json_data, output_path, folder_name, vlm_enable):
    eq_path = output_path / folder_name / ('vlm' if vlm_enable else 'auto') / 'equation_images'
    eq_path.mkdir(parents=True,exist_ok=True)
    for block_index, block in enumerate(full_json_data["output"]):
        if block["type"] == "interline_equation":
            img_path = block["lines"][0]["spans"][0]["image_path"]
            img_path=Path(output_path)/folder_name/('vlm' if vlm_enable else 'auto')/'images'/img_path
            if img_path.exists():
                shutil.move(str(img_path), str(output_path / folder_name / 'vlm' if vlm_enable else 'auto'/'equation_images' / img_path.name))
