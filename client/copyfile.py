import yaml
import subprocess

# 目标虚拟机信息
DEST_USER = "techtile"
DEST_HOST = "192.108.1.147"
DEST_BASE_DIR = "/media/sf_Shared/Data"


def get_ceiling_hosts(inventory_path):
    """
    从 YAML 格式的 inventory 文件中提取 ceiling 组下的所有主机
    并返回字典，键为 inventory 中的主机 key（如 G09），值为实际连接使用的地址（ansible_host）。
    """
    with open(inventory_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    # 获取 ceiling 组下的主机 key 列表
    ceiling_keys = list(data["all"]["children"]["ceiling"]["hosts"].keys())
    # 全局 hosts 部分包含各主机的详细信息
    all_hosts = data["all"]["hosts"]
    hosts_info = {}
    for key in ceiling_keys:
        # 如果全局 hosts 中定义了 ansible_host，则使用其值，否则使用 key 本身
        hosts_info[key] = all_hosts.get(key, {}).get("ansible_host", key)
    return hosts_info


def create_destination_dir(host_key):
    """
    在目标虚拟机上创建目的文件夹 ~/Data/{host_key}
    """
    dest_dir = f"~/Data/{host_key}"
    cmd = ["ssh", f"{DEST_USER}@{DEST_HOST}", "mkdir", "-p", dest_dir]
    print("创建目标目录命令:", " ".join(cmd))
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"在虚拟机上创建目录 {dest_dir} 失败，请检查 SSH 配置。")
    else:
        print(f"虚拟机上目录 {dest_dir} 创建成功。")


def copy_raw_data(host_key, remote_host, remote_path="~/Techtile_Channel_Measurement/Raw_Data", src_user="pi"):
    """
    从远程设备（通过 remote_host 连接）复制 remote_path 目录到目标虚拟机上的 ~/Data/{host_key}
    """
    # 确保目标虚拟机上对应目录已存在
    create_destination_dir(host_key)

    src = f"{src_user}@{remote_host}:{remote_path}"
    dest = f"{DEST_USER}@{DEST_HOST}:{DEST_BASE_DIR}/{host_key}"
    cmd = ["scp", "-r", src, dest]
    print("执行复制命令:", " ".join(cmd))
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"从主机 {host_key} ({remote_host}) 复制数据失败，请检查网络或相关配置。")
    else:
        print(f"从主机 {host_key} ({remote_host}) 复制数据成功！")


def main():
    # 请根据实际情况修改 inventory 文件路径
    inventory_path = "inventory.yaml"
    hosts_info = get_ceiling_hosts(inventory_path)
    print("提取到的 ceiling 组主机信息:", hosts_info)
    for host_key, remote_host in hosts_info.items():
        copy_raw_data(host_key, remote_host)


if __name__ == "__main__":
    main()
