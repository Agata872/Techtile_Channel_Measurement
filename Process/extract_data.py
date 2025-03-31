import os
import re
import math
import numpy as np


def process_device_file(file_path):
    """
    处理单个设备文件：
      - 按照分隔符 '----------------------------------------' 拆分数据段；
      - 只提取包含 "round1" 的数据段；
      - 从数据段中提取时间戳（格式 round1_YYYYMMDD_HHMMSS）和 “CircMean phase diff” 数值；
      - 将 phase 数值转换为复数：实部为 cos(phase)，虚部为 sin(phase)；
      - 按时间戳排序后返回一个列表，每个元素为一个复数。
    """
    segments_data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 按照分隔符拆分数据段，并去除多余空白字符
    segments = [seg.strip() for seg in content.split('----------------------------------------') if seg.strip()]

    for seg in segments:
        # 只处理包含 "Processing file:" 的数据段
        if 'Processing file:' not in seg:
            continue

        # 提取 "Processing file:" 后面的文件名
        m_file = re.search(r'Processing file:\s*(\S+)', seg)
        if not m_file:
            continue
        filename = m_file.group(1)

        # 只处理文件名中包含 "round1" 的数据段
        if "round1" not in filename:
            continue

        # 从文件名中提取时间戳，格式假设为 round1_YYYYMMDD_HHMMSS
        m_ts = re.search(r'round1_(\d{8}_\d{6})', filename)
        if not m_ts:
            continue
        timestamp = m_ts.group(1)

        # 提取 “CircMean phase diff” 数值（单位为 rad）
        m_phase = re.search(r'CircMean phase diff:\s*([-+]?[0-9]*\.?[0-9]+)', seg)
        if not m_phase:
            continue
        try:
            phase_val = float(m_phase.group(1))
        except ValueError:
            continue

        # 计算复数：实部为 cos(phase)，虚部为 sin(phase)
        comp_value = complex(math.cos(phase_val), math.sin(phase_val))
        segments_data.append((timestamp, comp_value))

    # 根据时间戳排序（YYYYMMDD_HHMMSS 格式，直接字符串排序即可）
    segments_data.sort(key=lambda x: x[0])

    # 返回排序后的复数值列表
    return [comp for ts, comp in segments_data]


def main():
    # 设置 Data 文件夹路径（请根据实际情况调整）
    data_folder = "Data"
    if not os.path.exists(data_folder):
        print(f"错误：目录 {data_folder} 不存在。")
        return

    device_files = sorted([f for f in os.listdir(data_folder) if f.endswith("_result.txt")])
    all_device_results = []  # 每个元素为一个设备的测量数据列表（复数列表）

    for file_name in device_files:
        file_path = os.path.join(data_folder, file_name)
        print(f"正在处理文件 {file_name}")
        measurements = process_device_file(file_path)
        all_device_results.append(measurements)

    # 找出所有设备中测量数据的最大个数
    max_length = max(len(row) for row in all_device_results) if all_device_results else 0
    n_devices = len(all_device_results)

    # 创建一个二维数组，填充值为 np.nan（注意：np.nan 对于复数数组会被视为 nan+0j）
    result_array = np.full((n_devices, max_length), np.nan, dtype=complex)
    for i, row in enumerate(all_device_results):
        result_array[i, :len(row)] = row

    # 保存为 npy 文件
    np.save("round1_phase_data.npy", result_array)
    print("所有设备数据已保存为二维数组至 round1_phase_data.npy")


if __name__ == "__main__":
    main()
