import yaml
import subprocess

REMOTE_USER = "pi"  # 默认远程用户名
REMOTE_DATA_PATH = "~/Techtile_Channel_Measurement/Raw_Data"


def get_ceiling_hosts(inventory_path):
    """
    从 YAML 格式的 inventory 文件中提取 ceiling 组下所有设备，
    返回一个字典，键为设备标识（如 A05），值为实际连接地址（ansible_host）。
    """
    with open(inventory_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    ceiling_keys = list(data["all"]["children"]["ceiling"]["hosts"].keys())
    global_hosts = data["all"]["hosts"]

    hosts_info = {}
    for key in ceiling_keys:
        # 采用全局 hosts 中的 ansible_host，如果没有则直接使用 key 作为地址
        hosts_info[key] = global_hosts.get(key, {}).get("ansible_host", key)
    return hosts_info


def process_remote_data(host_key, remote_host, remote_user=REMOTE_USER, remote_data_path=REMOTE_DATA_PATH):
    """
    利用 SSH 登录远程设备，在指定目录下处理数据。
    示例中，我们执行命令统计文件个数和该目录的总大小。
    你可以将 remote_command 修改为任何你需要的处理命令或调用远程脚本。
    """
    # 示例命令：进入目录后输出文件个数和总大小
    remote_command = (
        f'cd {remote_data_path} && '
        'echo "文件个数: $(ls | wc -l)" && '
        'echo "目录总大小: $(du -sh . | cut -f1)"'
    )
    cmd = ["ssh", f"{remote_user}@{remote_host}", remote_command]
    print(f"正在处理 {host_key} ({remote_host}) 的数据...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except Exception as e:
        print(f"{host_key} 处理时出现异常: {e}")
        return None
    if result.returncode != 0:
        print(f"{host_key} 数据处理失败: {result.stderr.strip()}")
        return None
    return result.stdout.strip()


def main():
    inventory_path = "inventory.yaml"  # 修改为你的 inventory 文件路径
    hosts_info = get_ceiling_hosts(inventory_path)
    results = {}
    for host_key, remote_host in hosts_info.items():
        output = process_remote_data(host_key, remote_host)
        if output:
            results[host_key] = output

    print("\n处理结果汇总：")
    for host, output in results.items():
        print(f"{host} ({hosts_info[host]}):\n{output}\n{'-' * 40}")


if __name__ == "__main__":
    main()
