import os
import re


def sort_file(file_path):
    # ... (函数内容保持不变)
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    segments = [seg.strip() for seg in content.split('----------------------------------------') if seg.strip()]
    segments_with_ts = []
    segments_without_ts = []
    for seg in segments:
        if 'Processing file:' in seg:
            m = re.search(r'round\d+_(\d{8}_\d{6})', seg)
            if m:
                timestamp = m.group(1)
                segments_with_ts.append((timestamp, seg))
            else:
                segments_without_ts.append(seg)
        else:
            segments_without_ts.append(seg)
    segments_with_ts.sort(key=lambda x: x[0])
    sorted_segments = [seg for ts, seg in segments_with_ts] + segments_without_ts
    new_content = "\n----------------------------------------\n".join(sorted_segments) + "\n"
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print(f"{file_path} 已排序并覆盖原数据。")


def main():
    # 修改这里，设置 data_folder 为正确的路径。假设 Data 文件夹在脚本上一级目录中
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_folder = os.path.join(script_dir, "..", "Data")  # 根据实际情况调整

    if not os.path.exists(data_folder):
        print(f"错误：目录 {data_folder} 不存在。")
        return

    for file_name in os.listdir(data_folder):
        if file_name.endswith("_result.txt"):
            file_path = os.path.join(data_folder, file_name)
            sort_file(file_path)


if __name__ == "__main__":
    main()
