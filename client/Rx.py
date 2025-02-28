#!/usr/bin/env python3
import logging
import sys
import time
import threading
from datetime import datetime, timedelta
import numpy as np
import uhd
import queue
import tools  # 请确保tools模块中包含get_phases_and_apply_bandpass、to_min_pi_plus_pi、circmean等函数

# 全局参数
RATE = 250e3
INIT_DELAY = 0.2
CAPTURE_TIME = 10       # 采集时长（秒）
RX_GAIN = 22
FREQ = 0

# 设置日志
logging.basicConfig(level=logging.DEBUG,
                    format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# --------------------------
# 辅助函数：delta 和 starting_in
# --------------------------
def delta(usrp, at_time):
    return at_time - usrp.get_time_now().get_real_secs()

def starting_in(usrp, at_time):
    return f"Starting in {delta(usrp, at_time):.2f}s"

# --------------------------
# USRP 初始化及配置
# --------------------------
def setup_usrp(usrp):
    mcr = 20e6
    usrp.set_master_clock_rate(mcr)
    channels = [0, 1]
    # 使用外部时钟和 PPS 同步
    usrp.set_clock_source("external")
    usrp.set_time_source("external")
    rx_bw = 200e3
    for chan in channels:
        usrp.set_rx_rate(RATE, chan)
        usrp.set_tx_rate(RATE, chan)  # 即使不发射也建议设置一致
        usrp.set_rx_dc_offset(True, chan)
        usrp.set_rx_bandwidth(rx_bw, chan)
        usrp.set_rx_agc(False, chan)
    # 设置 RX 增益（对通道0，此处可根据需要调整天线选择）
    usrp.set_rx_gain(RX_GAIN, 0)
    st_args = uhd.usrp.StreamArgs("fc32", "sc16")
    st_args.channels = channels
    rx_streamer = usrp.get_rx_stream(st_args)
    # 同步时间
    usrp.set_time_unknown_pps(uhd.types.TimeSpec(0.0))
    time.sleep(2)
    # 调谐（这里简单调谐到FREQ，具体细节可根据实际需求扩展）
    tune_req_time = INIT_DELAY
    tune_req = uhd.types.TuneRequest(FREQ)
    for chan in channels:
        usrp.set_rx_freq(tune_req, chan)
    logger.info("USRP 调谐完成，当前时间：%.6f", usrp.get_time_now().get_real_secs())
    return rx_streamer

# --------------------------
# 接收数据处理函数 rx_ref
# --------------------------
def rx_ref(usrp, rx_streamer, quit_event, duration, result_queue, start_time=None):
    logger.debug("rx_ref 开始采集数据，采集时长: %s 秒", duration)
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
    num_rx = 0
    try:
        while not quit_event.is_set():
            try:
                num_rx_i = rx_streamer.recv(recv_buffer, rx_md, timeout)
                if rx_md.error_code != uhd.types.RXMetadataErrorCode.none:
                    logger.error("RX 错误: %s", rx_md.error_code)
                else:
                    if num_rx_i > 0:
                        samples = recv_buffer[:, :num_rx_i]
                        if num_rx + num_rx_i > buffer_length:
                            logger.error("RX 缓冲区溢出")
                        else:
                            iq_data[:, num_rx:num_rx+num_rx_i] = samples
                            num_rx += num_rx_i
            except RuntimeError as ex:
                logger.error("RX 运行时错误: %s", ex)
                break
    except KeyboardInterrupt:
        pass
    finally:
        logger.debug("rx_ref 结束采集")
        rx_streamer.issue_stream_cmd(uhd.types.StreamCMD(uhd.types.StreamMode.stop_cont))
        # 截取有效数据进行处理（例如跳过初始部分）
        iq_samples = iq_data[:, int(RATE//10):num_rx]
        np.save("rx_pilot_iq_data.npy", iq_samples)
        # 利用 tools 模块处理 IQ 数据，计算两通道之间的相位差
        phase_ch0, _ = tools.get_phases_and_apply_bandpass(iq_samples[0, :])
        phase_ch1, _ = tools.get_phases_and_apply_bandpass(iq_samples[1, :])
        phase_diff = tools.to_min_pi_plus_pi(phase_ch0 - phase_ch1, deg=False)
        pilot_phase = np.mean(phase_diff)
        result_queue.put(pilot_phase)
        logger.debug("计算得到的 pilot 相位: %.6f", pilot_phase)

# --------------------------
# 启动 RX 线程
# --------------------------
def rx_thread(usrp, rx_streamer, quit_event, duration, result_queue, start_time=None):
    _rx_thread = threading.Thread(target=rx_ref, args=(usrp, rx_streamer, quit_event, duration, result_queue, start_time))
    _rx_thread.setName("RX_thread")
    _rx_thread.start()
    return _rx_thread

# --------------------------
# measure_pilot 函数（保留初始代码中的实现）
# --------------------------
def measure_pilot(usrp, rx_streamer, quit_event, result_queue, at_time=None):
    logger.debug("########### Measure PILOT ###########")
    start_time = uhd.types.TimeSpec(at_time)
    logger.debug(starting_in(usrp, at_time))
    # 切换到“TX/RX”天线模式（假设该设置适用于硬件）
    usrp.set_rx_antenna("TX/RX", 1)
    rx_thr = rx_thread(usrp, rx_streamer, quit_event, duration=CAPTURE_TIME, result_queue=result_queue, start_time=start_time)
    # 等待采集时长结束
    sleep_time = CAPTURE_TIME + delta(usrp, at_time)
    if sleep_time < 0:
        sleep_time = CAPTURE_TIME
    time.sleep(sleep_time)
    quit_event.set()
    rx_thr.join()
    # 恢复天线设置
    usrp.set_rx_antenna("RX2", 1)
    quit_event.clear()

# --------------------------
# 主函数
# --------------------------
def main():
    rx_args = "addr=192.108.1.161, enable_user_regs, fpga=usrp_b210_fpga_loopback_ctrl.bin, mode_n=integer"
    try:
        usrp = uhd.usrp.MultiUSRP(rx_args)
        logger.info("RX USRP初始化成功: %s", usrp.get_pp_string())
    except Exception as e:
        logger.error("RX USRP初始化失败: %s", e)
        sys.exit(1)
    rx_streamer = setup_usrp(usrp)
    quit_event = threading.Event()
    result_queue = queue.Queue()

    # 预定采集启动时刻，取当前时间加5秒
    current_time = usrp.get_time_now().get_real_secs()
    start_time_val = current_time + 5.0
    logger.info("预定 RX 启动时刻: %.6f", start_time_val)

    # 使用 measure_pilot 函数完成 pilot 信号的采集与测量
    measure_pilot(usrp, rx_streamer, quit_event, result_queue, at_time=start_time_val)

    if not result_queue.empty():
        pilot_phase = result_queue.get()
        logger.info("最终测量到的 pilot 相位: %.6f", pilot_phase)
    else:
        logger.error("未获得测量结果")

    logger.info("RX 脚本运行结束")

if __name__ == "__main__":
    main()
