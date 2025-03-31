#!/usr/bin/env python3
import yaml
import subprocess
import os
import concurrent.futures

# 默认远程用户名及 inventory 文件路径（根据需要修改）
REMOTE_USER = "pi"
INVENTORY_PATH = "../Process/inventory.yaml"
# 远程数据目录（在远程设备上存放 .npy 文件的目录）
REMOTE_DATA_DIR = "~/Techtile_Channel_Measurement/Raw_Data"


def get_ceiling_hosts(inventory_path):
    """
    从 inventory 文件中提取 ceiling 组下所有设备，
    返回一个字典：键为设备名称（例如 A05），值为用于连接的 IP 地址，
    优先使用 device_ip，否则使用 ansible_host。
    """
    with open(inventory_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    ceiling_keys = list(data["all"]["children"]["ceiling"]["hosts"].keys())
    global_hosts = data["all"]["hosts"]

    hosts_info = {}
    for key in ceiling_keys:
        entry = global_hosts.get(key, {})
        if "device_ip" in entry:
            hosts_info[key] = entry["device_ip"]
        else:
            hosts_info[key] = entry.get("ansible_host", key)
    return hosts_info


def process_remote_device(device_name, remote_ip):
    """
    利用 SSH 登录远程设备，执行内嵌的 Python 脚本，
    脚本遍历 REMOTE_DATA_DIR 目录下的所有 .npy 文件，
    对每个文件使用 tools 模块处理 IQ 数据：
      - 分别计算两个通道的相位及频率斜率，
      - 计算两个通道间的相位差，得到循环均值和线性均值，
      - 计算每个通道的平均幅度、最大 I 和最大 Q 分量。
    脚本将处理结果（文本摘要）打印出来，最终由本地保存为 "{设备名称}_result.txt"。
    同时在处理时打印当前处理的文件名称以便查看进度。
    """
    remote_script = r'''
import os, sys, glob, numpy as np
# 将 tools 模块所在目录添加到模块搜索路径中
sys.path.insert(0, os.path.expanduser('~/Techtile_Channel_Measurement/client'))
import tools

def process_data(raw_data_dir):
    output_lines = []
    npy_files = glob.glob(os.path.join(raw_data_dir, '*.npy'))
    if not npy_files:
        output_lines.append("No .npy files found in {}".format(raw_data_dir))
        return "\n".join(output_lines)
    for file_path in npy_files:
        file_name = os.path.basename(file_path)
        output_lines.append("Processing file: {}".format(file_name))
        file_id = os.path.splitext(file_name)[0]
        try:
            data = np.load(file_path)
            if data.ndim != 2 or data.shape[0] != 2:
                output_lines.append("Skipping {}: invalid shape (expected 2 rows)".format(file_name))
                continue
            # 利用 tools 模块分别处理两个通道的 IQ 数据
            phase_ch0, freq_slope_ch0 = tools.get_phases_and_apply_bandpass(data[0, :])
            phase_ch1, freq_slope_ch1 = tools.get_phases_and_apply_bandpass(data[1, :])
            freq_offset_ch0 = freq_slope_ch0 / (2*np.pi)
            freq_offset_ch1 = freq_slope_ch1 / (2*np.pi)
            phase_diff = tools.to_min_pi_plus_pi(phase_ch0 - phase_ch1, deg=False)
            circ_mean = tools.circmean(phase_diff, deg=False)
            linear_mean = np.mean(phase_diff)
            avg_ampl = np.mean(np.abs(data), axis=1)
            max_I = np.max(np.abs(np.real(data)), axis=1)
            max_Q = np.max(np.abs(np.imag(data)), axis=1)

            output_lines.append("File: {}".format(file_name))
            output_lines.append("  CircMean phase diff: {:.6f}".format(circ_mean))
            output_lines.append("  Linear mean phase diff: {:.6f}".format(linear_mean))
            output_lines.append("  Frequency offset CH0: {:.4f}".format(freq_offset_ch0))
            output_lines.append("  Frequency offset CH1: {:.4f}".format(freq_offset_ch1))
            output_lines.append("  Avg amplitude: CH0 {:.6f}, CH1 {:.6f}".format(avg_ampl[0], avg_ampl[1]))
            output_lines.append("  Max I: CH0 {:.6f}, CH1 {:.6f}".format(max_I[0], max_I[1]))
            output_lines.append("  Max Q: CH0 {:.6f}, CH1 {:.6f}".format(max_Q[0], max_Q[1]))
            output_lines.append("-" * 40)
        except Exception as e:
            output_lines.append("Error processing {}: {}".format(file_name, e))
    return "\n".join(output_lines)

raw_data_dir = os.path.expanduser("''' + REMOTE_DATA_DIR + r'''")
result_text = process_data(raw_data_dir)
print(result_text)
'''
    cmd = ["ssh", f"{REMOTE_USER}@{remote_ip}", "python3", "-"]
    print(f"Processing device {device_name} ({remote_ip}) ...")
    try:
        result = subprocess.run(cmd, input=remote_script, text=True,
                                capture_output=True)
    except Exception as e:
        print(f"Error connecting to {device_name} ({remote_ip}): {e}")
        return None

    if result.returncode != 0:
        print(f"Remote processing error on {device_name} ({remote_ip}):\n{result.stderr}")
        return None

    return result.stdout


def process_device(device_name, remote_ip):
    """
    封装 process_remote_device() 并将结果保存到本地文件 {device_name}_result.txt
    """
    result_text = process_remote_device(device_name, remote_ip)
    if result_text is not None:
        filename = f"{device_name}_result.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(result_text)
        print(f"Result for {device_name} saved to {filename}")
    else:
        print(f"Failed to process device {device_name} ({remote_ip})")


def main():
    hosts_info = get_ceiling_hosts(INVENTORY_PATH)
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        for device_name, remote_ip in hosts_info.items():
            futures.append(executor.submit(process_device, device_name, remote_ip))
        # 等待所有线程完成
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as exc:
                print(f"Generated an exception: {exc}")


if __name__ == "__main__":
    main()
