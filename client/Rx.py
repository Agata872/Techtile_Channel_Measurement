#!/usr/bin/env python3
import logging
import os
import socket
import sys
import threading
import time
from datetime import datetime, timedelta
import csv

import numpy as np
import uhd
import yaml
import zmq
import queue
import tools

CMD_DELAY = 0.05               # 命令延时
RX_TX_SAME_CHANNEL = True      # 同通道环回标志
CLOCK_TIMEOUT = 1000           # 外部时钟锁定超时（ms）
INIT_DELAY = 0.2               # 初始延时（秒）
RATE = 250e3
LOOPBACK_TX_GAIN = 70          # 发射增益（经验值）
RX_GAIN = 22                   # 接收增益（经验值）
CAPTURE_TIME = 10              # 采集时间（秒）
FREQ = 0
meas_id = 0
exp_id = 0
results = []

SWITCH_LOOPBACK_MODE = 0x00000006
SWITCH_RESET_MODE = 0x00000000

# 初始化 ZMQ（尽管本接收端脚本主要用于采集，但保留该部分代码）
context = zmq.Context()
iq_socket = context.socket(zmq.PUB)
iq_socket.bind(f"tcp://*:{50001}")

HOSTNAME = socket.gethostname()[4:]
file_open = False
server_ip = None  # 本接收端不依赖服务器

# 读取 cal-settings.yml 中的配置（如有）
with open(os.path.join(os.path.dirname(__file__), "cal-settings.yml"), "r") as file:
    vars = yaml.safe_load(file)
    globals().update(vars)  # 更新全局变量

# 设置日志输出（自定义时间戳格式）
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

# 根据 RX_TX_SAME_CHANNEL 定义各通道角色
if RX_TX_SAME_CHANNEL:
    REF_RX_CH = FREE_TX_CH = 0
    LOOPBACK_RX_CH = LOOPBACK_TX_CH = 1
    logger.debug("\nPLL REF-->CH0 RX\nCH1 TX-->CH1 RX\nCH0 TX -->")
else:
    LOOPBACK_RX_CH = FREE_TX_CH = 0
    REF_RX_CH = LOOPBACK_TX_CH = 1
    logger.debug("\nPLL REF-->CH1 RX\nCH1 TX-->CH0 RX\nCH0 TX -->")

