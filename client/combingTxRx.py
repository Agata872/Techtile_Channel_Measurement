#!/usr/bin/env python3
import subprocess
import threading
import sys
import yaml


def load_inventory(inventory_file):
    """加载 inventory.yaml 文件"""
    try:
        with open(inventory_file, "r") as f:
            inventory = yaml.safe_load(f)
        return inventory
    except Exception as e:
        print(f"加载 {inventory_file} 失败: {e}")
        sys.exit(1)


def run_remote_script(ip, script_path):
    """
    通过 SSH 在远程设备上执行指定脚本，
    切换到脚本目录并设置必要的 PYTHONPATH 环境变量，
    最后执行脚本。
    """
    remote_cmd = (
        'cd ~/Techtile_Channel_Measurement/client && '
        'export PYTHONPATH="/usr/local/lib/python3/dist-packages:$PYTHONPATH"; '
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
    inventory_file = "inventory.yaml"
    inventory = load_inventory(inventory_file)

    # 从 inventory 中获取所有主机信息
    all_hosts = inventory.get("all", {}).get("hosts", {})

    # 设置发射端为 T01，接收端为 A05
    if "T01" not in all_hosts:
        print("未找到 T01 主机信息")
        sys.exit(1)
    if "A05" not in all_hosts:
        print("未找到 A05 主机信息")
        sys.exit(1)

    tx_info = all_hosts["T01"]
    rx_info = all_hosts["A05"]

    tx_ip = tx_info.get("ansible_host")
    rx_ip = rx_info.get("ansible_host")

    if not tx_ip:
        print("T01 主机缺少 ansible_host 属性")
        sys.exit(1)
    if not rx_ip:
        print("A05 主机缺少 ansible_host 属性")
        sys.exit(1)

    # 定义远程脚本路径（请确保 Tx.py 和 Rx.py 路径正确）
    TX_SCRIPT_PATH = "~/Techtile_Channel_Measurement/client/Tx.py"
    RX_SCRIPT_PATH = "~/Techtile_Channel_Measurement/client/Rx.py"

    # 创建发射端和接收端线程
    tx_thread = threading.Thread(target=run_remote_script, args=(tx_ip, TX_SCRIPT_PATH))
    rx_thread = threading.Thread(target=run_remote_script, args=(rx_ip, RX_SCRIPT_PATH))

    print(f"启动发射端 T01 ({tx_ip}) ...")
    tx_thread.start()
    print(f"启动接收端 A05 ({rx_ip}) ...")
    rx_thread.start()

    # 等待所有线程结束
    tx_thread.join()
    rx_thread.join()

    print("协调控制脚本运行结束，实验已完成。")


if __name__ == "__main__":
    main()
