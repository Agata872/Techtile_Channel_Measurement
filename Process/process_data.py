import yaml
import subprocess

REMOTE_USER = "pi"  # 默认远程用户名
REMOTE_DATA_PATH = "~/Techtile_Channel_Measurement/Raw_Data"


def get_ceiling_hosts(inventory_path):
    """
    从 YAML 格式的 inventory 文件中提取 ceiling 组下所有设备。
    优先使用每个设备定义中的 device_ip 字段，如果不存在则使用 ansible_host。
    返回一个字典，键为设备标识（例如 A05），值为用于连接的 IP 地址。
    """
    with open(inventory_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    # 获取 ceiling 组中设备的标识列表
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


def process_remote_data(host_key, remote_ip, remote_user=REMOTE_USER, remote_data_path=REMOTE_DATA_PATH):
    """
    通过 SSH 登录远程设备，进入指定的目录（例如 REMOTE_DATA_PATH），
    并执行数据处理命令（本示例中列出该目录下的文件列表）。
    你可以根据实际需求修改 remote_command 为其他数据处理操作。
    """
    remote_command = (
        f'cd {remote_data_path} && '
        'echo "处理数据目录: $(pwd)" && '
        'echo "文件列表:" && ls -l'
    )
    cmd = ["ssh", f"{remote_user}@{remote_ip}", remote_command]
    print(f"正在处理 {host_key} ({remote_ip}) 上的数据...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except Exception as e:
        print(f"{host_key} ({remote_ip}) 连接异常: {e}")
        return None
    if result.returncode != 0:
        print(f"{host_key} ({remote_ip}) 数据处理失败: {result.stderr.strip()}")
        return None
    return result.stdout.strip()


def main():
    inventory_path = "inventory.yaml"  # 修改为你的 inventory 文件路径
    hosts_info = get_ceiling_hosts(inventory_path)
    results = {}
    for host_key, remote_ip in hosts_info.items():
        output = process_remote_data(host_key, remote_ip)
        if output:
            results[host_key] = output

    print("\n所有设备处理结果：")
    for host, output in results.items():
        print(f"{host} ({hosts_info[host]}):\n{output}\n{'-' * 40}")


if __name__ == "__main__":
    main()