# ---------------------------
# 接收端相关函数
# ---------------------------
def rx_ref(usrp, rx_streamer, quit_event, duration, result_queue, start_time=None):
    logger.debug("rx_ref: 开始采集数据，采集时长: %s 秒", duration)
    num_channels = rx_streamer.get_num_channels()
    max_samps_per_packet = rx_streamer.get_max_num_samps()
    buffer_length = int(duration * RATE * 2)
    iq_data = np.empty((num_channels, buffer_length), dtype=np.complex64)
    recv_buffer = np.zeros((num_channels, max_samps_per_packet), dtype=np.complex64)
    rx_md = uhd.types.RXMetadata()

    stream_cmd = uhd.types.StreamCMD(uhd.types.StreamMode.start_cont)
    stream_cmd.stream_now = False
    timeout = 1.0
    if start_time is not None:
        stream_cmd.time_spec = start_time
        time_diff = start_time.get_real_secs() - usrp.get_time_now().get_real_secs()
        if time_diff > 0:
            timeout = 1.0 + time_diff
    else:
        stream_cmd.time_spec = uhd.types.TimeSpec(usrp.get_time_now().get_real_secs() + INIT_DELAY + 0.1)
    rx_streamer.issue_stream_cmd(stream_cmd)
    try:
        num_rx = 0
        while not quit_event.is_set():
            try:
                num_rx_i = rx_streamer.recv(recv_buffer, rx_md, timeout)
                if rx_md.error_code != uhd.types.RXMetadataErrorCode.none:
                    logger.error("RX error: %s", rx_md.error_code)
                else:
                    if num_rx_i > 0:
                        samples = recv_buffer[:, :num_rx_i]
                        if num_rx + num_rx_i > buffer_length:
                            logger.error("采集数据超出预设缓冲区")
                        else:
                            iq_data[:, num_rx:num_rx+num_rx_i] = samples
                            num_rx += num_rx_i
            except RuntimeError as ex:
                logger.error("rx_ref 运行时错误: %s", ex)
                break
    except KeyboardInterrupt:
        pass
    finally:
        logger.debug("rx_ref: 采集结束，关闭流")
        rx_streamer.issue_stream_cmd(uhd.types.StreamCMD(uhd.types.StreamMode.stop_cont))
        # 截取有效数据（略去前面部分）
        iq_samples = iq_data[:, int(RATE // 10):num_rx]

        # 保存 IQ 数据到 .npy 文件，文件名由 file_name_state 决定
        np.save(file_name_state, iq_samples)
        logger.debug("IQ 数据已保存为 %s.npy", file_name_state)

        # 保存 IQ 数据为 CSV 文件
        csv_filename = file_name_state + ".csv"
        with open(csv_filename, 'w', newline='') as csvfile:
            csv_writer = csv.writer(csvfile)
            # 写入表头，根据通道数生成列标题（每个通道的实部和虚部）
            header = []
            for ch in range(iq_samples.shape[0]):
                header.extend([f"ch{ch}_real", f"ch{ch}_imag"])
            csv_writer.writerow(header)
            # 写入数据，每行保存各通道同一采样点的实部和虚部
            n_samples = iq_samples.shape[1]
            for i in range(n_samples):
                row = []
                for ch in range(iq_samples.shape[0]):
                    row.extend([iq_samples[ch, i].real, iq_samples[ch, i].imag])
                csv_writer.writerow(row)
        logger.debug("IQ 数据已保存为 CSV 文件：%s", csv_filename)

        # 利用 tools 模块处理 IQ 数据，计算 pilot 信号相位
        phase_ch0, freq_slope_ch0 = tools.get_phases_and_apply_bandpass(iq_samples[0, :])
        phase_ch1, freq_slope_ch1 = tools.get_phases_and_apply_bandpass(iq_samples[1, :])
        logger.debug("Frequency offset CH0: %.4f", freq_slope_ch0 / (2*np.pi))
        logger.debug("Frequency offset CH1: %.4f", freq_slope_ch1 / (2*np.pi))
        phase_diff = tools.to_min_pi_plus_pi(phase_ch0 - phase_ch1, deg=False)
        _circ_mean = tools.circmean(phase_diff, deg=False)
        _mean = np.mean(phase_diff)
        logger.debug("Diff cirmean and mean: %.6f", _circ_mean - _mean)
        result_queue.put(_mean)

        avg_ampl = np.mean(np.abs(iq_samples), axis=1)
        max_I = np.max(np.abs(np.real(iq_samples)), axis=1)
        max_Q = np.max(np.abs(np.imag(iq_samples)), axis=1)
        logger.debug("MAX AMPL IQ CH0: I %.6f Q %.6f CH1: I %.6f Q %.6f", max_I[0], max_Q[0], max_I[1], max_Q[1])
        logger.debug("AVG AMPL IQ CH0: %.6f CH1: %.6f", avg_ampl[0], avg_ampl[1])

def rx_thread(usrp, rx_streamer, quit_event, duration, res, start_time=None):
    _rx_thread = threading.Thread(
        target=rx_ref,
        args=(usrp, rx_streamer, quit_event, duration, res, start_time),
    )
    _rx_thread.setName("RX_thread")
    _rx_thread.start()
    return _rx_thread

def delta(usrp, at_time):
    return at_time - usrp.get_time_now().get_real_secs()

def starting_in(usrp, at_time):
    return f"Starting in {delta(usrp, at_time):.2f}s"

def measure_pilot(usrp, rx_streamer, quit_event, result_queue, at_time=None):
    logger.debug("########### Measure PILOT ###########")
    start_time = uhd.types.TimeSpec(at_time)
    logger.debug(starting_in(usrp, at_time))
    # 设置 RX 天线为 “TX/RX” 模式（硬件要求）
    usrp.set_rx_antenna("TX/RX", 1)
    rx_thr = rx_thread(usrp, rx_streamer, quit_event, duration=CAPTURE_TIME, res=result_queue, start_time=start_time)
    # 等待采集时长（加上启动延时补偿）
    sleep_time = CAPTURE_TIME + delta(usrp, at_time)
    if sleep_time < 0:
        sleep_time = CAPTURE_TIME
    time.sleep(sleep_time)
    quit_event.set()
    rx_thr.join()
    # 恢复天线设置
    usrp.set_rx_antenna("RX2", 1)
    quit_event.clear()

# ---------------------------
# 时钟、调谐、同步设置等函数（沿用最初代码）
# ---------------------------
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
    # 发射端与接收端设置：接收端主要关注 REF_RX_CH 的接收增益
    usrp.set_tx_gain(LOOPBACK_TX_GAIN, LOOPBACK_TX_CH)
    usrp.set_tx_gain(LOOPBACK_TX_GAIN, FREE_TX_CH)
    usrp.set_rx_gain(LOOPBACK_RX_GAIN, LOOPBACK_RX_CH)
    usrp.set_rx_gain(REF_RX_GAIN, REF_RX_CH)
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
    time.sleep(2)
    tune_usrp(usrp, FREQ, channels, at_time=INIT_DELAY)
    logger.info(f"USRP tuned and setup. (Current time: {usrp.get_time_now().get_real_secs()})")
    return tx_streamer, rx_streamer

# ---------------------------
# 主程序：仅进行 pilot 信号测量
# ---------------------------
def main():
    global file_name_state, file_name
    file_name = "data_offline"
    file_name_state = file_name + "_pilot"
    try:
        # 初始化 USRP 设备（加载指定 FPGA 固件）
        usrp = uhd.usrp.MultiUSRP("enable_user_regs, fpga=usrp_b210_fpga_loopback_ctrl.bin, mode_n=integer")
        logger.info("Using Device: %s", usrp.get_pp_string())

        # 硬件设置、同步与调谐
        tx_streamer, rx_streamer = setup(usrp, server_ip, connect=False)
        quit_event = threading.Event()
        result_queue = queue.Queue()

        # 设置测量启动时间：当前时间后 5 秒
        current_time = usrp.get_time_now().get_real_secs()
        start_time_val = current_time + 5.0
        logger.info("Scheduled RX start time: %.6f", start_time_val)

        # 使用 measure_pilot 进行 pilot 信号测量
        measure_pilot(usrp, rx_streamer, quit_event, result_queue, at_time=start_time_val)
        phi_P = result_queue.get()
        logger.info("Pilot signal measured phase: %.6f", phi_P)

        # 将测量结果保存到文件中
        results_filename = "measurement_results.txt"
        with open(results_filename, "a") as f:
            f.write(f"{datetime.now()}: Pilot phase: {phi_P:.6f}\n")
        logger.info("Measurement results saved to %s", results_filename)

        print("Measurement DONE")
    except Exception as e:
        logger.error("Error encountered: %s", e)
        quit_event.set()
    finally:
        time.sleep(1)
        sys.exit(0)

if __name__ == "__main__":
    main()
