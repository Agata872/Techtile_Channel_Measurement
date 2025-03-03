#!/usr/bin/env python3
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# 采样率（和采集时设置的一致）
RATE = 250e3

# CSV 文件名（请根据实际情况修改）
csv_filename = "data_offline_pilot_9.csv"

# 读取 CSV 文件，假设文件中有表头：ch0_real,ch0_imag,ch1_real,ch1_imag
df = pd.read_csv(csv_filename)

# 检查是否包含预期的列
expected_columns = ["ch0_real", "ch0_imag", "ch1_real", "ch1_imag"]
if not all(col in df.columns for col in expected_columns):
    raise ValueError("CSV 文件中缺少必要的列，请检查文件格式。")

# 将各通道数据转换为复数信号
iq_ch0 = df["ch0_real"].values + 1j * df["ch0_imag"].values
iq_ch1 = df["ch1_real"].values + 1j * df["ch1_imag"].values

# 计算每个通道的幅度
amp_ch0 = np.abs(iq_ch0)
amp_ch1 = np.abs(iq_ch1)

# 绘制时域幅度图
plt.figure(figsize=(10, 4))
plt.plot(amp_ch0, label="Channel 0 Amplitude")
plt.plot(amp_ch1, label="Channel 1 Amplitude", alpha=0.7)
plt.xlabel("Sample index")
plt.ylabel("Amplitude")
plt.title("Time-domain Amplitude")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()

# 对通道0进行 FFT 分析
N = len(iq_ch0)
fft_ch0 = np.fft.fft(iq_ch0)
fft_ch0 = np.fft.fftshift(fft_ch0)
freqs = np.fft.fftfreq(N, d=1/RATE)
freqs = np.fft.fftshift(freqs)

# 绘制频谱（dB）
plt.figure(figsize=(10, 4))
plt.plot(freqs, 20 * np.log10(np.abs(fft_ch0) + 1e-12))  # 加一个很小的数防止对数为负无穷
plt.xlabel("Frequency (Hz)")
plt.ylabel("Magnitude (dB)")
plt.title("Spectrum of Channel 0")
plt.grid(True)
plt.tight_layout()
plt.show()

# 简单统计分析：计算平均幅度和标准差
mean_amp_ch0 = np.mean(amp_ch0)
std_amp_ch0 = np.std(amp_ch0)
print("Channel 0: mean amplitude = {:.4f}, standard deviation = {:.4f}".format(mean_amp_ch0, std_amp_ch0))

# 简单判定：如果平均幅度大于标准差的3倍，则认为有真实信号
if mean_amp_ch0 > 3 * std_amp_ch0:
    print("Channel 0 likely contains a real signal.")
else:
    print("Channel 0 likely contains mostly noise.")

# 如果需要，也可以对通道1做类似的统计分析
mean_amp_ch1 = np.mean(amp_ch1)
std_amp_ch1 = np.std(amp_ch1)
print("Channel 1: mean amplitude = {:.4f}, standard deviation = {:.4f}".format(mean_amp_ch1, std_amp_ch1))
if mean_amp_ch1 > 3 * std_amp_ch1:
    print("Channel 1 likely contains a real signal.")
else:
    print("Channel 1 likely contains mostly noise.")
