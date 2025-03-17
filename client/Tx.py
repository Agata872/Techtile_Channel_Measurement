#!/usr/bin/env python3
import logging
import os
import socket
import sys
import threading
import time
from datetime import datetime, timedelta

import numpy as np
import uhd
import yaml
import zmq
import queue
import tools

# 全局常量（默认值可被 cal-settings.yml 中的配置覆盖）
CMD_DELAY = 0.05               # 命令间延时 50ms
RX_TX_SAME_CHANNEL = True      # 若环回由同一通道进行
CLOCK_TIMEOUT = 1000           # 外部时钟锁定超时（ms）
INIT_DELAY = 0.2               # 发射前延时 200ms
RATE = 250e3
LOOPBACK_TX_GAIN = 70          # 发射增益（经验值）
RX_GAIN = 22                 # 接收增益（经验值）
CAPTURE_TIME = 10              # 发射（或测量）时长，单位秒
FREQ = 0
meas_id = 0
exp_id = 0
results = []

SWITCH_LOOPBACK_MODE = 0x00000006
SWITCH_RESET_MODE = 0x00000000

# 初始化 ZMQ （此处虽然 TX 任务不发送 IQ 数据，但保留初始化代码）
context = zmq.Context()
iq_socket = context.socket(zmq.PUB)
iq_socket.bind(f"tcp://*:{50001}")

HOSTNAME = socket.gethostname()[4:]
file_open = False
server_ip = None  # 此处暂不使用

# 读取 cal-settings.yml 配置文件（如有）
with open(os.path.join(os.path.dirname(__file__), "cal-settings.yml"), "r") as file:
    vars = yaml.safe_load(file)
    globals().update(vars)  # 更新全局变量

# Setup logger with custom timestamp formatting
class LogFormatter(logging.Formatter):
    @staticmethod
    def pp_now():
        now = datetime.now()
        return "{:%H:%M}:{:05.2f}".format(now, now.second + now.microsecond / 1e6)

    def formatTime(self, record, datefmt=None):
        converter = self.converter(record.created)
        if datefmt:
            formatted_date = converter.strftime(datefmt)
        else:
            formatted_date = LogFormatter.pp_now()
        return formatted_date

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
console = logging.StreamHandler()
formatter = LogFormatter(fmt="[%(asctime)s] [%(levelname)s] (%(threadName)-10s) %(message)s")
console.setFormatter(formatter)
logger.addHandler(console)

# 根据 RX_TX_SAME_CHANNEL 定义通道角色
if RX_TX_SAME_CHANNEL:
    REF_RX_CH = FREE_TX_CH = 0
    LOOPBACK_RX_CH = LOOPBACK_TX_CH = 1
    logger.debug("\nPLL REF-->CH0 RX\nCH1 TX-->CH1 RX\nCH0 TX -->")
else:
    LOOPBACK_RX_CH = FREE_TX_CH = 0
    REF_RX_CH = LOOPBACK_TX_CH = 1
    logger.debug("\nPLL REF-->CH1 RX\nCH1 TX-->CH0 RX\nCH0 TX -->")


# -------------------------------
# 初始化与设置函数（直接沿用原脚本）
# -------------------------------
def setup_clock(usrp, clock_src, num_mboards):
    usrp.set_clock_source(clock_src)
    logger.debug("Now confirming lock on clock signals...")
    end_time = datetime.now() + timedelta(milliseconds=CLOCK_TIMEOUT)
    for i in range(num_mboards):
        is_locked = usrp.get_mboard_sensor("ref_locked", i)
        while (not is_locked) and (datetime.now() < end_time):
            time.sleep(1e-3)
            is_locked = usrp.get_mboard_sensor("ref_locked", i)
        if not is_locked:
            logger.error("Unable to confirm clock signal locked on board %d", i)
            return False
        else:
            logger.debug("Clock signals are locked")
    return True

def setup_pps(usrp, pps):
    logger.debug("Setting PPS")
    usrp.set_time_source(pps)
    return True

def print_tune_result(tune_res):
    logger.debug(
        "Tune Result:\n    Target RF  Freq: %.6f (MHz)\n Actual RF  Freq: %.6f (MHz)\n Target DSP Freq: %.6f (MHz)\n Actual DSP Freq: %.6f (MHz)\n",
        (tune_res.target_rf_freq / 1e6),
        (tune_res.actual_rf_freq / 1e6),
        (tune_res.target_dsp_freq / 1e6),
        (tune_res.actual_dsp_freq / 1e6),
    )

