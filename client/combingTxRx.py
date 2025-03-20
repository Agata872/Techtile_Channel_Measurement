#!/usr/bin/env python3
import subprocess
import threading
import sys
import yaml


def load_inventory(inventory_file):
    """加载 inventory.yaml 文件"""
    try:
        with open(inventory_file, 'r') as f:
            inventory = yaml.safe_load(f)
        return inventory
    except Exception as e:
        print(f"加载 {inventory_file} 失败: {e}")
        sys.exit(1)


def run_remote_script(target, script_path, python_path, pre_cmd=""):
    """
    通过 SSH 在远程设备上执行指定脚本，
    可选 pre_cmd 用于在执行脚本前运行其它命令（例如创建目录）。
    """
    remote_cmd = (
        f'{pre_cmd}cd ~/Techtile_Channel_Measurement/client && '
        f'export PYTHONPATH="{python_path}:$PYTHONPATH"; '
        f'python3 {script_path}'
    )
    cmd = ["ssh", target, remote_cmd]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        print(f"【{target}】脚本输出：\n{result.stdout}")
        if result.stderr:
            print(f"【{target}】脚本错误输出：\n{result.stderr}")
    except Exception as e:
        print(f"调用 {target} 上脚本失败: {e}")


def main():
    # 指定 inventory 文件路径
    inventory_file = "inventory.yaml"
    inventory = load_inventory(inventory_file)

    # 从 inventory 中获取全局用户名（假设全局 ansible_user 为 pi）
    global_user = inventory.get("all", {}).get("vars", {}).get("ansible_user", "")

    # 从 all.hosts 中提取设备信息
    all_hosts = inventory.get("all", {}).get("hosts", {})

    # 例如发射端设为 T03（这里示例中改为 T03，实际请根据需要设置）
    tx_name = "T03"
    if tx_name not in all_hosts:
        print(f"未找到 {tx_name} 主机信息")
        sys.exit(1)
    tx_info = all_hosts[tx_name]
    tx_ip = tx_info.get("ansible_host")
    if not tx_ip:
        print(f"{tx_name} 主机缺少 ansible_host 属性")
        sys.exit(1)
    tx_target = f"{global_user}@{tx_ip}" if global_user else tx_ip

    # 接收端设为 T04（示例中只有一个接收端）
    rx_names = ["T04"]
    rx_devices = []
    for name in rx_names:
        if name in all_hosts:
            host_ip = all_hosts[name].get("ansible_host")
            if host_ip:
                target = f"{global_user}@{host_ip}" if global_user else host_ip
                rx_devices.append((name, target))
            else:
                print(f"{name} 主机缺少 ansible_host 属性")
        else:
            print(f"未找到主机 {name}")

    if not rx_devices:
        print("未找到接收端设备")
        sys.exit(1)

    # 定义远程脚本路径
    TX_SCRIPT_PATH = "~/Techtile_Channel_Measurement/client/Tx.py"
    RX_SCRIPT_PATH = "~/Techtile_Channel_Measurement/client/Rx.py"

    # 分别为 Tx 和 Rx 指定不同的 PYTHONPATH
    tx_python_path = "/usr/local/lib/python3/dist-packages"
    rx_python_path = "/usr/local/lib/python3/dist-packages"
    # rx_python_path = "/usr/local/lib/python3/dist-packages"

    # 对于 Rx 设备，我们在运行脚本前先创建 data 目录
    rx_pre_cmd = 'mkdir -p ~/Techtile_Channel_Measurement/data && '

    # 创建发射端线程
    tx_thread = threading.Thread(
        target=run_remote_script,
        args=(tx_target, TX_SCRIPT_PATH, tx_python_path),
        name="TX_Thread"
    )

    # 为每个接收端设备创建线程（预先创建 data 目录）
    rx_threads = []
    for name, target in rx_devices:
        thread = threading.Thread(
            target=run_remote_script,
            args=(target, RX_SCRIPT_PATH, rx_python_path, rx_pre_cmd),
            name=f"RX_Thread_{name}"
        )
        rx_threads.append(thread)

    print(f"启动发射端 {tx_name} ({tx_target}) ...")
    tx_thread.start()

    for name, target in rx_devices:
        print(f"启动接收端 {name} ({target}) ...")

    for thread in rx_threads:
        thread.start()

    # 等待所有线程结束
    tx_thread.join()
    for thread in rx_threads:
        thread.join()

    print("协调控制脚本运行结束，实验已完成。")


if __name__ == "__main__":
    main()
