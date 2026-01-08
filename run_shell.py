#!/usr/bin/env python3
"""
增强文件系统交互式shell
"""

import sys
import os
import cmd
import shlex
import time
from enhanced_fs import EnhancedFileSystem


class FileSystemShell(cmd.Cmd):
    """文件系统交互式shell"""

    intro = "欢迎使用增强型文件系统 Shell! 输入 'help' 获取命令列表。"
    prompt = "fs> "

    def __init__(self):
        super().__init__()
        self.fs = EnhancedFileSystem()
        self.current_user = "root"

    def do_login(self, args):
        """登录用户: login username password"""
        try:
            username, password = args.split()
            if self.fs.login(username, password):
                self.current_user = username
                print(f"登录成功: {username}")
            else:
                print("登录失败: 用户名或密码错误")
        except ValueError:
            print("用法: login username password")

    def do_logout(self, args):
        """登出用户"""
        self.fs.logout()
        self.current_user = "root"
        print("已登出，当前用户: root")

    def do_create_user(self, args):
        """创建用户: create_user username password"""
        if self.current_user != "root":
            print("只有root用户能创建新用户")
            return

        try:
            username, password = args.split()
            if self.fs.create_user(username, password):
                print(f"用户创建成功: {username}")
            else:
                print("用户创建失败: 用户已存在")
        except ValueError:
            print("用法: create_user username password")

    def do_mkdir(self, args):
        """创建目录: mkdir directory_name"""
        if self.fs.create_directory(args):
            print(f"目录创建成功: {args}")
        else:
            print(f"目录创建失败: {args}")

    def do_touch(self, args):
        """创建文件: touch filename"""
        if self.fs.create_file(args):
            print(f"文件创建成功: {args}")
        else:
            print(f"文件创建失败: {args}")

    def do_ls(self, args):
        """列出目录: ls [path]"""
        items = self.fs.list_directory(args if args else ".")
        if items:
            print(f"{'权限':<10} {'类型':<4} {'大小':<8} {'所有者':<10} {'修改时间':<20} 名称")
            print("-" * 80)
            for item in items:
                print(f"{item['permissions']:<10} {item['type']:<4} "
                      f"{item['size']:<8} {item['owner']:<10} "
                      f"{item['modified']:<20} {item['name']}")
        else:
            print("目录为空或不存在")

    def do_cat(self, args):
        """查看文件内容: cat filename"""
        fd = self.fs.open_file(args, "r")
        if fd is None:
            print(f"无法打开文件: {args}")
            return

        data = self.fs.read_file(fd, 4096)
        while data:
            print(data.decode('utf-8', errors='ignore'), end='')
            data = self.fs.read_file(fd, 4096)

        self.fs.close_file(fd)
        print()

    def do_write(self, args):
        """写入文件: write filename "content" """
        try:
            filename, content = args.split(maxsplit=1)
            if content.startswith('"') and content.endswith('"'):
                content = content[1:-1]

            fd = self.fs.open_file(filename, "w")
            if fd is None:
                print(f"无法打开文件: {filename}")
                return

            if self.fs.write_file(fd, content.encode('utf-8')):
                print(f"写入成功: {filename}")
            else:
                print(f"写入失败: {filename}")

            self.fs.close_file(fd)
        except ValueError:
            print('用法: write filename "content"')

    def do_rm(self, args):
        """删除文件或目录: rm path"""
        if self.fs.delete(args):
            print(f"删除成功: {args}")
        else:
            print(f"删除失败: {args}")

    def do_info(self, args):
        """查看文件信息: info path"""
        info = self.fs.get_file_info(args)
        if info:
            for key, value in info.items():
                print(f"{key}: {value}")
        else:
            print(f"文件不存在: {args}")

    def do_chmod(self, args):
        """修改权限: chmod path mode (八进制，如755)"""
        try:
            path, mode_str = args.split()
            mode = int(mode_str, 8)
            if self.fs.change_permissions(path, mode):
                print(f"权限修改成功: {path} -> {oct(mode)}")
            else:
                print(f"权限修改失败: {path}")
        except (ValueError, TypeError):
            print("用法: chmod path mode (如: chmod myfile 644)")

    def do_copy(self, args):
        """复制文件: copy source destination [--no-perms] [--no-timestamps]"""
        try:
            parts = args.split()
            if len(parts) < 2:
                print("用法: copy source destination [--no-perms] [--no-timestamps]")
                return

            src = parts[0]
            dst = parts[1]

            # 解析选项
            preserve_permissions = True
            preserve_timestamps = True

            if '--no-perms' in parts:
                preserve_permissions = False
            if '--no-timestamps' in parts:
                preserve_timestamps = False

            if self.fs.copy_file(src, dst, preserve_permissions, preserve_timestamps):
                print(f"复制成功: {src} -> {dst}")
            else:
                print(f"复制失败: {src} -> {dst}")
        except Exception as e:
            print(f"复制出错: {e}")

    def do_merge(self, args):
        """合并文件: merge file1 file2 output_file [separator]"""
        try:
            parts = args.split()
            if len(parts) == 3:
                file1, file2, output = parts
                separator = "\n"  # 默认换行符分隔
            elif len(parts) == 4:
                file1, file2, output, sep = parts
                separator = sep
            else:
                print("用法: merge file1 file2 output_file [separator]")
                return

            if self.fs.merge_files(file1, file2, output, separator.encode()):
                print(f"合并成功: {file1} + {file2} -> {output}")
            else:
                print(f"合并失败: {file1} + {file2} -> {output}")
        except Exception as e:
            print(f"合并出错: {e}")

    def do_encrypt(self, args):
        """启用/禁用加密: encrypt filename [on|off]"""
        try:
            parts = args.split()
            if len(parts) == 1:
                # 默认启用
                if self.fs.enable_file_encryption(parts[0], True):
                    print(f"已启用加密: {parts[0]}")
                else:
                    print(f"启用加密失败: {parts[0]}")
            elif len(parts) == 2:
                enable = parts[1].lower() in ['on', 'true', '1', 'yes']
                if self.fs.enable_file_encryption(parts[0], enable):
                    state = "启用" if enable else "禁用"
                    print(f"已{state}加密: {parts[0]}")
                else:
                    print(f"操作失败: {parts[0]}")
        except:
            print("用法: encrypt filename [on|off]")

    def do_compress(self, args):
        """启用/禁用压缩: compress filename [on|off]"""
        try:
            parts = args.split()
            if len(parts) == 1:
                # 默认启用
                if self.fs.enable_file_compression(parts[0], True):
                    print(f"已启用压缩: {parts[0]}")
                else:
                    print(f"启用压缩失败: {parts[0]}")
            elif len(parts) == 2:
                enable = parts[1].lower() in ['on', 'true', '1', 'yes']
                if self.fs.enable_file_compression(parts[0], enable):
                    state = "启用" if enable else "禁用"
                    print(f"已{state}压缩: {parts[0]}")
                else:
                    print(f"操作失败: {parts[0]}")
        except:
            print("用法: compress filename [on|off]")

    def do_versions(self, args):
        """查看文件版本: versions filename"""
        versions = self.fs.list_file_versions(args)
        if versions:
            print(f"文件 '{args}' 的版本历史:")
            print(f"{'版本ID':<25} {'大小':<8} {'时间':<20} {'作者':<10} 备注")
            print("-" * 80)
            for ver in versions:
                time_str = time.strftime('%Y-%m-%d %H:%M', time.localtime(ver['timestamp']))
                print(f"{ver['id']:<25} {ver['size']:<8} {time_str:<20} "
                      f"{ver['author']:<10} {ver.get('comment', '')}")
        else:
            print(f"文件 '{args}' 没有版本历史")

    def do_restore(self, args):
        """恢复版本: restore filename version_id"""
        try:
            filename, version_id = args.split()
            if self.fs.restore_version(filename, version_id):
                print(f"恢复成功: {filename} -> {version_id}")
            else:
                print(f"恢复失败: {filename}")
        except ValueError:
            print("用法: restore filename version_id")

    def do_stats(self, args):
        """查看系统统计"""
        stats = self.fs.get_system_stats()
        print("=" * 60)
        print("系统统计信息")
        print("=" * 60)

        # 磁盘使用
        print("\n📊 磁盘使用:")
        du = stats['disk_usage']
        print(f"  总大小: {du['total_size_mb']:.1f} MB")
        print(f"  已使用: {du['used_size_mb']:.1f} MB")
        print(f"  空闲: {du['total_size_mb'] - du['used_size_mb']:.1f} MB")
        print(
            f"  块使用: {du['used_blocks']}/{du['total_blocks']} "
            f"({(du['used_blocks'] / du['total_blocks'] * 100):.1f}%)")

        # 文件统计
        print("\n📁 文件统计:")
        fc = stats['file_counts']
        print(f"  Inode总数: {fc['total_inodes']}")
        print(f"  加密文件: {fc['encrypted_files']}")
        print(f"  压缩文件: {fc['compressed_files']}")

        # 操作统计
        print("\n⚡ 操作统计:")
        ops = stats['operation_stats']
        total_ops = sum(ops.values())
        print(f"  总操作数: {total_ops}")
        for op, count in ops.items():
            print(f"  {op}: {count}")

        # 功能状态
        print("\n🔧 功能状态:")
        fe = stats['features_enabled']
        for feature, enabled in fe.items():
            status = "✅ 启用" if enabled else "❌ 禁用"
            print(f"  {feature}: {status}")

        # 版本统计
        if 'version_stats' in stats:
            print("\n🔄 版本控制:")
            vs = stats['version_stats']
            print(f"  有版本的文件数: {vs['total_files_with_versions']}")
            print(f"  总版本数: {vs['total_versions']}")
            print(f"  存储大小: {vs['total_storage_bytes'] / 1024:.1f} KB")

        # 加密统计
        if 'crypto_stats' in stats:
            print("\n🔐 加密压缩:")
            cs = stats['crypto_stats']
            print(f"  压缩率: {cs['compression_ratio']}")
            print(f"  节省空间: {cs['space_saved'] / 1024:.1f} KB")
            print(f"  加密次数: {cs['encryption_count']}")
            print(f"  压缩次数: {cs['compression_count']}")

        # 缓存统计
        if 'cache_stats' in stats:
            print("\n💾 缓存统计:")
            cs = stats['cache_stats']
            print(f"  命中率: {cs['hit_rate']}")
            print(f"  命中: {cs['hits']}, 未命中: {cs['misses']}")
            print(f"  缓存大小: {cs['size']}/{cs['capacity']}")

    def do_save(self, args):
        """保存文件系统: save filename"""
        if args:
            self.fs.save_to_file(args)
            print(f"文件系统已保存到: {args}")
        else:
            print("用法: save filename")

    def do_load(self, args):
        """加载文件系统: load filename"""
        if args:
            if self.fs.load_from_file(args):
                print(f"文件系统已从 {args} 加载")
            else:
                print(f"加载失败: {args}")
        else:
            print("用法: load filename")

    def do_recover(self, args):
        """执行崩溃恢复"""
        recovered = self.fs.manual_recovery()
        print(f"恢复完成: 重做了 {recovered} 个操作")

    def do_clear(self, args):
        """清屏"""
        os.system('cls' if os.name == 'nt' else 'clear')

    def do_exit(self, args):
        """退出系统"""
        print("再见!")
        return True

    def do_quit(self, args):
        """退出系统"""
        return self.do_exit(args)

    def do_help(self, args):
        """显示帮助信息"""
        super().do_help(args)
        print("\n📋 主要命令:")
        print(" login/logout - 登录/登出")
        print(" mkdir/touch - 创建目录/文件")
        print(" ls/cat - 列出目录/查看文件")
        print(" write/rm - 写入/删除文件")
        print(" info/chmod - 查看信息/修改权限")
        print(" copy/merge - 复制/合并文件")  # 新增
        print(" encrypt/compress - 加密/压缩文件")
        print(" versions/restore - 版本管理")
        print(" stats - 系统统计")
        print(" save/load - 保存/加载文件系统")
        print(" recover - 崩溃恢复")
        print(" exit/quit - 退出系统")
        print("\n📖 示例:")
        print("  copy file1.txt file2.txt")
        print("  merge part1.txt part2.txt combined.txt")
        print("  copy data.txt backup.txt --no-perms")


def main():
    """主函数"""
    import time
    shell = FileSystemShell()
    try:
        shell.cmdloop()
    except KeyboardInterrupt:
        print("\n\n程序被中断")
        shell.do_exit("")


if __name__ == "__main__":
    main()