def tune_usrp(usrp, freq, channels, at_time):
    treq = uhd.types.TuneRequest(freq)
    usrp.set_command_time(uhd.types.TimeSpec(at_time))
    treq.dsp_freq = 0.0
    treq.target_freq = freq
    treq.rf_freq = freq
    treq.rf_freq_policy = uhd.types.TuneRequestPolicy(ord("M"))
    treq.dsp_freq_policy = uhd.types.TuneRequestPolicy(ord("M"))
    args = uhd.types.DeviceAddr("mode_n=integer")
    treq.args = args
    rx_freq = freq - 1e3
    rreq = uhd.types.TuneRequest(rx_freq)
    rreq.rf_freq = rx_freq
    rreq.target_freq = rx_freq
    rreq.dsp_freq = 0.0
    rreq.rf_freq_policy = uhd.types.TuneRequestPolicy(ord("M"))
    rreq.dsp_freq_policy = uhd.types.TuneRequestPolicy(ord("M"))
    rreq.args = uhd.types.DeviceAddr("mode_n=fractional")
    for chan in channels:
        print_tune_result(usrp.set_rx_freq(rreq, chan))
        print_tune_result(usrp.set_tx_freq(treq, chan))
    while not usrp.get_rx_sensor("lo_locked").to_bool():
        print(".")
        time.sleep(0.01)
    logger.info("RX LO is locked")
    while not usrp.get_tx_sensor("lo_locked").to_bool():
        print(".")
        time.sleep(0.01)
    logger.info("TX LO is locked")

def setup(usrp, server_ip, connect=False):
    rate = RATE
    mcr = 20e6
    assert (mcr / rate).is_integer(), f"The masterclock rate {mcr} should be an integer multiple of the sampling rate {rate}"
    usrp.set_master_clock_rate(mcr)
    channels = [0, 1]
    setup_clock(usrp, "external", usrp.get_num_mboards())
    setup_pps(usrp, "external")
    rx_bw = 200e3
    for chan in channels:
        usrp.set_rx_rate(rate, chan)
        usrp.set_tx_rate(rate, chan)
        usrp.set_rx_dc_offset(True, chan)
        usrp.set_rx_bandwidth(rx_bw, chan)
        usrp.set_rx_agc(False, chan)
    # 发射端设置：使用指定的 TX 通道（这里根据 RX_TX_SAME_CHANNEL，发射信号使用 FREE_TX_CH）
    usrp.set_tx_gain(LOOPBACK_TX_GAIN, FREE_TX_CH)
    # 此外可设置接收增益（虽然本 TX 脚本不采集，但为了保持配置一致）
    usrp.set_rx_gain(RX_GAIN, REF_RX_CH)
    st_args = uhd.usrp.StreamArgs("fc32", "sc16")
    st_args.channels = channels
    tx_streamer = usrp.get_tx_stream(st_args)
    rx_streamer = usrp.get_rx_stream(st_args)
    logger.info("Setting device timestamp to 0...")
    usrp.set_time_unknown_pps(uhd.types.TimeSpec(0.0))
    usrp.set_time_unknown_pps(uhd.types.TimeSpec(0.0))
    logger.debug("[SYNC] Resetting time.")
    logger.info(f"RX GAIN PROFILE CH0: {usrp.get_rx_gain_names(0)}")
    logger.info(f"RX GAIN PROFILE CH1: {usrp.get_rx_gain_names(1)}")
    time.sleep(2)  # 等待 PPS 上升沿
    tune_usrp(usrp, FREQ, channels, at_time=INIT_DELAY)
    logger.info(f"USRP tuned and setup. (Current time: {usrp.get_time_now().get_real_secs()})")
    return tx_streamer, rx_streamer

# -------------------------------
# 发射相关函数：tx_ref、tx_thread、tx_meta_thread
# -------------------------------
def tx_ref(usrp, tx_streamer, quit_event, phase, amplitude, start_time=None):
    num_channels = tx_streamer.get_num_channels()
    max_samps_per_packet = tx_streamer.get_max_num_samps()
    amplitude = np.asarray(amplitude)
    phase = np.asarray(phase)
    sample = amplitude * np.exp(phase * 1j)
    transmit_buffer = np.ones((num_channels, 1000 * max_samps_per_packet), dtype=np.complex64)
    transmit_buffer[0, :] *= sample[0]
    if num_channels > 1:
        transmit_buffer[1, :] *= sample[1]
    tx_md = uhd.types.TXMetadata()
    if start_time is not None:
        tx_md.time_spec = start_time
    else:
        tx_md.time_spec = uhd.types.TimeSpec(usrp.get_time_now().get_real_secs() + INIT_DELAY)
    tx_md.has_time_spec = True
    logger.info("TX will start at time: %.6f", tx_md.time_spec.get_real_secs())
    try:
        while not quit_event.is_set():
            tx_streamer.send(transmit_buffer, tx_md)
    except KeyboardInterrupt:
        logger.debug("CTRL+C pressed in TX")
    finally:
        tx_md.end_of_burst = True
        tx_streamer.send(np.zeros((num_channels, 0), dtype=np.complex64), tx_md)
        logger.info("TX finished.")

