import matplotlib as mpl
mpl.rcParams['animation.embed_limit'] = 200  # 增大动画嵌入大小限制

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import yaml
from matplotlib.animation import FuncAnimation
from tqdm import tqdm
import pandas as pd  # 用于读取 Excel 文件

# -------------------- 文件路径配置 --------------------
INVENTORY_PATH = "./inventory.yaml"
POSITIONS_PATH = "./positions.yml"
PHASE_DATA_PATH = "./round1_phase_data.npy"
AMPLITUDE_DATA_PATH = "./amplitude_data.npy"  # 幅度数据路径
TRUE_LOCATION_PATH = "./location.xlsx"         # 真实位置数据

# -------------------- 数据读取函数 --------------------
def get_ceiling_devices(inventory_path):
    with open(inventory_path, 'r') as f:
        inventory = yaml.safe_load(f)
    ceiling_devices = inventory['all']['children']['ceiling']['hosts'].keys()
    return list(ceiling_devices)

def get_ceiling_antenna_positions(positions_path, ceiling_tiles):
    with open(positions_path, 'r') as f:
        positions = yaml.safe_load(f)
    antenna_positions = []
    for tile in positions['antennes']:
        if tile['tile'] in ceiling_tiles:
            for ch in tile['channels']:
                if ch['ch'] == 0:
                    # 这里只读取天线的位置信息，固定假设天线朝向为 (0, 0, -1)
                    pos = {
                        'tile': tile['tile'],
                        'x': ch['x'],
                        'y': ch['y'],
                        'z': ch['z']
                    }
                    antenna_positions.append(pos)
    return antenna_positions

# -------------------- 数据加载 --------------------
# 加载相位数据，假设数据形状为 [n_devices, n_time_steps]
phase_data = np.load(PHASE_DATA_PATH)
n_devices, n_time_steps = phase_data.shape

# 加载幅度数据
amplitude_data = np.load(AMPLITUDE_DATA_PATH)
if amplitude_data.shape != (n_devices, n_time_steps):
    print("Warning: 幅度数据形状与相位数据形状不一致！")

# -------------------- 读取真实发射端位置信息 --------------------
# Excel文件第一行为表头 "x, y, z"，从第二行开始为数据，单位 mm，转换为 m
true_locations_df = pd.read_excel(TRUE_LOCATION_PATH)
true_positions = true_locations_df[['x', 'y', 'z']].values / 1000.0
if true_positions.shape[0] != n_time_steps:
    print("Warning: 真实位置数据的数量与时间帧数不一致！")

# -------------------- 加权最小二乘求交点函数 --------------------
def estimate_emitter_position(points, directions, weights):
    """
    利用加权最小二乘法估计信号源位置。
    参数：
      points: (n, 3) 天线位置数组
      directions: list/数组，包含 n 个 3D 单位方向向量
      weights: list/数组，表示各天线的权重（例如接收到的幅度）
    返回：
      估计的信号源位置 (3,)，若无法求解则返回 None
    """
    A = np.zeros((3, 3))
    b = np.zeros(3)
    for p, d, w in zip(points, directions, weights):
        # 忽略权重为 0 或无效的数据
        if np.isnan(w) or w <= 0:
            continue
        d = d.reshape(3, 1)  # 转换为列向量
        # 计算投影矩阵：去除 d 方向的分量
        P = np.eye(3) - d @ d.T
        A += w * P
        b += w * (P @ p)
    if np.linalg.norm(A) < 1e-6:
        return None
    try:
        x = np.linalg.solve(A, b)
    except np.linalg.LinAlgError:
        x = None
    return x

# -------------------- 主流程 --------------------
# 获取设备列表与天线位置（设备数和顺序应与相位数据一致）
device_tiles = get_ceiling_devices(INVENTORY_PATH)
antenna_positions = get_ceiling_antenna_positions(POSITIONS_PATH, device_tiles)
# 每个设备的固定位置
points = [np.array([pos['x'], pos['y'], pos['z']]) for pos in antenna_positions]

# -------------------- 创建动画 --------------------
fig = plt.figure(figsize=(10, 9))
ax = fig.add_subplot(111, projection='3d')

# 创建全局 tqdm 进度条，total 为总帧数
pbar = tqdm(total=n_time_steps, desc="Processing frames")

def update(frame):
    global pbar
    ax.cla()  # 清除当前图像
    L = 2.0  # 箭头长度尺度
    pts = []      # 存储天线位置
    dirs = []     # 存储方向向量
    weights = []  # 存储幅度权重

    # 遍历每个设备，绘制天线位置和方向，同时收集数据用于加权求交点
    for i, pos in enumerate(antenna_positions):
        p = np.array([pos['x'], pos['y'], pos['z']])
        # 取当前时刻的相位，计算方向（假设水平分量由相位决定，垂直分量固定为 -1）
        phi = np.angle(phase_data[i, frame])
        dx = np.cos(phi)
        dy = np.sin(phi)
        dz = -1
        d = np.array([dx, dy, dz])
        d = d / np.linalg.norm(d)  # 单位化方向向量

        # 获取幅度数据作为权重（若为 NaN 则置为 0）
        amp = amplitude_data[i, frame]
        if np.isnan(amp):
            amp = 0

        pts.append(p)
        dirs.append(d)
        weights.append(amp)

        # 绘制天线位置（蓝色点）
        ax.scatter(p[0], p[1], p[2], color='blue', s=50)
        # 绘制天线信号方向（箭头，cyan 颜色）
        ax.quiver(p[0], p[1], p[2], d[0], d[1], d[2],
                  length=L, normalize=True, color='cyan')
        # 添加天线标签
        ax.text(p[0], p[1], p[2], pos['tile'], fontsize=8)

    # 计算并绘制加权最小二乘法得到的交叉点（预测的信号源位置）
    estimated_pos = estimate_emitter_position(np.array(pts), dirs, weights)
    if estimated_pos is not None:
        ax.scatter(estimated_pos[0], estimated_pos[1], estimated_pos[2],
                   color='magenta', s=100, marker='*', label='Predicted Source')
        ax.text(estimated_pos[0], estimated_pos[1], estimated_pos[2],
                "Predicted", color='magenta', fontsize=10)

    # 绘制真实发射端位置（绿色圆圈），前提是 true_positions 数据与帧对应
    if frame < len(true_positions):
        true_pos = true_positions[frame]
        # 调试打印真实位置的 z 坐标
        print(f"Frame {frame}: True position z = {true_pos[2]}")
        ax.scatter(true_pos[0], true_pos[1], true_pos[2],
                   color='green', s=100, marker='o', label='True Source')
        ax.text(true_pos[0], true_pos[1], true_pos[2],
                "True", color='green', fontsize=10)

    ax.set_box_aspect((1, 1, 1))
    # 设置坐标轴标签和标题
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")
    ax.set_title(f"Time Step {frame}/{n_time_steps}")
    # 根据实际需求设置坐标轴范围，Z轴从0开始
    ax.set_xlim([0, 8])
    ax.set_ylim([0, 8])
    ax.set_zlim([0, 2.5])
    ax.legend()

    # 更新进度条
    pbar.update(1)

# 使用 range(n_time_steps) 作为帧序列
anim = FuncAnimation(fig, update, frames=range(n_time_steps), interval=300, repeat=False)

# 保存动画到文件
anim.save("animation.mp4", writer="ffmpeg", fps=10)

pbar.close()
