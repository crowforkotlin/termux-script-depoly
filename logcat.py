#!/data/data/com.termux/files/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Termux Logcat监控器 - 专门监控需要的包的日志
author: crowforkotlin
date: 2025-07-21

功能:
- 后台监控指定包的logcat日志
- 应用重启自动检测并恢复监控
- 文件大小200MB自动轮转
- 最多保留450个文件，自动删除最旧的
- 支持启动/停止/状态查看

使用方法:
    python /sdcard/log.py start    # 开始监控(后台)
    python /sdcard/log.py stop     # 停止监控
    python /sdcard/log.py status   # 查看状态
    python /sdcard/log.py fg       # 前台运行(调试用)
"""

import subprocess
import os
import signal
import sys
import time
import glob
import json
from datetime import datetime
from pathlib import Path
import argparse
import threading

# 配置常量
PACKAGE_NAME = "com.xxx.xxx"
LOG_DIR = "/sdcard/logcat_logs"
MAX_FILE_SIZE = 200 * 1024 * 1024  # 200MB
MAX_FILES = 450
PID_FILE = "/sdcard/logcat_logs/.logcat_monitor.pid"
STATUS_FILE = "/sdcard/logcat_logs/.monitor_status.json"

class LogcatMonitor:
    def __init__(self):
        self.package_name = PACKAGE_NAME
        self.log_dir = LOG_DIR
        self.max_file_size = MAX_FILE_SIZE
        self.max_files = MAX_FILES
        self.pid_file = PID_FILE
        self.status_file = STATUS_FILE

        self.current_file = None
        self.current_size = 0
        self.process = None
        self.running = False
        self.start_time = datetime.now()
        self.log_count = 0
        self.current_app_pid = None

        # 创建日志目录
        os.makedirs(self.log_dir, exist_ok=True)

    def log_message(self, message, level="INFO"):
        """输出带时间戳的消息"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] [{level}] {message}")

    def get_package_pid(self):
        """获取包名对应的PID"""
        try:
            # 方法1: 使用pidof命令
            result = subprocess.run(['pidof', self.package_name],
                                    capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split()
                return pids[0]

            # 方法2: 从ps命令获取
            result = subprocess.run(['ps', '-A'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if self.package_name in line:
                        parts = line.split()
                        if len(parts) >= 2:
                            return parts[1]  # PID通常在第二列

        except Exception as e:
            self.log_message(f"获取PID失败: {e}", "ERROR")

        return None

    def wait_for_app(self, max_wait=60):
        """等待应用启动（较短的等待时间）"""
        self.log_message(f"等待应用 {self.package_name} 启动...")

        wait_time = 0
        while wait_time < max_wait and self.running:
            pid = self.get_package_pid()
            if pid:
                self.log_message(f"检测到应用启动 (PID: {pid})")
                return pid

            time.sleep(2)
            wait_time += 2

        return None

    def create_new_logfile(self):
        """创建新的日志文件"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{self.package_name}_{timestamp}.log"
        filepath = os.path.join(self.log_dir, filename)

        # 关闭当前文件
        if self.current_file:
            self.current_file.close()

        self.current_file = open(filepath, 'w', encoding='utf-8', buffering=1)
        self.current_size = 0

        self.log_message(f"创建新日志文件: {filename}")

        # 写入文件头信息
        header = f"""# Logcat Monitor Log File
# Package: {self.package_name}
# Start Time: {datetime.now().isoformat()}
# Max File Size: {self.max_file_size/1024/1024:.0f}MB
# Max Files: {self.max_files}
# ==========================================

"""
        self.current_file.write(header)
        self.current_size += len(header.encode('utf-8'))

        # 清理旧文件
        self.cleanup_old_files()

    def cleanup_old_files(self):
        """清理超出数量限制的旧文件"""
        try:
            pattern = os.path.join(self.log_dir, f"{self.package_name}_*.log")
            log_files = glob.glob(pattern)

            # 按修改时间排序，最新的在前
            log_files.sort(key=os.path.getmtime, reverse=True)

            # 删除超出限制的文件
            deleted_count = 0
            if len(log_files) > self.max_files:
                files_to_delete = log_files[self.max_files:]
                for file_to_delete in files_to_delete:
                    try:
                        file_size = os.path.getsize(file_to_delete)
                        os.remove(file_to_delete)
                        deleted_count += 1
                        self.log_message(f"删除旧文件: {os.path.basename(file_to_delete)} "
                                         f"({file_size/1024/1024:.1f}MB)")
                    except Exception as e:
                        self.log_message(f"删除文件失败 {file_to_delete}: {e}", "ERROR")

            if deleted_count > 0:
                self.log_message(f"总共删除 {deleted_count} 个旧文件")

        except Exception as e:
            self.log_message(f"清理旧文件时出错: {e}", "ERROR")

    def write_log_line(self, line):
        """写入日志行"""
        if not self.current_file:
            self.create_new_logfile()

        # 添加时间戳
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        log_line = f"[{timestamp}] {line}\n"

        # 检查文件大小
        line_size = len(log_line.encode('utf-8'))
        if self.current_size + line_size > self.max_file_size:
            self.log_message(f"文件达到大小限制 ({self.current_size/1024/1024:.1f}MB)，切换新文件")
            self.create_new_logfile()

        # 写入日志
        try:
            self.current_file.write(log_line)
            self.current_file.flush()  # 确保立即写入
            self.current_size += line_size
            self.log_count += 1

        except Exception as e:
            self.log_message(f"写入日志失败: {e}", "ERROR")

    def write_app_event(self, event_type, pid=None):
        """写入应用事件日志"""
        if not self.current_file:
            self.create_new_logfile()

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

        if event_type == "APP_START":
            event_line = f"[{timestamp}] === APP STARTED: {self.package_name} (PID: {pid}) ===\n"
        elif event_type == "APP_STOP":
            event_line = f"[{timestamp}] === APP STOPPED: {self.package_name} (PID: {pid}) ===\n"
        elif event_type == "APP_RESTART":
            event_line = f"[{timestamp}] === APP RESTARTED: {self.package_name} (NEW PID: {pid}) ===\n"
        else:
            event_line = f"[{timestamp}] === {event_type} ===\n"

        try:
            self.current_file.write(event_line)
            self.current_file.flush()
            self.current_size += len(event_line.encode('utf-8'))
        except Exception as e:
            self.log_message(f"写入事件日志失败: {e}", "ERROR")

    def update_status(self):
        """更新状态文件"""
        status = {
            "package_name": self.package_name,
            "monitor_pid": os.getpid(),
            "app_pid": self.current_app_pid,
            "start_time": self.start_time.isoformat(),
            "current_time": datetime.now().isoformat(),
            "log_count": self.log_count,
            "current_file": os.path.basename(self.current_file.name) if self.current_file else None,
            "current_file_size": f"{self.current_size/1024/1024:.1f}MB",
            "running": self.running
        }

        try:
            with open(self.status_file, 'w') as f:
                json.dump(status, f, indent=2)
        except Exception as e:
            self.log_message(f"更新状态文件失败: {e}", "ERROR")

    def monitor_with_pid_tracking(self):
        """带PID跟踪的监控方法"""
        self.log_message("启动PID跟踪监控模式")

        while self.running:
            try:
                # 获取当前应用PID
                current_pid = self.get_package_pid()

                if not current_pid:
                    # 应用未运行，等待启动
                    if self.current_app_pid:
                        self.log_message(f"应用 {self.package_name} 已停止 (PID: {self.current_app_pid})")
                        self.write_app_event("APP_STOP", self.current_app_pid)
                        self.current_app_pid = None

                    # 等待应用启动
                    current_pid = self.wait_for_app(max_wait=30)
                    if not current_pid and self.running:
                        continue

                if current_pid and current_pid != self.current_app_pid:
                    # PID发生变化，应用重启了
                    if self.current_app_pid:
                        self.log_message(f"检测到应用重启: {self.current_app_pid} -> {current_pid}")
                        self.write_app_event("APP_RESTART", current_pid)
                    else:
                        self.log_message(f"应用启动: PID {current_pid}")
                        self.write_app_event("APP_START", current_pid)

                    self.current_app_pid = current_pid

                    # 如果有旧的logcat进程，先停止
                    if self.process:
                        try:
                            self.process.terminate()
                            self.process.wait(timeout=3)
                        except:
                            try:
                                self.process.kill()
                            except:
                                pass
                        self.process = None

                    # 启动新的logcat监控
                    self.start_logcat_for_pid(current_pid)

                # 检查logcat进程是否还在运行
                if self.process and self.process.poll() is not None:
                    self.log_message("logcat进程意外退出，重新启动")
                    self.process = None
                    if self.current_app_pid:
                        self.start_logcat_for_pid(self.current_app_pid)

                # 更新状态
                self.update_status()

                # 短暂休眠
                time.sleep(5)

            except Exception as e:
                self.log_message(f"PID跟踪过程出错: {e}", "ERROR")
                time.sleep(10)

    def start_logcat_for_pid(self, pid):
        """为指定PID启动logcat监控"""
        try:
            self.log_message(f"启动logcat监控 PID: {pid}")

            cmd = ['logcat', '--pid', pid, '-v', 'threadtime']
            self.process = subprocess.Popen(cmd,
                                            stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE,
                                            universal_newlines=True,
                                            bufsize=1)

            # 在后台线程中读取日志
            def read_logcat():
                try:
                    for line in iter(self.process.stdout.readline, ''):
                        if not self.running:
                            break

                        if line.strip():
                            self.write_log_line(line.strip())
                except Exception as e:
                    if self.running:  # 只在监控运行时才报告错误
                        self.log_message(f"读取logcat失败: {e}", "ERROR")

            # 启动读取线程
            logcat_thread = threading.Thread(target=read_logcat, daemon=True)
            logcat_thread.start()

        except Exception as e:
            self.log_message(f"启动logcat失败: {e}", "ERROR")
            self.process = None

    def monitor_logcat_fallback(self):
        """备用监控方法：使用包名过滤"""
        self.log_message("使用包名过滤监控模式")

        try:
            # 使用logcat + grep的方式过滤
            cmd = ['logcat', '-v', 'threadtime']
            self.process = subprocess.Popen(cmd,
                                            stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE,
                                            universal_newlines=True,
                                            bufsize=1)

            for line in iter(self.process.stdout.readline, ''):
                if not self.running:
                    break

                # 过滤包含包名的行
                if line.strip() and self.package_name in line:
                    self.write_log_line(line.strip())

        except Exception as e:
            self.log_message(f"备用监控失败: {e}", "ERROR")

    def start_monitoring(self, daemon=True):
        """开始监控"""
        if self.is_running():
            self.log_message("监控已在运行中")
            return False

        self.running = True

        # 后台运行
        if daemon:
            self.log_message("启动后台监控...")
            pid = os.fork()
            if pid > 0:
                self.log_message(f"后台进程PID: {pid}")
                return True

            # 子进程继续执行
            os.setsid()

            # 重定向输入输出到日志文件
            log_file = os.path.join(self.log_dir, "monitor.log")
            with open(log_file, 'a') as f:
                os.dup2(f.fileno(), sys.stdout.fileno())
                os.dup2(f.fileno(), sys.stderr.fileno())

            sys.stdin.close()

        # 保存PID
        self.save_pid()

        # 设置信号处理
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        self.log_message("=== Logcat监控启动 ===")
        self.log_message(f"包名: {self.package_name}")
        self.log_message(f"日志目录: {self.log_dir}")
        self.log_message(f"文件大小限制: {self.max_file_size/1024/1024:.0f}MB")
        self.log_message(f"最大文件数: {self.max_files}")

        try:
            # 首先尝试PID跟踪模式
            self.monitor_with_pid_tracking()
        except Exception as e:
            self.log_message(f"PID跟踪模式失败，切换到备用模式: {e}", "WARNING")
            try:
                self.monitor_logcat_fallback()
            except Exception as e2:
                self.log_message(f"备用监控也失败: {e2}", "ERROR")
        finally:
            self.stop_monitoring()

        return True

    def _signal_handler(self, signum, frame):
        """信号处理器"""
        self.log_message(f"收到信号 {signum}，正在停止监控...")
        self.stop_monitoring()
        sys.exit(0)

    def stop_monitoring(self):
        """停止监控"""
        self.running = False

        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            except:
                pass

        if self.current_file:
            # 写入监控结束事件
            try:
                self.write_app_event("MONITOR_STOP")
            except:
                pass
            self.current_file.close()

        # 更新最终状态
        self.update_status()

        # 删除PID文件
        try:
            if os.path.exists(self.pid_file):
                os.remove(self.pid_file)
        except:
            pass

        self.log_message("=== 监控已停止 ===")

    def save_pid(self):
        """保存当前进程PID"""
        try:
            with open(self.pid_file, 'w') as f:
                f.write(str(os.getpid()))
        except Exception as e:
            self.log_message(f"保存PID失败: {e}", "ERROR")

    def is_running(self):
        """检查是否已在运行"""
        try:
            if not os.path.exists(self.pid_file):
                return False

            with open(self.pid_file, 'r') as f:
                pid = int(f.read().strip())

            # 检查进程是否存在
            os.kill(pid, 0)
            return True

        except (OSError, ValueError, FileNotFoundError):
            # PID不存在或无效，删除PID文件
            try:
                if os.path.exists(self.pid_file):
                    os.remove(self.pid_file)
            except:
                pass
            return False

    def stop_existing(self):
        """停止现有的监控进程"""
        try:
            if not os.path.exists(self.pid_file):
                return False

            with open(self.pid_file, 'r') as f:
                pid = int(f.read().strip())

            self.log_message(f"正在停止监控进程 (PID: {pid})")

            # 发送终止信号
            os.kill(pid, signal.SIGTERM)
            time.sleep(3)

            # 检查是否还在运行
            try:
                os.kill(pid, 0)
                # 如果还在运行，强制杀死
                self.log_message("进程未响应，强制终止")
                os.kill(pid, signal.SIGKILL)
                time.sleep(1)
            except OSError:
                pass

            # 删除PID文件
            try:
                if os.path.exists(self.pid_file):
                    os.remove(self.pid_file)
            except:
                pass

            self.log_message("监控进程已停止")
            return True

        except (OSError, ValueError, FileNotFoundError) as e:
            self.log_message(f"停止进程失败: {e}", "ERROR")
            return False

    def show_status(self):
        """显示监控状态"""
        print("=== Logcat监控状态 ===")
        print(f"包名: {self.package_name}")
        print(f"日志目录: {self.log_dir}")

        if self.is_running():
            print("状态: 运行中 ✓")

            # 显示详细状态
            try:
                if os.path.exists(self.status_file):
                    with open(self.status_file, 'r') as f:
                        status = json.load(f)

                    start_time = datetime.fromisoformat(status['start_time'])
                    current_time = datetime.fromisoformat(status['current_time'])
                    duration = current_time - start_time

                    print(f"监控进程PID: {status['monitor_pid']}")
                    print(f"应用PID: {status['app_pid'] or '未运行'}")
                    print(f"运行时长: {duration}")
                    print(f"已记录日志: {status['log_count']} 行")
                    print(f"当前文件: {status['current_file']}")
                    print(f"当前文件大小: {status['current_file_size']}")

            except Exception as e:
                print(f"无法读取详细状态: {e}")

        else:
            print("状态: 未运行 ✗")

        # 显示日志文件信息
        try:
            pattern = os.path.join(self.log_dir, f"{self.package_name}_*.log")
            log_files = glob.glob(pattern)
            log_files.sort(key=os.path.getmtime, reverse=True)

            print(f"\n日志文件: {len(log_files)} 个")

            if log_files:
                total_size = sum(os.path.getsize(f) for f in log_files)
                print(f"总大小: {total_size/1024/1024:.1f}MB")

                print("\n最新的5个文件:")
                for i, log_file in enumerate(log_files[:5]):
                    size = os.path.getsize(log_file)
                    mtime = datetime.fromtimestamp(os.path.getmtime(log_file))
                    print(f"  {i+1}. {os.path.basename(log_file)} "
                          f"({size/1024/1024:.1f}MB, {mtime.strftime('%m-%d %H:%M')})")

        except Exception as e:
            print(f"无法读取日志文件信息: {e}")

        print("=" * 40)


def check_dependencies():
    """检查并提示安装依赖"""
    print("检查Termux环境...")

    # 检查Python版本
    if sys.version_info < (3, 6):
        print("错误: 需要Python 3.6或更高版本")
        print("请运行: pkg install python")
        return False

    print(f"Python版本: {sys.version}")

    # 检查必要的系统命令
    required_commands = ['logcat', 'pidof', 'ps']
    missing_commands = []

    for cmd in required_commands:
        try:
            subprocess.run([cmd, '--help'], capture_output=True, timeout=5)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            try:
                subprocess.run(['which', cmd], capture_output=True, check=True)
            except subprocess.CalledProcessError:
                missing_commands.append(cmd)

    if missing_commands:
        print(f"错误: 缺少必要命令: {', '.join(missing_commands)}")
        print("请运行: pkg install android-tools")
        return False

    print("依赖检查通过 ✓")
    return True


def show_help():
    """显示帮助信息"""
    print(__doc__)
    print("\n安装依赖:")
    print("  pkg update && pkg install python android-tools")
    print("\n日志文件位置:")
    print(f"  {LOG_DIR}/")
    print(f"  监控日志: {LOG_DIR}/monitor.log")
    print("\n特性:")
    print("  ✓ 应用重启自动检测和恢复监控")
    print("  ✓ PID变化跟踪")
    print("  ✓ 应用启动/停止事件记录")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='Logcat监控器 - 监控com.log.ymtest包')
    parser.add_argument('action', nargs='?', default='help',
                        choices=['start', 'stop', 'status', 'fg', 'check', 'help'],
                        help='操作: start(后台启动), stop(停止), status(状态), fg(前台运行), check(检查依赖)')

    args = parser.parse_args()

    if args.action == 'help':
        show_help()
        return

    if args.action == 'check':
        check_dependencies()
        return

    # 检查依赖
    if not check_dependencies():
        print("\n请先安装依赖:")
        print("pkg update && pkg install python android-tools")
        sys.exit(1)

    monitor = LogcatMonitor()

    if args.action == 'start':
        if monitor.start_monitoring(daemon=True):
            print("后台监控已启动")
        else:
            print("启动失败")
            sys.exit(1)

    elif args.action == 'fg':
        print("前台模式启动...")
        monitor.start_monitoring(daemon=False)

    elif args.action == 'stop':
        if monitor.stop_existing():
            print("监控已停止")
        else:
            print("没有找到运行中的监控进程")

    elif args.action == 'status':
        monitor.show_status()


if __name__ == "__main__":
    main()