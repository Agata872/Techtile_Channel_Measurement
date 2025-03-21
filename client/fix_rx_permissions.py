#!/usr/bin/env python3
import subprocess
import sys
import yaml

def load_inventory(inventory_file):
    """加载 inventory.yaml 文件"""
    try:
        with open(inventory_file, "r") as f:
            inventory = yaml.safe_load(f)
        return inventory
    except Exception as e:
        print(f"加载 {inventory_file} 失败: {e}")
        sys.exit(1)

def fix_remote_permissions(target):
    """
    修改远程设备上 Raw_Data 目录的权限，确保当前用户可以写入
    """
    remote_cmd = 'sudo chown -R $USER:$USER ~/Techtile_Channel_Measurement/Raw_Data'
    cmd = ["ssh", target, remote_cmd]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅【{target}】权限修复成功")
        else:
            print(f"❌【{target}】权限修复失败:\n{result.stderr}")
    except Exception as e:
        print(f"❌【{target}】连接失败: {e}")

def main():
    inventory_file = "inventory.yaml"
    inventory = load_inventory(inventory_file)

    global_user = inventory.get("all", {}).get("vars", {}).get("ansible_user", "pi")
    all_hosts = inventory.get("all", {}).get("hosts", {})

    # 你可以在这里指定多个接收端名称
    rx_names = ["ceiling"]  # 你也可以加 A06, A07 等

    for rx_name in rx_names:
        rx_info = all_hosts.get(rx_name)
        if not rx_info:
            print(f"⚠️ 未找到 {rx_name} 主机信息，跳过")
            continue
        rx_ip = rx_info.get("ansible_host")
        if not rx_ip:
            print(f"⚠️ {rx_name} 缺少 ansible_host，跳过")
            continue

        rx_target = f"{global_user}@{rx_ip}"
        print(f"🔧 正在修复 {rx_name} ({rx_target}) 的 Raw_Data 权限 ...")
        fix_remote_permissions(rx_target)

if __name__ == "__main__":
    main()
