#!/usr/bin/env python3
import subprocess
import threading
import sys
import yaml


# Todo: 首先应该将本地密钥文件推送到远程RPIs上以避免每次输入密码

def load_inventory(inventory_file):
    """加载 inventory.yaml 文件"""
    try:
        with open(inventory_file, 'r') as f:
            inventory = yaml.safe_load(f)
        return inventory
    except Exception as e:
        print(f"加载 {inventory_file} 失败: {e}")
        sys.exit(1)


def run_remote_script(ip, script_path):
    """
    通过 SSH 在远程设备上执行指定脚本，
    在命令中先切换到脚本目录并导出必要的环境变量，
    确保非交互式 Shell 下能正确找到 uhd 模块和固件。
    """
    remote_cmd = (
        'cd ~/Techtile_Channel_Measurement/client && '
        'export PYTHONPATH="/usr/local/lib/python3.11/site-packages:$PYTHONPATH"; '
        f'python3 {script_path}'
    )
    cmd = ["ssh", ip, remote_cmd]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        print(f"【{ip}】脚本输出：\n{result.stdout}")
        if result.stderr:
            print(f"【{ip}】脚本错误输出：\n{result.stderr}")
    except Exception as e:
        print(f"调用 {ip} 上脚本失败: {e}")


def main():
    # 指定 inventory 文件路径（如有需要，可通过命令行参数传入）
    inventory_file = "inventory.yaml"
    inventory = load_inventory(inventory_file)

    # 从 all.hosts 获取所有设备信息
    all_hosts = inventory.get("all", {}).get("hosts", {})

    # 设定发射端为 T10
    if "T10" not in all_hosts:
        print("未找到 T10 主机信息")
        sys.exit(1)
    tx_info = all_hosts["T10"]
    tx_ip = tx_info.get("ansible_host")
    if not tx_ip:
        print("T10 主机缺少 ansible_host 属性")
        sys.exit(1)

    # 从 children.ceiling 获取接收端列表（注意 ceiling 下的 hosts 节点只列出主机名）
    children = inventory.get("all", {}).get("children", {})
    ceiling_group = children.get("ceiling", {})
    ceiling_hosts = ceiling_group.get("hosts", {})
    rx_devices = []
    for host in ceiling_hosts.keys():
        if host in all_hosts:
            host_ip = all_hosts[host].get("ansible_host")
            if host_ip:
                rx_devices.append((host, host_ip))
        else:
            print(f"在 all.hosts 中未找到 {host} 的详细信息")

    if not rx_devices:
        print("未找到 ceiling 组的接收端设备")
        sys.exit(1)

    # 定义远程脚本路径
    TX_SCRIPT_PATH = "~/Techtile_Channel_Measurement/client/Tx.py"
    RX_SCRIPT_PATH = "~/Techtile_Channel_Measurement/client/Rx.py"

    # 创建发射端线程
    tx_thread = threading.Thread(target=run_remote_script, args=(tx_ip, TX_SCRIPT_PATH))

    # 为每个接收端设备创建线程
    rx_threads = []
    for host, ip in rx_devices:
        t = threading.Thread(target=run_remote_script, args=(ip, RX_SCRIPT_PATH))
        rx_threads.append(t)

    # 同时启动发射端与所有接收端的线程
    print(f"启动发射端 T10 ({tx_ip})...")
    tx_thread.start()
    for host, ip in rx_devices:
        print(f"启动接收端 {host} ({ip})...")
        # 启动接收端线程
        for t in rx_threads:
            t.start()
        break  # 注意：此处避免重复启动，实际启动全部接收端线程的代码见下面

    # 正式启动所有接收端线程
    for t in rx_threads:
        t.start()

    # 等待所有线程结束
    tx_thread.join()
    for t in rx_threads:
        t.join()

    print("协调控制脚本运行结束，实验已完成。")


if __name__ == "__main__":
    main()
