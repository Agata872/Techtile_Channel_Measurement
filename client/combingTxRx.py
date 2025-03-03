#!/usr/bin/env python3
import subprocess
import threading
import time

# 定义设备信息与远程脚本路径
TX_IP = "192.108.1.162"
RX_IP = "192.108.1.161"

# 假设 Tx.py 和 Rx.py 分别位于两台设备上的 "~/Techtile_Channel_Measurement/client/" 目录下
TX_SCRIPT_PATH = "~/Techtile_Channel_Measurement/client/Tx.py"
RX_SCRIPT_PATH = "~/Techtile_Channel_Measurement/client/Rx.py"


def run_remote_script(ip, script_path):
    """
    通过 SSH 执行远程脚本，在远程命令中先导出必要的环境变量，
    以确保非交互式 Shell 环境下可以找到 uhd 模块和固件。
    """
    # 在命令中导出 PYTHONPATH 和 UHD_IMAGES_DIR 环境变量，然后调用 python3 运行脚本
    remote_cmd = (
        'export PYTHONPATH="/usr/local/lib/python3.11/site-packages:$PYTHONPATH"; '
        f'python3 {script_path}'
    )

    cmd = ["ssh", f"{ip}", remote_cmd]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(f"【{ip}】脚本输出：\n{result.stdout}")
        if result.stderr:
            print(f"【{ip}】脚本错误输出：\n{result.stderr}")
    except Exception as e:
        print(f"调用 {ip} 上脚本失败: {e}")


def main():
    # 创建线程分别调用接收端和发射端脚本
    rx_thread = threading.Thread(target=run_remote_script, args=(RX_IP, RX_SCRIPT_PATH))
    tx_thread = threading.Thread(target=run_remote_script, args=(TX_IP, TX_SCRIPT_PATH))

    # 同时启动两个线程
    rx_thread.start()
    tx_thread.start()

    # 等待两个线程结束
    rx_thread.join()
    tx_thread.join()

    print("协调控制脚本运行结束，实验已完成。")


if __name__ == "__main__":
    main()