def tx_thread(usrp, tx_streamer, quit_event, phase=[0, 0], amplitude=[0.8, 0.8], start_time=None):
    tx_thr = threading.Thread(target=tx_ref, args=(usrp, tx_streamer, quit_event, phase, amplitude, start_time))
    tx_thr.setName("TX_thread")
    tx_thr.start()
    return tx_thr

def tx_async_th(tx_streamer, quit_event):
    async_metadata = uhd.types.TXAsyncMetadata()
    try:
        while not quit_event.is_set():
            if not tx_streamer.recv_async_msg(async_metadata, 0.01):
                continue
            else:
                if async_metadata.event_code != uhd.types.TXMetadataEventCode.burst_ack:
                    logger.error(async_metadata.event_code)
    except KeyboardInterrupt:
        pass

def tx_meta_thread(tx_streamer, quit_event):
    tx_meta_thr = threading.Thread(target=tx_async_th, args=(tx_streamer, quit_event))
    tx_meta_thr.setName("TX_META_thread")
    tx_meta_thr.start()
    return tx_meta_thr

def delta(usrp, at_time):
    return at_time - usrp.get_time_now().get_real_secs()

def get_current_time(usrp):
    return usrp.get_time_now().get_real_secs()

# -------------------------------
# 主程序：执行发射任务（同步控制后启动）
# -------------------------------
def main():
    try:
        # 初始化 USRP 设备并加载 FPGA 固件
        usrp = uhd.usrp.MultiUSRP("enable_user_regs, fpga=usrp_b210_fpga_loopback_ctrl.bin, mode_n=integer")
        logger.info("Using Device: %s", usrp.get_pp_string())

        # 完成硬件设置、同步与调谐，获得 TX 与 RX streamer
        tx_streamer, rx_streamer = setup(usrp, server_ip, connect=False)
        quit_event = threading.Event()

        # =========================
        # 新增：与同步服务器进行通信
        # =========================
        # 请将下面的 IP 修改为你的同步服务器实际IP地址
        sync_server_ip = "192.108.1.148"
        sync_context = zmq.Context()
        # 建立 REQ socket 与服务器的 alive 端口（5558）通信
        alive_client = sync_context.socket(zmq.REQ)
        alive_client.connect(f"tcp://{sync_server_ip}:5558")
        alive_message = f"{HOSTNAME} TX alive"
        logger.info("Sending alive message to sync server: %s", alive_message)
        alive_client.send_string(alive_message)
        reply = alive_client.recv_string()
        logger.info("Received alive reply from sync server: %s", reply)

        # 建立 SUB socket 监听同步消息（5557 端口）
        sync_subscriber = sync_context.socket(zmq.SUB)
        sync_subscriber.connect(f"tcp://{sync_server_ip}:5557")
        sync_subscriber.setsockopt_string(zmq.SUBSCRIBE, "")
        logger.info("Waiting for SYNC message from sync server...")
        sync_msg = sync_subscriber.recv_string()
        logger.info("Received SYNC message: %s", sync_msg)
        # =========================

        # 同步后，根据当前时间调度 TX 发射
        current_time = get_current_time(usrp)
        # 此处可设置一个短延时（例如 0.2 秒）确保配置完成后开始发射
        start_time_val = current_time + 0.2
        start_time_spec = uhd.types.TimeSpec(start_time_val)
        logger.info("Scheduled TX start time: %.6f", start_time_val)

        # 启动 TX 发射线程：此处信号参数设为幅度 1.0，相位 0.0（两个通道）
        tx_thr = tx_thread(usrp, tx_streamer, quit_event, phase=[0.0, 0.0], amplitude=[1.0, 1.0],
                           start_time=start_time_spec)
        # 同时启动 TX 异步元数据监控线程
        tx_meta_thr = tx_meta_thread(tx_streamer, quit_event)

        # 运行一段时间后停止发射
        time.sleep(CAPTURE_TIME + 15.0)
        quit_event.set()
        tx_thr.join()
        tx_meta_thr.join()

        logger.info("TX script finished successfully.")
    except Exception as e:
        logger.error("Error encountered in TX script: %s", e)
        sys.exit(1)
    finally:
        time.sleep(1)
        sys.exit(0)

if __name__ == "__main__":
    main()
