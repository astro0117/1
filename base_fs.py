#!/usr/bin/env python3
"""
基础文件系统实现
包含：虚拟磁盘、inode、目录、基本文件操作
"""

import os
import time
import json
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from collections import OrderedDict

from constants import FileType, Permission, MAX_FILENAME, MAX_OPEN_FILES


@dataclass
class Inode:
    """Inode 数据结构"""
    id: int
    type: FileType
    size: int = 0
    blocks: List[int] = field(default_factory=list)
    created: float = field(default_factory=time.time)
    modified: float = field(default_factory=time.time)
    accessed: float = field(default_factory=time.time)
    owner: str = "root"
    group: str = "root"
    permissions: int = 0o644  # 默认权限 rw-r--r--
    link_count: int = 1
    xattrs: Dict[str, bytes] = field(default_factory=dict)  # 扩展属性

    def __post_init__(self):
        if self.blocks is None:
            self.blocks = []

    def update_access_time(self):
        """更新访问时间"""
        self.accessed = time.time()

    def update_modify_time(self):
        """更新修改时间"""
        self.modified = time.time()

    def get_permission_string(self) -> str:
        """获取权限字符串表示"""
        perm = self.permissions
        type_char = 'd' if self.type == FileType.DIRECTORY else '-'
        result = type_char

        # 所有者权限
        result += 'r' if (perm & 0o400) else '-'
        result += 'w' if (perm & 0o200) else '-'
        result += 'x' if (perm & 0o100) else '-'
        # 组权限
        result += 'r' if (perm & 0o040) else '-'
        result += 'w' if (perm & 0o020) else '-'
        result += 'x' if (perm & 0o010) else '-'
        # 其他用户权限
        result += 'r' if (perm & 0o004) else '-'
        result += 'w' if (perm & 0o002) else '-'
        result += 'x' if (perm & 0o001) else '-'

        return result

    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            'id': self.id,
            'type': self.type.value,
            'size': self.size,
            'blocks': self.blocks,
            'created': self.created,
            'modified': self.modified,
            'accessed': self.accessed,
            'owner': self.owner,
            'group': self.group,
            'permissions': self.permissions,
            'link_count': self.link_count,
            'xattrs': {k: v.hex() for k, v in self.xattrs.items()}
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Inode':
        """从字典创建Inode"""
        inode = cls(
            id=data['id'],
            type=FileType(data['type']),
            size=data['size'],
            blocks=data['blocks'],
            created=data['created'],
            modified=data['modified'],
            accessed=data['accessed'],
            owner=data['owner'],
            group=data['group'],
            permissions=data['permissions'],
            link_count=data['link_count']
        )
        inode.xattrs = {k: bytes.fromhex(v) for k, v in data.get('xattrs', {}).items()}
        return inode


@dataclass
class DirectoryEntry:
    """目录项"""
    name: str
    inode_id: int

    def to_dict(self) -> Dict:
        return {'name': self.name, 'inode_id': self.inode_id}

    @classmethod
    def from_dict(cls, data: Dict) -> 'DirectoryEntry':
        return cls(name=data['name'], inode_id=data['inode_id'])


class BlockCache:
    """块缓存（LRU实现）"""

    def __init__(self, capacity: int = 100):
        self.cache = OrderedDict()
        self.capacity = capacity
        self.hits = 0
        self.misses = 0

    def get(self, block_id: int) -> Optional[bytearray]:
        """获取块，如果命中则移动到最新"""
        if block_id in self.cache:
            self.cache.move_to_end(block_id)
            self.hits += 1
            return self.cache[block_id]
        self.misses += 1
        return None

    def put(self, block_id: int, block_data: bytearray):
        """添加块到缓存"""
        if block_id in self.cache:
            self.cache.move_to_end(block_id)
        self.cache[block_id] = block_data
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)  # 移除最旧的

    def clear(self):
        """清空缓存"""
        self.cache.clear()

    def stats(self) -> Dict:
        """获取缓存统计"""
        total = self.hits + self.misses
        hit_rate = self.hits / total if total > 0 else 0
        return {
            'size': len(self.cache),
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': f'{hit_rate:.1%}',
            'capacity': self.capacity
        }


