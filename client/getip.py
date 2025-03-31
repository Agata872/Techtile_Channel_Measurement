import yaml
import subprocess

REMOTE_USER = "pi"  # 远程设备默认用户名


def get_ceiling_hosts(inventory_path):
    """
    从 YAML 格式的 inventory 文件中提取 ceiling 组下所有设备，
    返回一个字典，键为设备标识（如 G09），值为实际连接地址（ansible_host）。
    """
    with open(inventory_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    ceiling_keys = list(data["all"]["children"]["ceiling"]["hosts"].keys())
    global_hosts = data["all"]["hosts"]

    hosts_info = {}
    for key in ceiling_keys:
        # 优先取 ansible_host 字段，否则使用 key 本身作为地址
        hosts_info[key] = global_hosts.get(key, {}).get("ansible_host", key)
    return hosts_info


def get_remote_ip(host_key, remote_host, remote_user=REMOTE_USER):
    """
    利用 SSH 登录远程设备并执行 'hostname -I' 获取该设备上报告的 IP 地址，
    返回第一个 IP 地址（若有多个）。
    """
    cmd = ["ssh", f"{remote_user}@{remote_host}", "hostname -I"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired:
        print(f"连接 {host_key} ({remote_host}) 超时。")
        return None
    if result.returncode != 0:
        print(f"从 {host_key} ({remote_host}) 获取 IP 地址失败，错误：{result.stderr.strip()}")
        return None
    ips = result.stdout.strip().split()
    if ips:
        return ips[0]
    else:
        return None


def main():
    inventory_path = "inventory.yml"  # 根据实际情况调整 inventory 文件路径
    hosts_info = get_ceiling_hosts(inventory_path)
    print("Ceiling 组设备及其获取的 IP 地址：")
    for host_key, remote_host in hosts_info.items():
        ip = get_remote_ip(host_key, remote_host)
        if ip:
            print(f"{host_key} ({remote_host}) -> IP: {ip}")
        else:
            print(f"{host_key} ({remote_host}) -> 无法获取 IP 地址")


if __name__ == "__main__":
    main()
