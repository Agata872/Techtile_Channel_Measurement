#!/usr/bin/env python3
import logging
import sys
import time
import threading
from datetime import datetime
import numpy as np
import uhd

# 全局参数
RATE = 250e3
INIT_DELAY = 0.2
CAPTURE_TIME = 10       # 发射持续时间（秒）
FREQ = 0                # 调谐频率
LOOPBACK_TX_GAIN = 70   # 发射增益

# 设置日志
logging.basicConfig(level=logging.DEBUG,
                    format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def setup_usrp(usrp):
    mcr = 20e6
    usrp.set_master_clock_rate(mcr)
    channels = [0, 1]
    # 使用外部时钟和PPS信号同步
    usrp.set_clock_source("external")
    usrp.set_time_source("external")
    rx_bw = 200e3
    for chan in channels:
        usrp.set_rx_rate(RATE, chan)
        usrp.set_tx_rate(RATE, chan)
        usrp.set_rx_dc_offset(True, chan)
        usrp.set_rx_bandwidth(rx_bw, chan)
        usrp.set_rx_agc(False, chan)
    # 对发射端，设置TX增益（这里选用通道0）
    usrp.set_tx_gain(LOOPBACK_TX_GAIN, 0)
    st_args = uhd.usrp.StreamArgs("fc32", "sc16")
    st_args.channels = channels
    tx_streamer = usrp.get_tx_stream(st_args)
    # 同步时间
    usrp.set_time_unknown_pps(uhd.types.TimeSpec(0.0))
    time.sleep(2)
    # 调谐（此处未做具体调整，可根据需要扩展）
    return tx_streamer

def tx_ref(usrp, tx_streamer, quit_event, phase, amplitude, start_time=None):
    """
    在指定的start_time时刻开始发射一个恒定信号，其幅度和相位由参数指定，
    直到 quit_event 被置位为止。
    """
    num_channels = tx_streamer.get_num_channels()
    max_samps_per_packet = tx_streamer.get_max_num_samps()
    amplitude = np.asarray(amplitude)
    phase = np.asarray(phase)
    sample = amplitude * np.exp(phase * 1j)
    # 构造发射缓冲区
    transmit_buffer = np.ones((num_channels, 1000 * max_samps_per_packet), dtype=np.complex64)
    transmit_buffer[0, :] *= sample[0]
    if num_channels > 1:
        transmit_buffer[1, :] *= sample[1] if len(sample) > 1 else sample[0]
    tx_md = uhd.types.TXMetadata()
    if start_time is not None:
        tx_md.time_spec = start_time
    else:
        tx_md.time_spec = uhd.types.TimeSpec(usrp.get_time_now().get_real_secs() + INIT_DELAY)
    tx_md.has_time_spec = True
    logger.info("TX 将在 %.6f 时刻开始发射", tx_md.time_spec.get_real_secs())
    try:
        while not quit_event.is_set():
            tx_streamer.send(transmit_buffer, tx_md)
    except KeyboardInterrupt:
        logger.info("接收到中断信号，结束发射")
    finally:
        tx_md.end_of_burst = True
        tx_streamer.send(np.zeros((num_channels, 0), dtype=np.complex64), tx_md)
        logger.info("TX 发射结束")

def main():
    # 发射端USRP设备地址
    tx_args = "addr=192.108.1.162, enable_user_regs, fpga=usrp_b210_fpga_loopback_ctrl.bin, mode_n=integer"
    try:
        usrp = uhd.usrp.MultiUSRP(tx_args)
        logger.info("TX USRP初始化成功: %s", usrp.get_pp_string())
    except Exception as e:
        logger.error("TX USRP初始化失败: %s", e)
        sys.exit(1)

    tx_streamer = setup_usrp(usrp)
    quit_event = threading.Event()

    # 预定发射启动时刻，取当前时间加5秒
    current_time = usrp.get_time_now().get_real_secs()
    start_time_val = current_time + 5.0
    start_time_spec = uhd.types.TimeSpec(start_time_val)
    logger.info("预定 TX 启动时刻: %.6f", start_time_val)

    # 启动发射线程，设置信号幅度为0.8，相位为0.0
    tx_thread_obj = threading.Thread(target=tx_ref,
                                     args=(usrp, tx_streamer, quit_event, [0.0], [0.8], start_time_spec))
    tx_thread_obj.start()

    # 发射持续一段时间后退出
    time.sleep(CAPTURE_TIME + 5.0)  # 加入额外延时保证完成发射
    quit_event.set()
    tx_thread_obj.join()
    logger.info("TX 脚本运行结束")

if __name__ == "__main__":
    main()
