import subprocess

# 配置树莓派和文件信息
prefixes = ["A", "B", "C", "D", "E", "F", "G"]
device_range = range(1, 21)  # 从 1 到 20
remote_user = "pi"
remote_path_template = "experiments/02_reciprocity_based_WPT/client/"
local_path = "/home/techtile/Data"
files_to_copy = [
    "data_{}_20241108144903_1_loopback.npy",
    "data_{}_20241108144903_1_pilot.npy",
    "data_{}_20241108144903_2_loopback.npy",
    "data_{}_20241108144903_2_pilot.npy"
]
host_suffix = ".local"

def run_command(command):
    """运行系统命令并打印输出"""
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {e.cmd}")
        print(f"Error: {e.stderr}")

def copy_files(device_id, hostname):
    """从树莓派复制文件到本地"""
    for file_template in files_to_copy:
        filename = file_template.format(device_id)
        remote_file = f"{remote_user}@{hostname}:{remote_path_template}{filename}"
        print(f"Copying {remote_file} to {local_path}...")
        command = f"scp {remote_file} {local_path}"
        run_command(command)

def main():
    for prefix in prefixes:
        for i in device_range:
            device_id = f"{prefix}{str(i).zfill(2)}"
            hostname = f"rpi-{device_id}{host_suffix}"
            print(f"Processing {hostname}...")

            # 复制文件
            copy_files(device_id, hostname)

if __name__ == "__main__":
    main()
