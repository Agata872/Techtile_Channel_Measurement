#!/usr/bin/env python3
import subprocess
import threading
import time

# 定义设备信息与远程脚本路径
TX_IP = "192.108.1.162"
RX_IP = "192.108.1.161"
USER = "dramco_Tianzheng"  # 树莓派的用户名

# 假设发射端和接收端脚本分别位于各自设备的 "~/Techtile_Channel_Measurement/client/" 目录下
TX_SCRIPT_PATH = "~/Techtile_Channel_Measurement/client/Tx.py"
RX_SCRIPT_PATH = "~/Techtile_Channel_Measurement/client/Rx.py"

def run_remote_script(ip, script_path):
    """
    通过 SSH 调用远程设备上指定的 Python 脚本
    """
    cmd = ["ssh", f"{USER}@{ip}", "python3", script_path]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(f"【{ip}】脚本输出：\n{result.stdout}")
        if result.stderr:
            print(f"【{ip}】脚本错误输出：\n{result.stderr}")
    except Exception as e:
        print(f"调用 {ip} 上脚本失败: {e}")

def main():
    # 创建线程同时调用发射端与接收端脚本
    rx_thread = threading.Thread(target=run_remote_script, args=(RX_IP, RX_SCRIPT_PATH))
    tx_thread = threading.Thread(target=run_remote_script, args=(TX_IP, TX_SCRIPT_PATH))

    # 先启动接收端，再启动发射端（或几乎同时启动）
    rx_thread.start()
    tx_thread.start()

    # 等待两个线程结束
    rx_thread.join()
    tx_thread.join()

    print("协调控制脚本运行结束，实验已完成。")

if __name__ == "__main__":
    main()
