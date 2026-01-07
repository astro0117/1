#!/usr/bin/env python3
"""
文件系统常量定义
"""
from enum import IntEnum

# 文件类型
class FileType(IntEnum):
    FILE = 0
    DIRECTORY = 1

# 权限掩码
class Permission(IntEnum):
    READ = 0o4
    WRITE = 0o2
    EXECUTE = 0o1

# 事务操作类型
class OperationType(IntEnum):
    CREATE_FILE = 1
    DELETE_FILE = 2
    WRITE_FILE = 3
    CREATE_DIR = 4
    DELETE_DIR = 5
    RENAME = 6
    CHMOD = 7
    OPEN_FILE = 8
    CLOSE_FILE = 9

# 系统常量
DISK_SIZE_MB = 10  # 虚拟磁盘大小 (MB)
BLOCK_SIZE_KB = 4  # 块大小 (KB)
MAX_FILENAME = 255  # 最大文件名长度
MAX_USERS = 100  # 最大用户数
MAX_OPEN_FILES = 20  # 最大打开文件数
VERSION_LIMIT = 10  # 每个文件最大版本数
TRANSACTION_LOG_FILE = ".fs_transaction.log"  # 事务日志文件
VERSION_STORAGE_DIR = ".versions"  # 版本存储目录
ENCRYPTION_KEY_FILE = ".fs_encryption_key"  # 加密密钥文件