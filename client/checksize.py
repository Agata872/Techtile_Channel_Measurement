import yaml
import subprocess

REMOTE_USER = "pi"  # 远程设备默认用户名


def get_ceiling_hosts(inventory_path):
    """
    从 YAML 格式的 inventory 文件中提取 ceiling 组下的所有设备，
    返回字典，键为设备标识（例如 G09），值为实际连接地址（ansible_host）。
    """
    with open(inventory_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    # 获取 ceiling 组中设备的 key 列表
    ceiling_keys = list(data["all"]["children"]["ceiling"]["hosts"].keys())
    all_hosts = data["all"]["hosts"]
    hosts_info = {}
    for key in ceiling_keys:
        # 如果全局 hosts 部分存在 ansible_host，则使用其值；否则默认使用 key
        hosts_info[key] = all_hosts.get(key, {}).get("ansible_host", key)
    return hosts_info


def get_sd_memory(host_key, remote_host, remote_user=REMOTE_USER):
    """
    通过 SSH 登录远程设备，并执行 `df -h /` 获取 SD 卡（根文件系统）剩余内存。
    返回字符串（例如 "5.7G"），如果失败则返回 None。
    """
    cmd = ["ssh", f"{remote_user}@{remote_host}", "df", "-h", "/"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired:
        print(f"连接设备 {host_key} ({remote_host}) 超时。")
        return None
    if result.returncode != 0:
        print(f"设备 {host_key} ({remote_host}) 执行命令失败，错误信息: {result.stderr.strip()}")
        return None
    lines = result.stdout.splitlines()
    if len(lines) < 2:
        print(f"设备 {host_key} ({remote_host}) 返回数据格式异常。")
        return None
    # 通常第二行包含 SD 卡（根文件系统）的信息，格式类似：
    # Filesystem      Size  Used Avail Use% Mounted on
    # /dev/root       7.8G  2.1G  5.7G  27% /
    fields = lines[1].split()
    if len(fields) < 5:
        print(f"设备 {host_key} ({remote_host}) 返回数据格式异常。")
        return None
    available = fields[3]  # “Avail” 列
    return available


def main():
    inventory_path = "inventory.yaml"  # 请修改为你的 inventory 文件路径
    hosts_info = get_ceiling_hosts(inventory_path)
    print("检测 ceiling 组中每个设备的 SD 卡剩余内存：")
    for host_key, remote_host in hosts_info.items():
        available = get_sd_memory(host_key, remote_host)
        if available:
            print(f"设备 {host_key} ({remote_host}) 剩余内存: {available}")
        else:
            print(f"设备 {host_key} ({remote_host}) 无法获取剩余内存信息。")


if __name__ == "__main__":
    main()
