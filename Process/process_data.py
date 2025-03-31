#!/usr/bin/env python3
import os
import glob
import numpy as np


def process_raw_data(raw_data_dir):
    """
    遍历 raw_data_dir 目录下所有 .npy 文件，
    对每个文件加载数据，检查是否为二维且有两行，
    分别计算每一行的平均值，并将结果保存到字典中，
    key 为文件名称（不含扩展名），value 为 [row1_avg, row2_avg]
    """
    npy_files = glob.glob(os.path.join(raw_data_dir, '*.npy'))
    results = {}

    if not npy_files:
        print(f"目录 {raw_data_dir} 下未找到 .npy 文件。")
        return results

    for file_path in npy_files:
        file_name = os.path.basename(file_path)
        file_id = os.path.splitext(file_name)[0]
        try:
            data = np.load(file_path)
            # 检查数据是否为二维数组且有两行
            if data.ndim != 2 or data.shape[0] != 2:
                print(f"文件 {file_name} 的数据格式不符合要求（必须为二维且有两行），跳过该文件。")
                continue
            avg_row1 = np.mean(data[0])
            avg_row2 = np.mean(data[1])
            results[file_id] = [avg_row1, avg_row2]
            print(f"处理 {file_name} 成功，第一行平均值: {avg_row1}, 第二行平均值: {avg_row2}")
        except Exception as e:
            print(f"处理 {file_name} 失败：{e}")
    return results


def save_results(results, output_file):
    """
    将结果字典保存到 output_file 中（使用 np.save 保存）
    """
    try:
        np.save(output_file, results)
        print(f"结果已保存到 {output_file}")
    except Exception as e:
        print(f"保存结果失败：{e}")


def main():
    # 目标数据目录，可以根据实际情况修改
    raw_data_dir = os.path.expanduser('~/Techtile_Channel_Measurement/Raw_Data')
    # 输出文件保存到该目录下
    output_file = os.path.join(raw_data_dir, 'result.npy')

    # 处理所有 npy 文件
    results = process_raw_data(raw_data_dir)
    # 保存处理结果
    save_results(results, output_file)


if __name__ == '__main__':
    main()
