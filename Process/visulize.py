import yaml
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # 3D绘图必备
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

def get_ceiling_devices(inventory_path):
    """
    从 inventory.yaml 中读取属于 ceiling 组的设备ID，
    路径：all -> children -> ceiling -> hosts。
    返回一个包含设备ID的集合。
    """
    with open(inventory_path, 'r') as f:
        inventory = yaml.safe_load(f)
    ceiling_devices = set(inventory["all"]["children"]["ceiling"]["hosts"].keys())
    return ceiling_devices

def get_ceiling_ap_positions(positions_path, ceiling_devices):
    """
    从 positions.yml 的 'antennes' 中读取天花板 AP 位置信息。
    仅包含 tile 在 ceiling_devices 中且 ch == 0 的项。
    返回 [{'tile', 'x', 'y', 'z'}, ...]。
    """
    with open(positions_path, 'r') as f:
        data = yaml.safe_load(f)
    positions = []
    for ap in data.get("antennes", []):
        tile_name = str(ap.get("tile"))
        if tile_name in ceiling_devices:
            for ch in ap.get("channels", []):
                if ch.get("ch") == 0:
                    positions.append({
                        "tile": tile_name,
                        "x": ch.get("x"),
                        "y": ch.get("y"),
                        "z": ch.get("z")
                    })
                    break
    return positions

def plot_cylinder(ax, center=(0,0), z_bottom=0.0, z_top=1.0, radius=0.1,
                  color='goldenrod', alpha=0.7, resolution=20):
    """
    在已有的 3D Axes 中绘制一个竖直圆柱，
    用来表示天线下部结构，从 z_bottom 到 z_top。
    """
    theta = np.linspace(0, 2*np.pi, resolution)
    z_vals = np.linspace(z_bottom, z_top, 2)
    Theta, Z = np.meshgrid(theta, z_vals)
    X = center[0] + radius * np.cos(Theta)
    Y = center[1] + radius * np.sin(Theta)
    ax.plot_surface(X, Y, Z, rstride=1, cstride=1, color=color, alpha=alpha, linewidth=0)

# ------------------ 文件路径 (根据实际情况修改) ------------------
inventory_path = "inventory.yaml"
positions_path = "positions.yml"

ceiling_devices = get_ceiling_devices(inventory_path)
print("Ceiling devices:", ceiling_devices)
ap_positions = get_ceiling_ap_positions(positions_path, ceiling_devices)
print(f"Found {len(ap_positions)} ceiling AP positions.")

if not ap_positions:
    print("No ceiling AP positions to display.")
    exit()

# ------------------ 计算椭圆底面参数 ------------------
ap_xs = [pos["x"] for pos in ap_positions]
ap_ys = [pos["y"] for pos in ap_positions]
ap_zs = [pos["z"] for pos in ap_positions]

# 天花板平面的 z 值：取所有 AP 的最高点
z_ceil = max(ap_zs)

# 椭圆中心
center_x = (min(ap_xs) + max(ap_xs)) / 2.0
center_y = (min(ap_ys) + max(ap_ys)) / 2.0

# 将 pad_factor 调大以扩大椭圆面积
pad_factor = 1.6
a = (max(ap_xs) - min(ap_xs)) / 2.0 * pad_factor
b = (max(ap_ys) - min(ap_ys)) / 2.0 * pad_factor

num_ellipse_points = 50
theta = np.linspace(0, 2*np.pi, num_ellipse_points)
ellipse_points = []
for t in theta:
    x = center_x + a * np.cos(t)
    y = center_y + b * np.sin(t)
    ellipse_points.append([x, y, z_ceil])

# ------------------ 地面天线（圆锥顶点） ------------------
# 设置地面发射天线的坐标（根据实际情况调整）
ground_antenna = {"tile": "Ground", "x": 3.5, "y": 2.5, "z": 0.8}
apex = [ground_antenna["x"], ground_antenna["y"], ground_antenna["z"]]

# ------------------ 构造圆锥体侧面 ------------------
cone_side_faces = []
for i in range(len(ellipse_points) - 1):
    face = [apex, ellipse_points[i], ellipse_points[i+1]]
    cone_side_faces.append(face)
cone_side_faces.append([apex, ellipse_points[-1], ellipse_points[0]])
ellipse_face = ellipse_points[:]  # 作为圆锥底面

# ------------------ 绘图 ------------------
fig = plt.figure(figsize=(12, 10))
ax = fig.add_subplot(111, projection='3d')

# 修改坐标系空间面板（构成网格的背景）的颜色为淡蓝色
ax.xaxis.set_pane_color((0.9, 0.9, 1.0, 1))
ax.yaxis.set_pane_color((0.9, 0.9, 1.0, 1))
ax.zaxis.set_pane_color((0.9, 0.9, 1.0, 1))

# 绘制圆锥体（信号圆锥），使用浅色且透明显示
cone_side = Poly3DCollection(cone_side_faces, facecolor='powderblue', alpha=0.3, edgecolor='none')
ax.add_collection3d(cone_side)
base_face = Poly3DCollection([ellipse_face], facecolor='powderblue', alpha=0.3, edgecolor='none')
ax.add_collection3d(base_face)

# 绘制天花板上的 AP
for pos in ap_positions:
    x, y, z = pos["x"], pos["y"], pos["z"]
    label = pos["tile"]
    ax.scatter(x, y, z, s=80, color="blue", marker="o", zorder=10)
    ax.text(x + 0.1, y + 0.1, z, label, fontsize=9, color="black", zorder=10)

# 绘制地面发射天线——用平行于地面的方形表示天线顶面，颜色改为 goldenrod
square_size = 0.8
half_size = square_size / 2
square_corners = [
    [apex[0] - half_size, apex[1] - half_size, apex[2]],
    [apex[0] + half_size, apex[1] - half_size, apex[2]],
    [apex[0] + half_size, apex[1] + half_size, apex[2]],
    [apex[0] - half_size, apex[1] + half_size, apex[2]]
]
antenna_face = Poly3DCollection([square_corners], facecolor='goldenrod', alpha=0.7, edgecolor='black')
ax.add_collection3d(antenna_face)

# 在天线方形下方添加圆柱体，表示天线主体，圆柱体平行于 z 轴，
# 半径减小为方形边长的1/4，将其延伸到地板（z=0）
cylinder_radius = square_size / 10
plot_cylinder(ax, center=(apex[0], apex[1]), z_bottom=0, z_top=apex[2],
              radius=cylinder_radius, color='goldenrod', alpha=0.7, resolution=30)

# 设置坐标轴范围
all_x = ap_xs + [ground_antenna["x"]] + [pt[0] for pt in ellipse_points]
all_y = ap_ys + [ground_antenna["y"]] + [pt[1] for pt in ellipse_points]
all_z = ap_zs + [ground_antenna["z"]] + [pt[2] for pt in ellipse_points]
ax.set_xlim(min(all_x), max(all_x) + 0.2)
ax.set_ylim(min(all_y), max(all_y) + 0.2)
ax.set_zlim(0, max(all_z) + 0.2)

ax.set_xlabel("X (m)", fontsize=12, labelpad=10)
ax.set_ylabel("Y (m)", fontsize=12, labelpad=10)
ax.set_zlabel("Z (m)", fontsize=12, labelpad=10)

ax.set_box_aspect((1, 1, 1))
ax.view_init(elev=25, azim=45)
ax.grid(True, linestyle='--', alpha=0.5)
plt.savefig('Results/illu.png', dpi=300, bbox_inches='tight')
plt.show()
