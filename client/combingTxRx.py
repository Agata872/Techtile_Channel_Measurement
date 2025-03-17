#!/usr/bin/env python3
import subprocess
import threading
import time


# Todo: 首先应该将本地密钥文件推送到远程RPIs上以避免每次输入密码


# 定义设备 IP 地址与远程脚本路径
TX_IP = "192.108.1.162"
RX1_IP = "192.108.1.161"
RX2_IP = "192.108.1.163"
RX3_IP = "192.108.1.164"

TX_SCRIPT_PATH = "~/Techtile_Channel_Measurement/client/Tx.py"
RX1_SCRIPT_PATH = "~/Techtile_Channel_Measurement/client/Rx.py"
RX2_SCRIPT_PATH = "~/Techtile_Channel_Measurement/client/Rx.py"
RX3_SCRIPT_PATH = "~/Techtile_Channel_Measurement/client/Rx.py"

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
    # 创建线程分别启动发射端和两个接收端的远程脚本
    tx_thread = threading.Thread(target=run_remote_script, args=(TX_IP, TX_SCRIPT_PATH))
    rx1_thread = threading.Thread(target=run_remote_script, args=(RX1_IP, RX1_SCRIPT_PATH))
    rx2_thread = threading.Thread(target=run_remote_script, args=(RX2_IP, RX2_SCRIPT_PATH))
    rx3_thread = threading.Thread(target=run_remote_script, args=(RX3_IP, RX3_SCRIPT_PATH))

    # 同时启动三个线程
    tx_thread.start()
    rx1_thread.start()
    rx2_thread.start()
    rx3_thread.start()

    # 等待所有线程结束
    tx_thread.join()
    rx1_thread.join()
    rx2_thread.join()
    rx3_thread.join()

    print("协调控制脚本运行结束，实验已完成。")

if __name__ == "__main__":
    main()