#!/usr/bin/env python3
import subprocess
import sys
import yaml

def load_inventory(inventory_file):
    try:
        with open(inventory_file, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"❌ 加载 inventory 文件失败: {e}")
        sys.exit(1)

def extract_hosts_from_group(inventory, group_name):
    """提取组内主机名列表"""
    children = inventory.get("all", {}).get("children", {})
    group = children.get(group_name, {})
    hosts = group.get("hosts", {})
    return list(hosts.keys())

def run_check_and_kill(target, user):
    ssh_prefix = f"{user}@{target}"
    check_cmd = "sudo lsof -i :5555 -t"

    try:
        # 通过 SSH 执行检查命令
        result = subprocess.run(
            ["ssh", ssh_prefix, check_cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5
        )

        if result.stdout.strip():
            pids = result.stdout.strip().splitlines()
            print(f"💡 [{ssh_prefix}] 监听端口的进程 PID: {', '.join(pids)}")

            for pid in pids:
                kill_cmd = f"sudo kill -9 {pid}"
                subprocess.run(["ssh", ssh_prefix, kill_cmd])
                print(f"🗡️  [{ssh_prefix}] 已终止 PID {pid}")
        else:
            print(f"✅ [{ssh_prefix}] 无监听 50001 的进程，跳过。")

    except subprocess.TimeoutExpired:
        print(f"⚠️  [{ssh_prefix}] SSH 超时，跳过。")
    except Exception as e:
        print(f"❌ [{ssh_prefix}] 执行出错: {e}")

def main():
    inventory_file = "inventory.yaml"
    group_name = "ceiling"

    inventory = load_inventory(inventory_file)
    global_user = inventory.get("all", {}).get("vars", {}).get("ansible_user", "pi")
    all_hosts = inventory.get("all", {}).get("hosts", {})

    rx_names = extract_hosts_from_group(inventory, group_name)

    for name in rx_names:
        host_info = all_hosts.get(name, {})
        ansible_host = host_info.get("ansible_host")
        if not ansible_host:
            print(f"⚠️  跳过 {name}，未找到 ansible_host。")
            continue
        run_check_and_kill(ansible_host, global_user)

    print("🎉 所有设备端口检查与清理完成。")

if __name__ == "__main__":
    main()
