#!/usr/bin/env python3
import subprocess
import threading
import sys
import yaml

def load_inventory(inventory_file):
    """加载 inventory.yaml 文件"""
    try:
        with open(inventory_file, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"❌ 加载 {inventory_file} 失败: {e}")
        sys.exit(1)

def extract_hosts_from_group(inventory, group_name):
    """提取指定组下的主机名列表"""
    children = inventory.get("all", {}).get("children", {})
    group = children.get(group_name, {})
    hosts = group.get("hosts", {})
    return list(hosts.keys())

def run_remote_script(target, script_path):
    """通过 SSH 在远程设备上执行指定脚本，并实时打印输出。"""
    remote_cmd = (
        'cd ~/Techtile_Channel_Measurement/client && '
        'export PYTHONPATH="/usr/local/lib/python3/dist-packages:$PYTHONPATH"; '
        f'python3 -u {script_path}'
    )
    cmd = ["ssh", target, remote_cmd]
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)

        # 实时读取输出
        for line in process.stdout:
            print(f"【{target}】输出: {line}", end='')

        process.wait()

        # 打印 stderr（如果有）
        stderr_output = process.stderr.read()
        if stderr_output:
            print(f"【{target}】错误输出:\n{stderr_output}")

    except Exception as e:
        print(f"❌ 调用 {target} 上脚本失败: {e}")

def main():
    TX_NAME = "A06"
    RX_NAMES = "A07"  # ceiling

    inventory_file = "inventory.yaml"
    inventory = load_inventory(inventory_file)

    global_user = inventory.get("all", {}).get("vars", {}).get("ansible_user", "pi")
    all_hosts = inventory.get("all", {}).get("hosts", {})

    # ✅ 提取接收端组内的所有主机名
    # RX_NAMES = extract_hosts_from_group(inventory, RX_GROUP_NAME)

    # 检查 TX 是否存在
    if TX_NAME not in all_hosts:
        print(f"❌ 未找到发射端 {TX_NAME} 主机信息")
        sys.exit(1)
    tx_ip = all_hosts[TX_NAME].get("ansible_host")
    if not tx_ip:
        print(f"❌ 发射端 {TX_NAME} 缺少 ansible_host 属性")
        sys.exit(1)
    tx_target = f"{global_user}@{tx_ip}"

    TX_SCRIPT_PATH = "~/Techtile_Channel_Measurement/client/Tx.py"
    RX_SCRIPT_PATH = "~/Techtile_Channel_Measurement/client/Rx.py"

    print(f"🚀 启动发射端 {TX_NAME} ({tx_target}) ...")
    tx_thread = threading.Thread(target=run_remote_script, args=(tx_target, TX_SCRIPT_PATH))
    tx_thread.start()

    # 启动接收端线程
    rx_threads = []
    for rx_name in RX_NAMES:
        if rx_name not in all_hosts:
            print(f"⚠️ 跳过接收端 {rx_name}，未找到主机信息")
            continue
        rx_ip = all_hosts[rx_name].get("ansible_host")
        if not rx_ip:
            print(f"⚠️ 跳过接收端 {rx_name}，缺少 ansible_host")
            continue
        rx_target = f"{global_user}@{rx_ip}"
        print(f"📡 启动接收端 {rx_name} ({rx_target}) ...")
        rx_thread = threading.Thread(target=run_remote_script, args=(rx_target, RX_SCRIPT_PATH))
        rx_threads.append(rx_thread)
        rx_thread.start()

    tx_thread.join()
    for t in rx_threads:
        t.join()

    print("✅ 协调控制脚本运行结束，实验已完成。")

if __name__ == "__main__":
    main()
