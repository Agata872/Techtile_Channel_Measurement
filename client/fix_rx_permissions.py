#!/usr/bin/env python3
import subprocess
import sys
import yaml

def load_inventory(inventory_file):
    """加载 inventory.yaml 文件"""
    try:
        with open(inventory_file, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"❌ 加载 {inventory_file} 失败: {e}")
        sys.exit(1)

def fix_remote_permissions(target):
    """
    修改远程设备上 Raw_Data 目录的权限
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
    inventory = load_inventory("inventory.yaml")

    global_user = inventory.get("all", {}).get("vars", {}).get("ansible_user", "pi")
    all_hosts = inventory.get("all", {}).get("hosts", {})
    ceiling_group = inventory.get("ceiling", {}).get("hosts", {})

    if not ceiling_group:
        print("⚠️ 没有找到 ceiling 组或该组为空")
        sys.exit(1)

    for hostname in ceiling_group:
        host_info = all_hosts.get(hostname)
        if not host_info:
            print(f"⚠️ 未找到主机 {hostname} 的详细信息，跳过")
            continue

        ansible_host = host_info.get("ansible_host")
        if not ansible_host:
            print(f"⚠️ 主机 {hostname} 缺少 ansible_host，跳过")
            continue

        target = f"{global_user}@{ansible_host}"
        print(f"🔧 正在修复 {hostname} ({target}) 的 Raw_Data 目录权限 ...")
        fix_remote_permissions(target)

if __name__ == "__main__":
    main()
