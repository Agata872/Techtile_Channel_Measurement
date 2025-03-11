import pandas as pd
import matplotlib.pyplot as plt

# 读取指定工作表（假设名称为 "Sheet1"）
df = pd.read_excel("phase_data.xlsx", sheet_name="Sheet1")

# 将 Timestamp 转为日期格式（如果需要）
df["Timestamp"] = pd.to_datetime(df["Timestamp"])

# 生成测量序号（1, 2, 3, ...）
measurement_numbers = range(1, len(df) + 1)

# 绘制各项数据随测量次数的变化
plt.figure(figsize=(10, 6))
plt.plot(measurement_numbers, df['RX1_phase'], marker='o', label='RX1_phase')
plt.plot(measurement_numbers, df['RX2_phase'], marker='o', label='RX2_phase')
plt.plot(measurement_numbers, df['Difference between RX1 and RX2'], marker='o', label='Difference')
plt.xlabel("Measurement")
plt.ylabel("Value")
plt.title("Measurement Changes - Sheet1")
plt.xticks(measurement_numbers)  # 将 x 轴刻度设置为测量序号
plt.legend()
plt.tight_layout()
plt.show()

# 读取 Sheet2（假设表头分别为 "Timestamp", "RX1_max_I", "RX2_max_I", "RX1_max_Q", "RX2_max_Q"）
df2 = pd.read_excel("phase_data.xlsx", sheet_name="Sheet2")

# 将 Timestamp 转为日期格式（如果需要）
df2["Timestamp"] = pd.to_datetime(df2["Timestamp"])

# 生成测量序号（1, 2, 3, ...）
measurement_numbers = range(1, len(df2) + 1)

# 绘制各项数据随测量次数的变化
plt.figure(figsize=(10, 6))
plt.plot(measurement_numbers, df2['RX1_max_I'], marker='o', label='RX1_max_I')
plt.plot(measurement_numbers, df2['RX2_max_I'], marker='o', label='RX2_max_I')
plt.plot(measurement_numbers, df2['RX1_max_Q'], marker='o', label='RX1_max_Q')
plt.plot(measurement_numbers, df2['RX2_max_Q'], marker='o', label='RX2_max_Q')
plt.xlabel("Measurement")
plt.ylabel("Value")
plt.title("Measurement Changes - Sheet2")
plt.xticks(measurement_numbers)  # 设置 x 轴刻度为测量次数
plt.legend()
plt.tight_layout()
plt.show()