class SimpleFileSystem:
    """简单文件系统"""

    def __init__(self, disk_size_mb: int = 10, block_size_kb: int = 4):
        # 磁盘参数
        self.block_size = block_size_kb * 1024  # 字节
        self.disk_size = disk_size_mb * 1024 * 1024
        self.block_count = self.disk_size // self.block_size

        # 存储结构
        self.blocks = [bytearray(self.block_size) for _ in range(self.block_count)]
        self.free_blocks = [True] * self.block_count  # True表示空闲

        # 缓存
        self.block_cache = BlockCache(capacity=50)

        # 管理结构
        self.inodes: Dict[int, Inode] = {}
        self.next_inode_id = 0
        self.directory_contents: Dict[int, List[DirectoryEntry]] = {}

        # 用户和会话
        self.users = {"root": "root123"}  # 用户名:密码
        self.current_user = "root"
        self.current_dir = 0  # 根目录inode

        # 打开文件表
        self.open_files: Dict[int, Dict] = {}  # fd -> {inode_id, offset, mode, path}
        self.next_fd = 0

        # 初始化根目录
        self._init_root_directory()

    def _init_root_directory(self):
        """初始化根目录"""
        # 创建根目录inode
        root_inode = Inode(
            id=0,
            type=FileType.DIRECTORY,
            permissions=0o755,
            owner="root",
            group="root"
        )
        self.inodes[0] = root_inode
        self.next_inode_id = 1

        # 根目录内容：. 和 ..
        self.directory_contents[0] = [
            DirectoryEntry(".", 0),
            DirectoryEntry("..", 0)
        ]

        # 为根目录分配存储块
        block_idx = self._allocate_block()
        if block_idx is not None:
            root_inode.blocks.append(block_idx)
            root_inode.size = 2 * 256  # 两个目录项的大小估算

    def _allocate_block(self) -> Optional[int]:
        """分配一个空闲块"""
        for i, free in enumerate(self.free_blocks):
            if free:
                self.free_blocks[i] = False
                self.blocks[i] = bytearray(self.block_size)  # 清空块
                return i
        return None

    def _free_block(self, block_idx: int):
        """释放一个块"""
        if 0 <= block_idx < self.block_count:
            self.free_blocks[block_idx] = True
            # 从缓存中移除
            if block_idx in self.block_cache.cache:
                del self.block_cache.cache[block_idx]

    def _read_block(self, block_idx: int) -> bytearray:
        """读取块数据（使用缓存）"""
        # 尝试从缓存获取
        cached = self.block_cache.get(block_idx)
        if cached is not None:
            return cached

        # 从磁盘读取
        if 0 <= block_idx < self.block_count:
            data = self.blocks[block_idx].copy()
            # 放入缓存
            self.block_cache.put(block_idx, data)
            return data
        return bytearray(self.block_size)

    def _write_block(self, block_idx: int, data: bytes):
        """写入块数据（更新缓存）"""
        if 0 <= block_idx < self.block_count:
            # 确保数据长度正确
            if len(data) > self.block_size:
                data = data[:self.block_size]
            elif len(data) < self.block_size:
                data = data.ljust(self.block_size, b'\x00')

            # 更新磁盘
            self.blocks[block_idx] = bytearray(data)
            # 更新缓存
            self.block_cache.put(block_idx, bytearray(data))

    def _allocate_inode(self, file_type: FileType) -> Optional[Inode]:
        """分配一个新的inode"""
        inode_id = self.next_inode_id
        inode = Inode(
            id=inode_id,
            type=file_type,
            owner=self.current_user,
            group=self.current_user,
            permissions=0o644 if file_type == FileType.FILE else 0o755
        )
        self.inodes[inode_id] = inode
        self.next_inode_id += 1
        return inode

    def _find_inode_by_path(self, path: str) -> Optional[int]:
        """根据路径查找inode"""
        if not path or path == "/":
            return 0  # 根目录

        # 处理绝对路径和相对路径
        if path.startswith("/"):
            current_inode = 0
            parts = [p for p in path.strip("/").split("/") if p]
        else:
            current_inode = self.current_dir
            parts = [p for p in path.split("/") if p]

        for part in parts:
            if part == ".":
                continue
            elif part == "..":
                # 获取父目录
                if current_inode == 0:
                    continue  # 根目录的父目录是自身
                dir_entries = self.directory_contents.get(current_inode, [])
                for entry in dir_entries:
                    if entry.name == "..":
                        current_inode = entry.inode_id
                        break
            else:
                # 在当前目录查找
                found = False
                dir_entries = self.directory_contents.get(current_inode, [])
                for entry in dir_entries:
                    if entry.name == part:
                        current_inode = entry.inode_id
                        found = True
                        break
                if not found:
                    return None

        return current_inode

    def _check_permission(self, inode_id: int, need_write: bool = False) -> bool:
        """检查当前用户对inode的权限"""
        if self.current_user == "root":
            return True

        inode = self.inodes.get(inode_id)
        if not inode:
            return False

        # 检查所有者权限
        if inode.owner == self.current_user:
            if need_write:
                return (inode.permissions & 0o200) != 0  # 检查写权限
            return (inode.permissions & 0o400) != 0  # 检查读权限

        # 非所有者，检查其他用户权限
        if need_write:
            return (inode.permissions & 0o002) != 0
        return (inode.permissions & 0o004) != 0

    def _add_to_directory(self, dir_inode_id: int, name: str, target_inode_id: int) -> bool:
        """添加目录项"""
        if dir_inode_id not in self.directory_contents:
            self.directory_contents[dir_inode_id] = []

        # 检查是否已存在
        for entry in self.directory_contents[dir_inode_id]:
            if entry.name == name:
                return False

        # 添加新目录项
        self.directory_contents[dir_inode_id].append(
            DirectoryEntry(name, target_inode_id)
        )

        # 更新目录inode
        dir_inode = self.inodes.get(dir_inode_id)
        if dir_inode:
            dir_inode.update_modify_time()
            # 估算目录大小
            dir_inode.size = len(self.directory_contents[dir_inode_id]) * 256

        return True

    def _remove_from_directory(self, dir_inode_id: int, name: str) -> bool:
        """移除目录项"""
        if dir_inode_id not in self.directory_contents:
            return False

        entries = self.directory_contents[dir_inode_id]
        for i, entry in enumerate(entries):
            if entry.name == name:
                del entries[i]

                # 更新目录inode
                dir_inode = self.inodes.get(dir_inode_id)
                if dir_inode:
                    dir_inode.update_modify_time()
                    dir_inode.size = len(entries) * 256

                return True

        return False

    def login(self, username: str, password: str) -> bool:
        """用户登录"""
        if username in self.users and self.users[username] == password:
            self.current_user = username
            return True
        return False

    def logout(self):
        """用户登出"""
        self.current_user = "root"
        # 关闭所有打开的文件
        for fd in list(self.open_files.keys()):
            self.close_file(fd)

    def create_user(self, username: str, password: str) -> bool:
        """创建新用户"""
        if self.current_user != "root":
            return False
        if username in self.users:
            return False
        self.users[username] = password
        return True

    def create_file(self, path: str) -> bool:
        """创建文件"""
        # 解析路径
        if "/" in path:
            dir_path, filename = path.rsplit("/", 1)
            if dir_path == "":
                dir_path = "/"
        else:
            dir_path = "."
            filename = path

        # 查找父目录
        dir_inode_id = self._find_inode_by_path(dir_path)
        if dir_inode_id is None:
            return False

        # 检查权限
        if not self._check_permission(dir_inode_id, need_write=True):
            return False

        # 检查是否已存在
        entries = self.directory_contents.get(dir_inode_id, [])
        for entry in entries:
            if entry.name == filename:
                return False

        # 创建新inode
        new_inode = self._allocate_inode(FileType.FILE)
        if not new_inode:
            return False

        # 添加到目录
        if not self._add_to_directory(dir_inode_id, filename, new_inode.id):
            inode_id = new_inode.id
            if inode_id in self.inodes:
                del self.inodes[inode_id]
            return False

        return True

    def create_directory(self, path: str) -> bool:
        """创建目录"""
        if "/" in path:
            dir_path, dirname = path.rsplit("/", 1)
            if dir_path == "":
                dir_path = "/"
        else:
            dir_path = "."
            dirname = path

        # 查找父目录
        parent_inode_id = self._find_inode_by_path(dir_path)
        if parent_inode_id is None:
            return False

        # 检查权限
        if not self._check_permission(parent_inode_id, need_write=True):
            return False

        # 检查是否已存在
        entries = self.directory_contents.get(parent_inode_id, [])
        for entry in entries:
            if entry.name == dirname:
                return False

        # 创建新目录inode
        new_inode = self._allocate_inode(FileType.DIRECTORY)
        if not new_inode:
            return False

        # 初始化新目录内容
        self.directory_contents[new_inode.id] = [
            DirectoryEntry(".", new_inode.id),
            DirectoryEntry("..", parent_inode_id)
        ]

        # 为目录分配存储块
        block_idx = self._allocate_block()
        if block_idx is not None:
            new_inode.blocks.append(block_idx)

        # 添加到父目录
        if not self._add_to_directory(parent_inode_id, dirname, new_inode.id):
            inode_id = new_inode.id
            if inode_id in self.inodes:
                del self.inodes[inode_id]
            if inode_id in self.directory_contents:
                del self.directory_contents[inode_id]
            return False

        return True

    def delete(self, path: str) -> bool:
        """删除文件或目录"""
        # 查找要删除的inode
        target_inode_id = self._find_inode_by_path(path)
        if target_inode_id is None or target_inode_id == 0:
            return False

        # 查找父目录和文件名
        if "/" in path:
            parent_path, name = path.rsplit("/", 1)
            if parent_path == "":
                parent_path = "/"
        else:
            parent_path = "."
            name = path

        parent_inode_id = self._find_inode_by_path(parent_path)
        if parent_inode_id is None:
            return False

        # 检查权限
        if not self._check_permission(target_inode_id, need_write=True):
            return False
        if not self._check_permission(parent_inode_id, need_write=True):
            return False

        target_inode = self.inodes.get(target_inode_id)
        if not target_inode:
            return False

        # 如果是目录，检查是否为空（除了.和..）
        if target_inode.type == FileType.DIRECTORY:
            entries = self.directory_contents.get(target_inode_id, [])
            if len(entries) > 2:
                return False  # 目录非空

        # 从父目录中移除
        if not self._remove_from_directory(parent_inode_id, name):
            return False

        # 释放数据块
        for block_idx in target_inode.blocks:
            self._free_block(block_idx)

        # 清理目录内容（如果是目录）
        if target_inode_id in self.directory_contents:
            del self.directory_contents[target_inode_id]

        # 删除inode
        if target_inode_id in self.inodes:
            del self.inodes[target_inode_id]

        return True

    def list_directory(self, path: str = ".") -> List[Dict[str, Any]]:
        """列出目录内容"""
        target_inode_id = self._find_inode_by_path(path)
        if target_inode_id is None:
            return []

        # 检查权限
        if not self._check_permission(target_inode_id):
            return []

        result = []
        entries = self.directory_contents.get(target_inode_id, [])

        for entry in entries:
            inode = self.inodes.get(entry.inode_id)
            if inode:
                result.append({
                    'name': entry.name,
                    'type': 'd' if inode.type == FileType.DIRECTORY else '-',
                    'permissions': inode.get_permission_string(),
                    'size': inode.size,
                    'owner': inode.owner,
                    'modified': time.strftime('%Y-%m-%d %H:%M',
                                              time.localtime(inode.modified))
                })

        return result

    def open_file(self, path: str, mode: str = "r") -> Optional[int]:
        """打开文件"""
        inode_id = self._find_inode_by_path(path)
        if inode_id is None:
            return None

        inode = self.inodes.get(inode_id)
        if not inode or inode.type != FileType.FILE:
            return None

        # 检查权限
        need_write = "w" in mode or "a" in mode
        if not self._check_permission(inode_id, need_write=need_write):
            return None

        # 分配文件描述符
        fd = self.next_fd
        self.next_fd += 1

        # 设置初始偏移量
        offset = 0
        if "a" in mode:  # 追加模式
            offset = inode.size

        self.open_files[fd] = {
            'inode_id': inode_id,
            'offset': offset,
            'mode': mode,
            'path': path
        }

        # 更新访问时间
        inode.update_access_time()

        return fd

    def close_file(self, fd: int) -> bool:
        """关闭文件"""
        if fd in self.open_files:
            del self.open_files[fd]
            return True
        return False

    def read_file(self, fd: int, size: int) -> Optional[bytes]:
        """读取文件"""
        if fd not in self.open_files:
            return None

        file_info = self.open_files[fd]
        if "r" not in file_info['mode'] and "+" not in file_info['mode']:
            return None

        inode_id = file_info['inode_id']
        offset = file_info['offset']
        inode = self.inodes.get(inode_id)

        if not inode or offset >= inode.size:
            return b""

        # 计算实际读取大小
        read_size = min(size, inode.size - offset)
        result = bytearray()

        # 从数据块读取
        bytes_read = 0
        while bytes_read < read_size:
            block_idx = offset // self.block_size
            block_offset = offset % self.block_size

            if block_idx >= len(inode.blocks):
                break

            actual_block = inode.blocks[block_idx]
            bytes_in_block = min(self.block_size - block_offset,
                                 read_size - bytes_read)

            # 读取块数据
            block_data = self._read_block(actual_block)
            result.extend(block_data[block_offset:block_offset + bytes_in_block])

            offset += bytes_in_block
            bytes_read += bytes_in_block

        # 更新偏移量
        file_info['offset'] = offset

        # 更新访问时间
        inode.update_access_time()

        return bytes(result)

    def write_file(self, fd: int, data: bytes) -> bool:
        """写入文件"""
        if fd not in self.open_files:
            return False

        file_info = self.open_files[fd]
        if "w" not in file_info['mode'] and "a" not in file_info['mode'] and "+" not in file_info['mode']:
            return False

        inode_id = file_info['inode_id']
        offset = file_info['offset']
        inode = self.inodes.get(inode_id)

        if not inode:
            return False

        # 确保有足够的数据块
        total_needed = offset + len(data)
        needed_blocks = (total_needed + self.block_size - 1) // self.block_size

        while len(inode.blocks) < needed_blocks:
            new_block = self._allocate_block()
            if new_block is None:
                return False  # 磁盘空间不足
            inode.blocks.append(new_block)

        # 写入数据
        bytes_written = 0
        while bytes_written < len(data):
            block_idx = offset // self.block_size
            block_offset = offset % self.block_size

            actual_block = inode.blocks[block_idx]
            bytes_in_block = min(self.block_size - block_offset,
                                 len(data) - bytes_written)

            # 读取现有数据（如果需要部分写入）
            if block_offset > 0 or bytes_in_block < self.block_size:
                block_data = self._read_block(actual_block)
            else:
                block_data = bytearray(self.block_size)

            # 写入新数据
            block_data[block_offset:block_offset + bytes_in_block] = \
                data[bytes_written:bytes_written + bytes_in_block]

            # 写回块
            self._write_block(actual_block, block_data)

            offset += bytes_in_block
            bytes_written += bytes_in_block

        # 更新inode信息
        inode.size = max(inode.size, offset)
        inode.update_modify_time()
        file_info['offset'] = offset

        return True

    def seek_file(self, fd: int, offset: int, whence: int = 0) -> Optional[int]:
        """移动文件指针"""
        if fd not in self.open_files:
            return None

        file_info = self.open_files[fd]
        inode_id = file_info['inode_id']
        inode = self.inodes.get(inode_id)

        if not inode:
            return None

        if whence == 0:  # SEEK_SET
            new_offset = offset
        elif whence == 1:  # SEEK_CUR
            new_offset = file_info['offset'] + offset
        elif whence == 2:  # SEEK_END
            new_offset = inode.size + offset
        else:
            return None

        # 确保偏移量有效
        if new_offset < 0:
            new_offset = 0
        elif new_offset > inode.size:
            new_offset = inode.size

        file_info['offset'] = new_offset
        return new_offset

    def get_file_info(self, path: str) -> Optional[Dict]:
        """获取文件信息"""
        inode_id = self._find_inode_by_path(path)
        if inode_id is None:
            return None

        inode = self.inodes.get(inode_id)
        if not inode:
            return None

        return {
            'path': path,
            'inode_id': inode.id,
            'type': 'directory' if inode.type == FileType.DIRECTORY else 'file',
            'size': inode.size,
            'blocks': len(inode.blocks),
            'owner': inode.owner,
            'group': inode.group,
            'permissions': inode.get_permission_string(),
            'permissions_octal': oct(inode.permissions),
            'created': time.strftime('%Y-%m-%d %H:%M:%S',
                                     time.localtime(inode.created)),
            'modified': time.strftime('%Y-%m-%d %H:%M:%S',
                                      time.localtime(inode.modified)),
            'accessed': time.strftime('%Y-%m-%d %H:%M:%S',
                                      time.localtime(inode.accessed)),
            'link_count': inode.link_count
        }

    def change_permissions(self, path: str, mode: int) -> bool:
        """修改文件权限"""
        inode_id = self._find_inode_by_path(path)
        if inode_id is None:
            return False

        inode = self.inodes.get(inode_id)
        if not inode:
            return False

        # 检查权限
        if inode.owner != self.current_user and self.current_user != "root":
            return False

        inode.permissions = mode & 0o777
        inode.update_modify_time()
        return True

    def get_disk_usage(self) -> Dict[str, Any]:
        """获取磁盘使用情况"""
        used_blocks = sum(1 for free in self.free_blocks if not free)
        used_inodes = len(self.inodes)

        return {
            'total_blocks': self.block_count,
            'used_blocks': used_blocks,
            'free_blocks': self.block_count - used_blocks,
            'used_inodes': used_inodes,
            'total_size_mb': self.disk_size / (1024 * 1024),
            'used_size_mb': (used_blocks * self.block_size) / (1024 * 1024),
            'block_size_kb': self.block_size / 1024,
            'block_count': self.block_count
        }

    def save_to_file(self, filename: str):
        """保存文件系统状态到文件"""
        # 构建保存的数据结构
        data = {
            'disk_size': self.disk_size,
            'block_size': self.block_size,
            'block_count': self.block_count,
            'blocks': [block.hex() for block in self.blocks],
            'free_blocks': self.free_blocks,
            'inodes': {k: v.to_dict() for k, v in self.inodes.items()},
            'directory_contents': {
                k: [e.to_dict() for e in v]
                for k, v in self.directory_contents.items()
            },
            'users': self.users,
            'next_inode_id': self.next_inode_id,
            'current_user': self.current_user,
            'current_dir': self.current_dir
        }

        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)

    def load_from_file(self, filename: str) -> bool:
        """从文件加载文件系统状态"""
        try:
            with open(filename, 'r') as f:
                data = json.load(f)

            # 恢复基本参数
            self.disk_size = data['disk_size']
            self.block_size = data['block_size']
            self.block_count = data['block_count']

            # 恢复块数据
            self.blocks = [
                bytearray.fromhex(block_hex)
                for block_hex in data['blocks']
            ]
            self.free_blocks = data['free_blocks']

            # 恢复inodes
            self.inodes = {
                int(k): Inode.from_dict(v)
                for k, v in data['inodes'].items()
            }

            # 恢复目录内容
            self.directory_contents = {
                int(k): [DirectoryEntry.from_dict(e) for e in v]
                for k, v in data['directory_contents'].items()
            }

            # 恢复其他状态
            self.users = data['users']
            self.next_inode_id = data['next_inode_id']
            self.current_user = data.get('current_user', 'root')
            self.current_dir = data.get('current_dir', 0)

            # 重新初始化块缓存
            self.block_cache.clear()

            return True

        except Exception as e:
            print(f"加载文件系统失败: {e}")
            return False