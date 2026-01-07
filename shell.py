#!/usr/bin/env python3
"""
增强型文件系统命令行界面
集成了三大扩展功能的完整操作界面
"""

import os
import sys
import cmd
import time
import json
from datetime import datetime
from typing import List, Dict, Any

# 导入文件系统类
try:
    from enhanced_fs import EnhancedFileSystem
    from base_fs import SimpleFileSystem
    from constants import FileType, OperationType
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保所有文件都在同一目录下")
    sys.exit(1)


class FileSystemShell(cmd.Cmd):
    """增强型文件系统命令行解释器"""

    intro = """
╔══════════════════════════════════════════════════════════════════════╗
║                 增强型文件系统 v3.0 - 操作系统大作业                 ║
║                                                                      ║
║  集成三大扩展功能：                                                  ║
║    1. 🛡️  事务日志与崩溃恢复                                         ║
║    2. 📚 文件版本控制                                                ║
║    3. 🔐 文件加密/压缩                                               ║
║                                                                      ║
║  输入 'help' 查看命令列表，'demo' 查看功能演示                       ║
╚══════════════════════════════════════════════════════════════════════╝
"""

    prompt = "efs> "

    def __init__(self):
        super().__init__()
        self.fs = None
        self._init_filesystem()

    def _init_filesystem(self):
        """初始化文件系统"""
        print("\n正在初始化增强型文件系统...")

        try:
            # 创建启用所有功能的文件系统
            self.fs = EnhancedFileSystem(
                disk_size_mb=10,
                enable_logging=True,
                enable_versions=True,
                enable_crypto=True
            )

            print("✅ 文件系统初始化成功！")
            print(f"   磁盘大小: {self.fs.disk_size / (1024 * 1024):.1f} MB")
            print(f"   块大小: {self.fs.block_size / 1024:.1f} KB")
            print(f"   总块数: {self.fs.block_count}")
            print(f"   启用功能: 事务日志、版本控制、加密压缩")

            # 显示系统状态
            self._show_system_status()

        except Exception as e:
            print(f"❌ 文件系统初始化失败: {e}")
            print("尝试使用基础文件系统...")
            self.fs = SimpleFileSystem()

    def _show_system_status(self):
        """显示系统状态"""
        stats = self.fs.get_system_stats()
        print(f"\n系统状态:")
        print(f"   用户: {self.fs.current_user}")
        print(f"   当前目录: inode {self.fs.current_dir}")
        print(f"   磁盘使用: {stats['disk_usage']['used_blocks']}/{stats['disk_usage']['total_blocks']} 块")

    # ========== 基本文件操作命令 ==========

    def do_init(self, arg):
        """重新初始化文件系统: INIT"""
        self._init_filesystem()

    def do_login(self, arg):
        """用户登录: LOGIN <用户名> <密码>"""
        args = arg.split()
        if len(args) != 2:
            print("用法: login <用户名> <密码>")
            return

        username, password = args
        if self.fs.login(username, password):
            print(f"✅ 用户 {username} 登录成功！")
            self._show_system_status()
        else:
            print("❌ 登录失败：用户名或密码错误")

    def do_logout(self, arg):
        """用户登出: LOGOUT"""
        self.fs.logout()
        print("✅ 已登出")

    def do_users(self, arg):
        """显示所有用户: USERS"""
        print("\n系统用户列表:")
        print("─" * 40)
        for i, (user, _) in enumerate(self.fs.users.items(), 1):
            current_marker = " (当前)" if user == self.fs.current_user else ""
            print(f"  {i:2d}. {user}{current_marker}")
        print("─" * 40)
        print(f"总计: {len(self.fs.users)} 个用户")

    def do_create(self, arg):
        """创建文件: CREATE <文件名>"""
        if not arg:
            print("用法: create <文件名>")
            return

        if self.fs.create_file(arg):
            print(f"✅ 文件 '{arg}' 创建成功")
        else:
            print(f"❌ 创建文件失败：权限不足或文件已存在")

    def do_mkdir(self, arg):
        """创建目录: MKDIR <目录名>"""
        if not arg:
            print("用法: mkdir <目录名>")
            return

        if self.fs.create_directory(arg):
            print(f"✅ 目录 '{arg}' 创建成功")
        else:
            print(f"❌ 创建目录失败：权限不足或目录已存在")

    def do_ls(self, arg):
        """列出目录内容: LS [路径]"""
        path = arg if arg else "."

        try:
            items = self.fs.list_directory(path)
        except Exception as e:
            print(f"❌ 列出目录失败: {e}")
            return

        if not items:
            print(f"目录 '{path}' 为空或不存在")
            return

        print(f"\n目录 '{path}' 内容:")
        print("─" * 90)
        print(f"{'权限':<10} {'大小':<8} {'版本':<4} {'加密':<3} {'压缩':<3} {'所有者':<8} {'修改时间':<16}  名称")
        print("─" * 90)

        # 获取inode以检查特殊属性
        for item in items:
            # 构建完整路径以查找inode
            full_path = f"{path}/{item['name']}" if path != "." else item['name']
            inode_id = self.fs._find_inode_by_path(full_path)

            # 检查属性
            encrypted = "🔒" if hasattr(self.fs, 'encrypted_files') and inode_id in self.fs.encrypted_files else " "
            compressed = "📦" if hasattr(self.fs, 'compressed_files') and inode_id in self.fs.compressed_files else " "

            # 检查版本数
            version_count = 0
            if hasattr(self.fs, 'version_manager') and inode_id:
                versions = self.fs.version_manager.list_versions(inode_id)
                version_count = len(versions)

            size_str = f"{item['size']}B" if item['type'] == '-' else "<DIR>"

            print(f"{item['permissions']:<10} {size_str:<8} "
                  f"{version_count:<4} {encrypted:<3} {compressed:<3} "
                  f"{item['owner']:<8} {item['modified']:<16}  {item['name']}")

        print("─" * 90)
        print(f"总计: {len(items)} 个项目")

    def do_rm(self, arg):
        """删除文件或目录: RM <路径>"""
        if not arg:
            print("用法: rm <文件或目录>")
            return

        # 确认删除
        confirm = input(f"确定要删除 '{arg}' 吗？(y/N): ")
        if confirm.lower() != 'y':
            print("取消删除")
            return

        if self.fs.delete(arg):
            print(f"✅ '{arg}' 已删除")
        else:
            print(f"❌ 删除失败：文件/目录不存在、非空或权限不足")

    def do_cat(self, arg):
        """显示文件内容: CAT <文件名>"""
        if not arg:
            print("用法: cat <文件名>")
            return

        # 打开文件
        fd = self.fs.open_file(arg, "r")
        if fd is None:
            print(f"❌ 无法打开文件 '{arg}'")
            return

        print(f"\n文件 '{arg}' 内容:")
        print("═" * 60)

        # 读取并显示内容
        total_bytes = 0
        try:
            while True:
                data = self.fs.read_file(fd, 1024)
                if not data:
                    break

                # 尝试解码为文本
                try:
                    text = data.decode('utf-8')
                    print(text, end='')
                except UnicodeDecodeError:
                    # 二进制数据，显示十六进制
                    hex_str = data.hex()
                    for i in range(0, len(hex_str), 32):
                        print(hex_str[i:i + 32])

                total_bytes += len(data)
        except Exception as e:
            print(f"\n读取错误: {e}")

        print("\n" + "═" * 60)
        print(f"总计: {total_bytes} 字节")

        # 关闭文件
        self.fs.close_file(fd)

    # ========== 版本控制命令 ==========

    def do_versions(self, arg):
        """列出文件的所有版本: VERSIONS <文件路径>"""
        if not arg:
            print("用法: versions <文件路径>")
            return

        if not hasattr(self.fs, 'list_file_versions'):
            print("❌ 版本控制功能未启用")
            return

        versions = self.fs.list_file_versions(arg)
        if not versions:
            print(f"文件 '{arg}' 没有版本历史或不存在")
            return

        print(f"\n文件 '{arg}' 的版本历史:")
        print("─" * 80)
        print(f"{'序号':<4} {'版本ID':<12} {'时间':<20} {'作者':<10} {'大小':<8} {'备注':<20}")
        print("─" * 80)

        for i, ver in enumerate(versions, 1):
            time_str = datetime.fromtimestamp(ver['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
            size_str = f"{ver['size']}B"
            comment = ver.get('comment', '')[:20]
            print(f"{i:<4} {ver['id'][:12]:<12} {time_str:<20} {ver['author']:<10} "
                  f"{size_str:<8} {comment:<20}")

        print("─" * 80)
        print(f"总计: {len(versions)} 个版本")

    def do_restore(self, arg):
        """恢复到指定版本: RESTORE <文件路径> <版本ID或序号>"""
        args = arg.split()
        if len(args) != 2:
            print("用法: restore <文件路径> <版本ID或序号>")
            return

        path, version_ref = args

        if not hasattr(self.fs, 'restore_version'):
            print("❌ 版本控制功能未启用")
            return

        # 检查版本引用是ID还是序号
        versions = self.fs.list_file_versions(path)
        if not versions:
            print(f"文件 '{path}' 没有版本历史")
            return

        version_id = version_ref
        if version_ref.isdigit():
            index = int(version_ref) - 1
            if 0 <= index < len(versions):
                version_id = versions[index]['id']
            else:
                print(f"❌ 无效的版本序号: {version_ref}")
                return

        # 执行恢复
        if self.fs.restore_version(path, version_id):
            print(f"✅ 文件 '{path}' 已成功恢复到版本 {version_id}")
        else:
            print("❌ 恢复失败")

    def do_diff(self, arg):
        """比较两个版本: DIFF <文件路径> <版本1> <版本2>"""
        args = arg.split()
        if len(args) != 3:
            print("用法: diff <文件路径> <版本1> <版本2>")
            print("      版本可以是版本ID或序号")
            return

        path, ver1_ref, ver2_ref = args

        if not hasattr(self.fs, 'compare_versions'):
            print("❌ 版本控制功能未启用")
            return

        # 获取版本列表
        versions = self.fs.list_file_versions(path)
        if not versions:
            print(f"文件 '{path}' 没有版本历史")
            return

        # 解析版本引用
        def resolve_version(ref):
            if ref.isdigit():
                index = int(ref) - 1
                if 0 <= index < len(versions):
                    return versions[index]['id']
            return ref

        ver1_id = resolve_version(ver1_ref)
        ver2_id = resolve_version(ver2_ref)

        # 执行比较
        result = self.fs.compare_versions(path, ver1_id, ver2_id)

        if 'error' in result:
            print(f"❌ 错误: {result['error']}")
            return

        print(f"\n版本比较: {ver1_id[:8]} ←→ {ver2_id[:8]}")
        print("─" * 50)

        if result.get('binary', False):
            print(f"  二进制文件比较:")
            print(f"    版本1大小: {result['size1']} 字节")
            print(f"    版本2大小: {result['size2']} 字节")
            print(f"    大小差异: {result['size_diff']:+d} 字节")
        else:
            print(f"  文本文件比较:")
            print(f"    新增行数: {result['added_lines']}")
            print(f"    删除行数: {result['removed_lines']}")
            print(f"    总变更数: {result['total_changes']}")

            if result['sample_diff']['added']:
                print(f"\n  示例新增内容:")
                for line in result['sample_diff']['added']:
                    print(f"    + {line}")

            if result['sample_diff']['removed']:
                print(f"\n  示例删除内容:")
                for line in result['sample_diff']['removed']:
                    print(f"    - {line}")

        print("─" * 50)

    def do_export(self, arg):
        """导出文件的所有版本: EXPORT <文件路径> [导出目录]"""
        args = arg.split()
        if len(args) < 1:
            print("用法: export <文件路径> [导出目录]")
            return

        path = args[0]
        export_dir = args[1] if len(args) > 1 else f"export_{os.path.basename(path)}"

        if not hasattr(self.fs, 'export_versions'):
            print("❌ 版本控制功能未启用")
            return

        if self.fs.export_versions(path, export_dir):
            print(f"✅ 版本已导出到目录: {export_dir}")
        else:
            print("❌ 导出失败")

    # ========== 加密压缩命令 ==========

    def do_encrypt(self, arg):
        """启用文件加密: ENCRYPT <文件路径>"""
        if not arg:
            print("用法: encrypt <文件路径>")
            return

        if not hasattr(self.fs, 'enable_file_encryption'):
            print("❌ 加密功能未启用")
            return

        if self.fs.enable_file_encryption(arg, True):
            print(f"✅ 文件 '{arg}' 已启用加密")
        else:
            print("❌ 启用加密失败")

    def do_decrypt(self, arg):
        """禁用文件加密: DECRYPT <文件路径>"""
        if not arg:
            print("用法: decrypt <文件路径>")
            return

        if not hasattr(self.fs, 'enable_file_encryption'):
            print("❌ 加密功能未启用")
            return

        if self.fs.enable_file_encryption(arg, False):
            print(f"✅ 文件 '{arg}' 已禁用加密")
        else:
            print("❌ 禁用加密失败")

    def do_compress(self, arg):
        """启用文件压缩: COMPRESS <文件路径>"""
        if not arg:
            print("用法: compress <文件路径>")
            return

        if not hasattr(self.fs, 'enable_file_compression'):
            print("❌ 压缩功能未启用")
            return

        if self.fs.enable_file_compression(arg, True):
            print(f"✅ 文件 '{arg}' 已启用压缩")
        else:
            print("❌ 启用压缩失败")

    def do_decompress(self, arg):
        """禁用文件压缩: DECOMPRESS <文件路径>"""
        if not arg:
            print("用法: decompress <文件路径>")
            return

        if not hasattr(self.fs, 'enable_file_compression'):
            print("❌ 压缩功能未启用")
            return

        if self.fs.enable_file_compression(arg, False):
            print(f"✅ 文件 '{arg}' 已禁用压缩")
        else:
            print("❌ 禁用压缩失败")

    def do_writex(self, arg):
        """高级写入文件: WRITEX <fd> <内容> [--encrypt] [--compress]"""
        args = arg.split()
        if len(args) < 2:
            print("用法: writex <fd> <内容> [--encrypt] [--compress]")
            return

        fd_str = args[0]
        if not fd_str.isdigit():
            print("❌ 文件描述符必须是数字")
            return

        fd = int(fd_str)

        # 解析选项
        encrypt = "--encrypt" in args
        compress = "--compress" in args

        # 提取内容（排除选项）
        content_parts = []
        for part in args[1:]:
            if part not in ["--encrypt", "--compress"]:
                content_parts.append(part)

        content = " ".join(content_parts)

        if not hasattr(self.fs, 'write_file'):
            print("❌ 写入功能不可用")
            return

        # 执行写入
        result = self.fs.write_file(
            fd, content.encode('utf-8'),
            create_version=True,
            encrypt=encrypt,
            compress=compress
        )

        if result:
            options = []
            if encrypt: options.append("加密")
            if compress: options.append("压缩")
            option_str = "、".join(options) if options else "无特殊处理"
            print(f"✅ 写入成功 ({option_str})")
        else:
            print("❌ 写入失败")

    # ========== 文件操作命令 ==========

    def do_open(self, arg):
        """打开文件: OPEN <文件名> <模式[r|w|a|r+|w+|a+]>"""
        args = arg.split()
        if len(args) < 1:
            print("用法: open <文件名> [模式]")
            return

        filename = args[0]
        mode = args[1] if len(args) > 1 else "r"

        fd = self.fs.open_file(filename, mode)
        if fd is not None:
            print(f"✅ 文件 '{filename}' 已打开，文件描述符: {fd}")
        else:
            print(f"❌ 打开文件失败：文件不存在或权限不足")

    def do_close(self, arg):
        """关闭文件: CLOSE <文件描述符>"""
        if not arg.isdigit():
            print("用法: close <文件描述符>")
            return

        fd = int(arg)
        if self.fs.close_file(fd):
            print(f"✅ 文件描述符 {fd} 已关闭")
        else:
            print(f"❌ 关闭文件失败：文件描述符无效")

    def do_read(self, arg):
        """读取文件: READ <文件描述符> [字节数]"""
        args = arg.split()
        if len(args) < 1:
            print("用法: read <文件描述符> [字节数]")
            return

        if not args[0].isdigit():
            print("❌ 文件描述符必须是数字")
            return

        fd = int(args[0])
        size = int(args[1]) if len(args) > 1 else 1024

        data = self.fs.read_file(fd, size)
        if data is not None:
            if data:
                print(f"\n读取 {len(data)} 字节:")
                print("─" * 50)
                try:
                    print(data.decode('utf-8'))
                except UnicodeDecodeError:
                    # 显示十六进制
                    hex_str = data.hex()
                    for i in range(0, len(hex_str), 64):
                        print(hex_str[i:i + 64])
                print("─" * 50)
            else:
                print("📄 已到达文件末尾")
        else:
            print("❌ 读取失败：文件描述符无效或权限不足")

    def do_write(self, arg):
        """写入文件: WRITE <文件描述符> <内容>"""
        args = arg.split(maxsplit=1)
        if len(args) < 2:
            print("用法: write <文件描述符> <内容>")
            return

        if not args[0].isdigit():
            print("❌ 文件描述符必须是数字")
            return

        fd = int(args[0])
        content = args[1].encode('utf-8')

        if self.fs.write_file(fd, content):
            print(f"✅ 写入 {len(content)} 字节成功")
        else:
            print("❌ 写入失败：文件描述符无效或权限不足")

    def do_seek(self, arg):
        """移动文件指针: SEEK <文件描述符> <偏移> [0|1|2]"""
        args = arg.split()
        if len(args) < 2:
            print("用法: seek <文件描述符> <偏移> [whence]")
            print("  whence: 0=开头, 1=当前位置, 2=末尾")
            return

        if not args[0].isdigit() or not args[1].isdigit():
            print("❌ 文件描述符和偏移必须是数字")
            return

        fd = int(args[0])
        offset = int(args[1])
        whence = int(args[2]) if len(args) > 2 else 0

        new_pos = self.fs.seek_file(fd, offset, whence)
        if new_pos is not None:
            print(f"✅ 文件指针已移动到位置: {new_pos}")
        else:
            print("❌ 移动文件指针失败")

    def do_cp(self, arg):
        """复制文件: CP <源文件> <目标文件>"""
        args = arg.split()
        if len(args) != 2:
            print("用法: cp <源文件> <目标文件>")
            return

        src, dst = args

        # 打开源文件
        src_fd = self.fs.open_file(src, "r")
        if src_fd is None:
            print(f"❌ 无法打开源文件 '{src}'")
            return

        # 创建目标文件
        if not self.fs.create_file(dst):
            print(f"❌ 无法创建目标文件 '{dst}'")
            self.fs.close_file(src_fd)
            return

        # 打开目标文件
        dst_fd = self.fs.open_file(dst, "w")
        if dst_fd is None:
            print(f"❌ 无法打开目标文件 '{dst}'")
            self.fs.close_file(src_fd)
            return

        # 复制数据
        total_bytes = 0
        try:
            while True:
                data = self.fs.read_file(src_fd, 4096)
                if data is None or not data:
                    break

                if not self.fs.write_file(dst_fd, data):
                    print("❌ 写入目标文件失败")
                    break

                total_bytes += len(data)
        except Exception as e:
            print(f"❌ 复制过程中出错: {e}")

        # 关闭文件
        self.fs.close_file(src_fd)
        self.fs.close_file(dst_fd)

        print(f"✅ 文件复制完成: {src} → {dst} ({total_bytes} 字节)")

    # ========== 系统管理命令 ==========

    def do_stats(self, arg):
        """显示系统统计信息: STATS"""
        if not hasattr(self.fs, 'get_system_stats'):
            print("❌ 统计功能不可用")
            return

        stats = self.fs.get_system_stats()

        print("\n📊 系统统计信息:")
        print("═" * 60)

        # 磁盘使用情况
        du = stats['disk_usage']
        usage_percent = (du['used_blocks'] / du['total_blocks']) * 100

        print("💾 磁盘使用:")
        print(f"   总空间: {du['total_size_mb']:.1f} MB")
        print(f"   已用空间: {du['used_size_mb']:.1f} MB")
        print(f"   空闲空间: {du['total_size_mb'] - du['used_size_mb']:.1f} MB")
        print(f"   使用率: {du['used_blocks']}/{du['total_blocks']} 块 ({usage_percent:.1f}%)")

        # 操作统计
        if 'operation_stats' in stats:
            ops = stats['operation_stats']
            print(f"\n🔄 操作统计:")
            print(f"   读取: {ops['reads']} 次")
            print(f"   写入: {ops['writes']} 次")
            print(f"   打开: {ops['opens']} 次")
            print(f"   创建: {ops['creates']} 次")
            print(f"   删除: {ops['deletes']} 次")

        # 文件统计
        if 'file_counts' in stats:
            fc = stats['file_counts']
            print(f"\n📁 文件统计:")
            print(f"   总inode数: {fc['total_inodes']}")
            print(f"   加密文件: {fc['encrypted_files']}")
            print(f"   压缩文件: {fc['compressed_files']}")

        # 版本控制统计
        if 'version_stats' in stats:
            vs = stats['version_stats']
            print(f"\n📚 版本控制:")
            print(f"   有版本的文件数: {vs['total_files_with_versions']}")
            print(f"   总版本数: {vs['total_versions']}")
            print(f"   平均版本数/文件: {vs['avg_versions_per_file']:.1f}")
            print(f"   版本存储: {vs['total_storage_bytes']} 字节")

        # 加密压缩统计
        if 'crypto_stats' in stats:
            cs = stats['crypto_stats']
            print(f"\n🔐 加密压缩:")
            print(f"   压缩率: {cs['compression_ratio']}")
            print(f"   节省空间: {cs['space_saved']} 字节")
            print(f"   加密次数: {cs['encryption_count']}")
            print(f"   压缩次数: {cs['compression_count']}")
            if 'encryption_available' in cs:
                status = "可用" if cs['encryption_available'] else "不可用"
                print(f"   加密库: {status}")

        # 缓存统计
        if 'cache_stats' in stats:
            cache = stats['cache_stats']
            print(f"\n⚡ 缓存统计:")
            print(f"   缓存大小: {cache['size']}/{cache['capacity']}")
            print(f"   命中率: {cache['hit_rate']}")
            print(f"   命中: {cache['hits']} 次")
            print(f"   未命中: {cache['misses']} 次")

        print("═" * 60)

    def do_recover(self, arg):
        """手动触发崩溃恢复: RECOVER"""
        if not hasattr(self.fs, 'manual_recovery'):
            print("❌ 事务日志功能未启用")
            return

        recovered = self.fs.manual_recovery()
        if recovered > 0:
            print(f"✅ 崩溃恢复完成，重做了 {recovered} 个操作")
        else:
            print("✅ 没有需要恢复的操作")

    def do_save(self, arg):
        """保存文件系统: SAVE [文件名]"""
        filename = arg if arg else "filesystem_backup.json"

        if not hasattr(self.fs, 'save_to_file'):
            print("❌ 保存功能不可用")
            return

        self.fs.save_to_file(filename)
        print(f"✅ 文件系统已保存到 '{filename}'")

    def do_load(self, arg):
        """加载文件系统: LOAD <文件名>"""
        if not arg:
            print("用法: load <文件名>")
            return

        if not hasattr(self.fs, 'load_from_file'):
            print("❌ 加载功能不可用")
            return

        if self.fs.load_from_file(arg):
            print(f"✅ 文件系统已从 '{arg}' 加载")
        else:
            print("❌ 加载文件系统失败")

    def do_info(self, arg):
        """显示文件信息: INFO <文件路径>"""
        if not arg:
            print("用法: info <文件路径>")
            return

        if not hasattr(self.fs, 'get_file_info'):
            print("❌ 信息功能不可用")
            return

        info = self.fs.get_file_info(arg)
        if info:
            print(f"\n📄 文件信息: {info['path']}")
            print("─" * 50)
            print(f"  Inode ID: {info['inode_id']}")
            print(f"  类型: {info['type']}")
            print(f"  大小: {info['size']} 字节")
            print(f"  数据块: {info['blocks']} 个")
            print(f"  所有者: {info['owner']}")
            print(f"  组: {info['group']}")
            print(f"  权限: {info['permissions']} ({info['permissions_octal']})")
            print(f"  创建时间: {info['created']}")
            print(f"  修改时间: {info['modified']}")
            print(f"  访问时间: {info['accessed']}")
            print(f"  链接数: {info['link_count']}")
            print("─" * 50)
        else:
            print(f"❌ 文件 '{arg}' 不存在")

    def do_chmod(self, arg):
        """修改文件权限: CHMOD <文件路径> <权限>"""
        args = arg.split()
        if len(args) != 2:
            print("用法: chmod <文件路径> <权限>")
            print("      权限可以是八进制(如755)或符号(如u+rwx)")
            return

        path, mode_str = args

        # 解析权限
        try:
            if mode_str.isdigit():
                # 八进制权限
                mode = int(mode_str, 8)
            else:
                # 符号权限（简化实现）
                mode = self._parse_symbolic_mode(mode_str)
        except ValueError:
            print("❌ 无效的权限格式")
            return

        if self.fs.change_permissions(path, mode):
            print(f"✅ 文件 '{path}' 权限已修改为 {oct(mode)}")
        else:
            print(f"❌ 修改权限失败")

    def _parse_symbolic_mode(self, mode_str: str) -> int:
        """解析符号权限表示"""
        # 简化实现，只处理基本格式
        if mode_str == "a+rwx":
            return 0o777
        elif mode_str == "u+rwx,g+rx,o+rx":
            return 0o755
        elif mode_str == "u+rw,go+r":
            return 0o644
        else:
            return 0o644  # 默认

    # ========== 演示和帮助命令 ==========

    def do_demo(self, arg):
        """运行功能演示: DEMO"""
        print("\n🚀 开始增强功能演示...")
        print("═" * 60)

        # 演示1: 基本文件操作
        print("\n1. 📝 基本文件操作演示")
        print("   - 创建测试文件")
        self.fs.create_file("demo_test.txt")

        print("   - 写入内容")
        fd = self.fs.open_file("demo_test.txt", "w")
        self.fs.write_file(fd, b"这是演示文件的内容\n")
        self.fs.close_file(fd)

        print("   - 读取内容")
        fd = self.fs.open_file("demo_test.txt", "r")
        data = self.fs.read_file(fd, 100)
        self.fs.close_file(fd)
        print(f"     读取到: {data.decode('utf-8').strip()}")

        # 演示2: 版本控制
        if hasattr(self.fs, 'list_file_versions'):
            print("\n2. 📚 版本控制演示")
            print("   - 创建多个版本")
            fd = self.fs.open_file("demo_test.txt", "a")
            self.fs.write_file(fd, b"版本2: 添加更多内容\n", create_version=True)
            self.fs.write_file(fd, b"版本3: 最后的内容\n", create_version=True)
            self.fs.close_file(fd)

            versions = self.fs.list_file_versions("demo_test.txt")
            print(f"   - 文件现在有 {len(versions)} 个版本")

        # 演示3: 加密压缩
        if hasattr(self.fs, 'enable_file_encryption'):
            print("\n3. 🔐 加密压缩演示")
            print("   - 启用文件加密")
            self.fs.enable_file_encryption("demo_test.txt", True)

            print("   - 写入加密内容")
            fd = self.fs.open_file("demo_test.txt", "a")
            self.fs.write_file(fd, b"加密的机密内容\n", encrypt=True)
            self.fs.close_file(fd)

            print("   - 启用文件压缩")
            self.fs.enable_file_compression("demo_test.txt", True)

            print("   - 写入压缩内容")
            fd = self.fs.open_file("demo_test.txt", "a")
            self.fs.write_file(fd, b"压缩的可重复内容" * 10, compress=True)
            self.fs.close_file(fd)

        # 演示4: 系统统计
        if hasattr(self.fs, 'get_system_stats'):
            print("\n4. 📊 系统统计演示")
            stats = self.fs.get_system_stats()
            print(f"   - 磁盘使用: {stats['disk_usage']['used_blocks']}/{stats['disk_usage']['total_blocks']} 块")

            if 'operation_stats' in stats:
                ops = stats['operation_stats']
                print(f"   - 操作次数: 读取{ops['reads']}, 写入{ops['writes']}")

        print("\n═" * 60)
        print("✅ 演示完成！")
        print("   使用 'stats' 查看详细统计信息")
        print("   使用 'versions demo_test.txt' 查看版本历史")
        print("   使用 'info demo_test.txt' 查看文件信息")

    def do_help(self, arg):
        """显示帮助信息: HELP [命令]"""
        if arg:
            # 显示特定命令的帮助
            super().do_help(arg)
        else:
            print("\n📖 增强型文件系统命令帮助:")
            print("═" * 70)

            categories = [
                ("系统命令", [
                    ("init", "重新初始化文件系统"),
                    ("login <用户> <密码>", "用户登录"),
                    ("logout", "用户登出"),
                    ("users", "显示所有用户"),
                    ("stats", "显示系统统计"),
                    ("save [文件]", "保存文件系统"),
                    ("load <文件>", "加载文件系统"),
                    ("recover", "手动触发崩溃恢复"),
                ]),
                ("文件/目录操作", [
                    ("create <文件>", "创建文件"),
                    ("mkdir <目录>", "创建目录"),
                    ("ls [路径]", "列出目录内容"),
                    ("rm <路径>", "删除文件/目录"),
                    ("cat <文件>", "显示文件内容"),
                    ("cp <源> <目标>", "复制文件"),
                    ("info <文件>", "显示文件详细信息"),
                    ("chmod <文件> <权限>", "修改文件权限"),
                ]),
                ("版本控制系统", [
                    ("versions <文件>", "列出文件版本历史"),
                    ("restore <文件> <版本ID>", "恢复到指定版本"),
                    ("diff <文件> <版本1> <版本2>", "比较两个版本"),
                    ("export <文件> [目录]", "导出所有版本"),
                ]),
                ("加密压缩功能", [
                    ("encrypt <文件>", "启用文件加密"),
                    ("decrypt <文件>", "禁用文件加密"),
                    ("compress <文件>", "启用文件压缩"),
                    ("decompress <文件>", "禁用文件压缩"),
                    ("writex <fd> <内容> [--encrypt] [--compress]", "高级写入"),
                ]),
                ("文件内容操作", [
                    ("open <文件> [模式]", "打开文件"),
                    ("close <fd>", "关闭文件"),
                    ("read <fd> [大小]", "读取文件"),
                    ("write <fd> <内容>", "写入文件"),
                    ("seek <fd> <偏移> [whence]", "移动文件指针"),
                ]),
                ("其他命令", [
                    ("demo", "运行功能演示"),
                    ("help [命令]", "显示帮助信息"),
                    ("exit", "退出系统"),
                ])
            ]

            for category, commands in categories:
                print(f"\n{category}:")
                for cmd, desc in commands:
                    print(f"  {cmd:<35} {desc}")

            print("\n═" * 70)
            print("💡 提示:")
            print("  - 使用 'demo' 命令查看功能演示")
            print("  - 文件描述符(fd)是 open 命令返回的数字")
            print("  - 版本ID可以在 versions 命令的输出中找到")

    def do_exit(self, arg):
        """退出系统: EXIT"""
        print("\n👋 正在退出增强型文件系统...")
        print("感谢使用！")
        return True

    def do_EOF(self, arg):
        """Ctrl+D 退出"""
        print()
        return self.do_exit(arg)

    def emptyline(self):
        """空行不执行任何操作"""
        pass


def main():
    """主函数"""
    # 检查Python版本
    if sys.version_info < (3, 8):
        print("❌ 需要Python 3.8或更高版本")
        sys.exit(1)

    # 创建并运行shell
    shell = FileSystemShell()

    try:
        shell.cmdloop()
    except KeyboardInterrupt:
        print("\n\n中断，正在退出...")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()