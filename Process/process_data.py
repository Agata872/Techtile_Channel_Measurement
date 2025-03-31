#!/usr/bin/env python3
import yaml
import subprocess
import os

# 全局配置
REMOTE_USER = "pi"  # 远程设备默认用户名
INVENTORY_PATH = "inventory.yml"  # 请确保此路径正确
# 目标数据目录（处理脚本中也采用此目录）
REMOTE_DATA_PATH = "~/Techtile_Channel_Measurement/Raw_Data"

# 内嵌的远程处理脚本内容，保存为 process_data.py 后在远程设备上执行
PROCESS_SCRIPT_CONTENT = '''#!/usr/bin/env python3
import os
import glob
import numpy as np

def process_raw_data(raw_data_dir):
    # 搜索目录下所有 .npy 文件
    npy_files = glob.glob(os.path.join(raw_data_dir, '*.npy'))
    results = {}
    if not npy_files:
        print(f"No .npy files found in {raw_data_dir}")
        return results
    for file_path in npy_files:
        file_name = os.path.basename(file_path)
        file_id = os.path.splitext(file_name)[0]
        try:
            data = np.load(file_path)
            # 要求数据为二维且有两行
            if data.ndim != 2 or data.shape[0] != 2:
                print(f"Skipping {file_name}: invalid shape {data.shape}")
                continue
            avg_row1 = np.mean(data[0])
            avg_row2 = np.mean(data[1])
            results[file_id] = [avg_row1, avg_row2]
            print(f"Processed {file_name}: row1 avg = {avg_row1}, row2 avg = {avg_row2}")
        except Exception as e:
            print(f"Error processing {file_name}: {e}")
    return results

def main():
    raw_data_dir = os.path.expanduser('~/Techtile_Channel_Measurement/Raw_Data')
    results = process_raw_data(raw_data_dir)
    output_file = os.path.join(raw_data_dir, 'result.npy')
    try:
        np.save(output_file, results)
        print(f"Results saved to {output_file}")
    except Exception as e:
        print(f"Failed to save results: {e}")

if __name__ == '__main__':
    main()
'''


def get_ceiling_hosts(inventory_path):
    """
    解析 YAML 格式的 inventory 文件，提取 ceiling 组中所有设备。
    优先使用 device_ip 字段，否则采用 ansible_host。
    返回一个字典：{ host_key: remote_ip, ... }
    """
    with open(inventory_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    ceiling_keys = list(data["all"]["children"]["ceiling"]["hosts"].keys())
    global_hosts = data["all"]["hosts"]
    hosts_info = {}
    for key in ceiling_keys:
        host_entry = global_hosts.get(key, {})
        if "device_ip" in host_entry:
            hosts_info[key] = host_entry["device_ip"]
        else:
            hosts_info[key] = host_entry.get("ansible_host", key)
    return hosts_info


def deploy_and_run(remote_ip):
    """
    将内嵌的处理脚本复制到远程设备上（保存为 ~/process_data.py），
    然后通过 SSH 执行该脚本，处理 Raw_Data 下的 .npy 文件，
    最后删除远程设备上的 process_data.py 文件。
    """
    local_script = "process_data.py"
    # 将 PROCESS_SCRIPT_CONTENT 写入本地文件
    with open(local_script, "w", encoding="utf-8") as f:
        f.write(PROCESS_SCRIPT_CONTENT)

    # 复制脚本到远程设备的家目录
    scp_cmd = ["scp", local_script, f"{REMOTE_USER}@{remote_ip}:~/process_data.py"]
    print(f"[{remote_ip}] Copying process_data.py ...")
    scp_result = subprocess.run(scp_cmd, capture_output=True, text=True)
    if scp_result.returncode != 0:
        print(f"[{remote_ip}] SCP failed: {scp_result.stderr}")
        return

    # 通过 SSH 执行远程脚本
    ssh_cmd = ["ssh", f"{REMOTE_USER}@{remote_ip}", "python3 ~/process_data.py"]
    print(f"[{remote_ip}] Running process_data.py ...")
    ssh_result = subprocess.run(ssh_cmd, capture_output=True, text=True)
    print(f"[{remote_ip}] Output:\n{ssh_result.stdout}")
    if ssh_result.returncode != 0:
        print(f"[{remote_ip}] Error running script: {ssh_result.stderr}")

    # 删除远程脚本
    ssh_rm_cmd = ["ssh", f"{REMOTE_USER}@{remote_ip}", "rm ~/process_data.py"]
    subprocess.run(ssh_rm_cmd)


def main():
    hosts_info = get_ceiling_hosts(INVENTORY_PATH)
    print("Ceiling 组设备及其 IP：")
    for host_key, remote_ip in hosts_info.items():
        print(f"{host_key} -> {remote_ip}")

    print("\n开始处理每个设备上的数据 ...")
    for host_key, remote_ip in hosts_info.items():
        print(f"\nProcessing device {host_key} ({remote_ip})")
        deploy_and_run(remote_ip)


if __name__ == "__main__":
    main()
