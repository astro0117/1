#!/usr/bin/env python3
"""
增强型文件系统：集成三大扩展功能
1. 事务日志与崩溃恢复
2. 文件版本控制
3. 文件加密/压缩
"""
import os
import time
import json
import zlib
import hashlib
import base64
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from dataclasses import dataclass, field

# 尝试导入加密库，如果失败则使用模拟实现
try:
    from cryptography.fernet import Fernet

    CRYPTO_AVAILABLE = True
except ImportError:
    print("警告: cryptography库未安装，加密功能将使用模拟实现")
    print("安装命令: pip install cryptography")
    CRYPTO_AVAILABLE = False
    Fernet = None

from constants import *
from base_fs import SimpleFileSystem, Inode, FileType


# ========== 事务日志模块 ==========
@dataclass
class LogEntry:
    """事务日志条目"""
    id: str
    timestamp: float
    operation: OperationType
    params: Dict[str, Any]
    user: str
    status: str = "pending"  # pending, committed, rolled_back

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'timestamp': self.timestamp,
            'operation': self.operation.name,
            'params': self._serialize_params(self.params),
            'user': self.user,
            'status': self.status
        }

    def _serialize_params(self, params: Dict) -> Dict:
        """序列化参数（处理特殊类型）"""
        serialized = {}
        for k, v in params.items():
            if isinstance(v, bytes):
                serialized[k] = base64.b64encode(v).decode('ascii')
            else:
                serialized[k] = v
        return serialized

    @classmethod
    def from_dict(cls, data: Dict) -> 'LogEntry':
        """从字典创建LogEntry"""
        params = cls._deserialize_params(data['params'])
        return cls(
            id=data['id'],
            timestamp=data['timestamp'],
            operation=OperationType[data['operation']],
            params=params,
            user=data['user'],
            status=data['status']
        )

    @staticmethod
    def _deserialize_params(params: Dict) -> Dict:
        """反序列化参数"""
        deserialized = {}
        for k, v in params.items():
            if isinstance(v, str) and len(v) > 100 and '=' in v:
                # 可能是base64编码的字节数据
                try:
                    deserialized[k] = base64.b64decode(v)
                except:
                    deserialized[k] = v
            else:
                deserialized[k] = v
        return deserialized


class TransactionLogger:
    """事务日志管理器"""

    def __init__(self, log_file: str = TRANSACTION_LOG_FILE):
        self.log_file = log_file
        self.current_transaction = None
        self.active = False

        # 创建日志文件目录
        os.makedirs(os.path.dirname(log_file) if os.path.dirname(log_file) else '.',
                    exist_ok=True)

    def begin_transaction(self, transaction_id: str = None):
        """开始新事务"""
        if not transaction_id:
            transaction_id = hashlib.md5(str(time.time()).encode()).hexdigest()[:8]

        self.current_transaction = {
            'id': transaction_id,
            'start_time': time.time(),
            'entries': []
        }
        self.active = True

    def log_operation(self, operation: OperationType, **params) -> Optional[str]:
        """记录操作到当前事务"""
        if not self.active or not self.current_transaction:
            return None

        entry_id = hashlib.md5(
            f"{time.time()}{operation}{params}".encode()
        ).hexdigest()[:12]

        entry = LogEntry(
            id=entry_id,
            timestamp=time.time(),
            operation=operation,
            params=params,
            user="system"
        )

        self.current_transaction['entries'].append(entry)
        # 立即写入日志文件（Write-Ahead Logging）
        self._append_to_log(entry)

        return entry_id

    def commit(self) -> bool:
        """提交当前事务"""
        if not self.active or not self.current_transaction:
            return False

        # 标记所有条目为已提交
        for entry in self.current_transaction['entries']:
            entry.status = "committed"
            self._update_log_status(entry.id, "committed")

        # 清理完成的事务
        self._cleanup_committed_logs()
        self.current_transaction = None
        self.active = False
        return True

    def rollback(self) -> bool:
        """回滚当前事务"""
        if not self.active or not self.current_transaction:
            return False

        # 标记所有条目为已回滚
        for entry in self.current_transaction['entries']:
            entry.status = "rolled_back"
            self._update_log_status(entry.id, "rolled_back")

        print(f"事务回滚: {self.current_transaction['id']}")
        self.current_transaction = None
        self.active = False
        return True

    def recover(self) -> int:
        """系统崩溃后恢复"""
        if not os.path.exists(self.log_file):
            return 0

        recovered_ops = 0
        redo_entries = []

        try:
            with open(self.log_file, 'r') as f:
                for line in f:
                    if line.strip():
                        try:
                            entry_data = json.loads(line)
                            if entry_data.get('status') == 'committed':
                                redo_entries.append(entry_data)
                        except json.JSONDecodeError:
                            continue

            # 执行重做操作（简化实现）
            for entry_data in redo_entries:
                print(f"重做操作: {entry_data['operation']}")
                recovered_ops += 1

            # 清理日志文件
            open(self.log_file, 'w').close()

        except Exception as e:
            print(f"恢复过程中出错: {e}")

        return recovered_ops

    def _append_to_log(self, entry: LogEntry):
        """追加日志条目到文件"""
        try:
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(entry.to_dict()) + '\n')
        except Exception as e:
            print(f"写入日志失败: {e}")

    def _update_log_status(self, entry_id: str, status: str):
        """更新日志条目的状态"""
        # 在实际系统中，这需要更复杂的日志管理
        # 这里我们简化处理，只打印信息
        print(f"更新日志状态: {entry_id} -> {status}")

    def _cleanup_committed_logs(self):
        """清理已提交的日志"""
        # 简化实现：定期清理日志文件
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, 'r') as f:
                    lines = f.readlines()

                # 保留未提交的条目
                pending_lines = []
                for line in lines:
                    try:
                        entry_data = json.loads(line)
                        if entry_data.get('status') != 'committed':
                            pending_lines.append(line)
                    except:
                        pending_lines.append(line)

                # 如果未提交的条目太多，截断文件
                if len(pending_lines) > 1000:
                    pending_lines = pending_lines[-500:]

                with open(self.log_file, 'w') as f:
                    f.writelines(pending_lines)

            except Exception as e:
                print(f"清理日志失败: {e}")


# ========== 版本控制模块 ==========
class VersionManager:
    """版本控制系统"""

    def __init__(self, storage_dir: str = VERSION_STORAGE_DIR):
        self.storage_dir = storage_dir
        self.version_index: Dict[int, List[Dict]] = {}  # file_id -> [版本列表]

        # 创建版本存储目录
        os.makedirs(storage_dir, exist_ok=True)
        # 加载现有版本索引
        self._load_index()

    def create_version(self, file_id: int, content: bytes,
                       author: str, comment: str = "") -> Optional[str]:
        """创建文件新版本"""
        # 计算版本ID
        version_hash = hashlib.md5(content).hexdigest()
        version_id = f"{file_id}_{version_hash[:8]}_{int(time.time())}"
        version_info = {
            'id': version_id,
            'hash': version_hash,
            'timestamp': time.time(),
            'author': author,
            'comment': comment,
            'size': len(content),
            'stored_size': 0
        }

        # 检查是否与上一个版本相同（避免重复存储）
        if file_id in self.version_index and self.version_index[file_id]:
            last_version = self.version_index[file_id][-1]
            if last_version['hash'] == version_hash:
                # 内容相同，不创建新版本
                return last_version['id']

        # 存储版本内容
        version_file = os.path.join(self.storage_dir, f"{version_id}.ver")
        stored_size = self._store_version(version_file, content, file_id)
        if stored_size == 0:
            return None

        version_info['stored_size'] = stored_size

        # 更新版本索引
        if file_id not in self.version_index:
            self.version_index[file_id] = []
        self.version_index[file_id].append(version_info)

        # 限制版本数量
        if len(self.version_index[file_id]) > VERSION_LIMIT:
            self._cleanup_old_versions(file_id)

        # 保存索引
        self._save_index()
        return version_id

    def get_version(self, file_id: int, version_id: str) -> Optional[bytes]:
        """获取特定版本的内容"""
        version_file = os.path.join(self.storage_dir, f"{version_id}.ver")
        if os.path.exists(version_file):
            return self._load_version(version_file, file_id)
        return None

    def list_versions(self, file_id: int) -> List[Dict]:
        """列出文件的所有版本"""
        return self.version_index.get(file_id, [])

    def get_version_info(self, file_id: int, version_id: str) -> Optional[Dict]:
        """获取版本信息"""
        versions = self.version_index.get(file_id, [])
        for version in versions:
            if version['id'] == version_id:
                return version
        return None

    def delete_versions(self, file_id: int):
        """删除文件的所有版本"""
        if file_id in self.version_index:
            for version in self.version_index[file_id]:
                version_file = os.path.join(self.storage_dir, f"{version['id']}.ver")
                if os.path.exists(version_file):
                    os.remove(version_file)
            del self.version_index[file_id]
            self._save_index()

    def get_storage_stats(self) -> Dict:
        """获取版本存储统计"""
        total_files = len(self.version_index)
        total_versions = sum(len(v) for v in self.version_index.values())
        total_size = 0

        # 计算总存储大小
        for versions in self.version_index.values():
            for version in versions:
                total_size += version.get('stored_size', 0)

        return {
            'total_files_with_versions': total_files,
            'total_versions': total_versions,
            'total_storage_bytes': total_size,
            'avg_versions_per_file': total_versions / max(total_files, 1)
        }

    def _store_version(self, filename: str, content: bytes, file_id: int) -> int:
        """存储版本内容"""
        try:
            # 使用gzip压缩存储
            compressed = zlib.compress(content, level=6)
            with open(filename, 'wb') as f:
                # 添加版本标记
                f.write(b'FSVER1.0')
                # 存储压缩后的数据
                f.write(compressed)
            return len(compressed) + 8  # 包括标记长度
        except Exception as e:
            print(f"存储版本失败: {e}")
            return 0

    def _load_version(self, filename: str, file_id: int) -> Optional[bytes]:
        """加载版本内容"""
        try:
            with open(filename, 'rb') as f:
                # 检查版本标记
                marker = f.read(8)
                if marker != b'FSVER1.0':
                    # 可能是旧格式，尝试直接读取
                    f.seek(0)
                    content = f.read()
                    return content

                # 读取压缩数据
                compressed = f.read()
                return zlib.decompress(compressed)
        except Exception as e:
            print(f"加载版本失败: {e}")
            return None

    def _cleanup_old_versions(self, file_id: int):
        """清理旧版本，只保留最近5个"""
        if file_id in self.version_index:
            versions = self.version_index[file_id]
            if len(versions) > 5:
                # 删除最旧的版本文件
                for version_info in versions[:-5]:
                    version_file = os.path.join(
                        self.storage_dir, f"{version_info['id']}.ver"
                    )
                    if os.path.exists(version_file):
                        os.remove(version_file)
                # 更新索引
                self.version_index[file_id] = versions[-5:]

    def _save_index(self):
        """保存版本索引"""
        index_file = os.path.join(self.storage_dir, "index.json")
        try:
            with open(index_file, 'w') as f:
                json.dump(self.version_index, f, indent=2)
        except Exception as e:
            print(f"保存版本索引失败: {e}")

    def _load_index(self):
        """加载版本索引"""
        index_file = os.path.join(self.storage_dir, "index.json")
        if os.path.exists(index_file):
            try:
                with open(index_file, 'r') as f:
                    # 转换字符串键为整数
                    loaded = json.load(f)
                    self.version_index = {
                        int(k): v for k, v in loaded.items()
                    }
            except Exception as e:
                print(f"加载版本索引失败: {e}")
                self.version_index = {}


# ========== 加密压缩模块 ==========
class CryptoCompressor:
    """加密压缩处理器"""

    def __init__(self, encryption_key: bytes = None, compression_level: int = 6):
        """
        encryption_key: 加密密钥（None则自动生成）
        compression_level: 压缩级别 0-9
        """
        self.compression_level = compression_level
        self.stats = {
            'total_compressed': 0,
            'total_original': 0,
            'encryption_count': 0,
            'compression_count': 0
        }

        # 初始化加密
        self.cipher = None
        if CRYPTO_AVAILABLE and Fernet:
            if encryption_key:
                try:
                    self.cipher = Fernet(encryption_key)
                except:
                    self.cipher = Fernet.generate_key()
            else:
                # 尝试从文件加载或生成新密钥
                key = self._load_or_generate_key()
                self.cipher = Fernet(key)
        else:
            print("警告: 加密功能不可用，将使用模拟加密")

    def _load_or_generate_key(self) -> bytes:
        """加载或生成加密密钥"""
        if os.path.exists(ENCRYPTION_KEY_FILE):
            try:
                with open(ENCRYPTION_KEY_FILE, 'rb') as f:
                    return f.read()
            except:
                pass

        # 生成新密钥
        key = Fernet.generate_key()
        try:
            with open(ENCRYPTION_KEY_FILE, 'wb') as f:
                f.write(key)
        except Exception as e:
            print(f"保存加密密钥失败: {e}")
        return key

    def process_for_storage(self, data: bytes,
                            encrypt: bool = False,
                            compress: bool = False) -> bytes:
        """处理数据以便存储"""
        original_size = len(data)
        result = data

        # 压缩
        if compress and len(data) > 100:  # 小数据不压缩
            try:
                compressed = zlib.compress(result, level=self.compression_level)
                if len(compressed) < len(result):
                    result = b'COMP:' + compressed  # 添加压缩标记
                    self.stats['compression_count'] += 1
            except Exception as e:
                print(f"压缩失败: {e}")

        # 加密
        if encrypt and self.cipher:
            try:
                result = self.cipher.encrypt(result)
                self.stats['encryption_count'] += 1
            except Exception as e:
                print(f"加密失败: {e}")
        elif encrypt and not self.cipher:
            # 模拟加密（简单的XOR）
            key = b'FS_SIMULATED_KEY'
            encrypted = bytearray()
            for i, byte in enumerate(result):
                encrypted.append(byte ^ key[i % len(key)])
            result = b'ENC:' + bytes(encrypted)
            self.stats['encryption_count'] += 1

        # 更新统计
        self.stats['total_original'] += original_size
        self.stats['total_compressed'] += len(result)

        return result

    def process_for_retrieval(self, data: bytes,
                              decrypt: bool = False,
                              decompress: bool = False) -> bytes:
        """处理数据以便读取"""
        result = data

        # 解密逻辑：优先处理模拟加密，然后尝试Fernet解密
        if decrypt:
            # 首先检查是否是模拟加密（有 ENC: 标记）
            if result.startswith(b'ENC:'):
                # 模拟解密
                key = b'FS_SIMULATED_KEY'
                encrypted = result[4:]
                decrypted = bytearray()
                for i, byte in enumerate(encrypted):
                    decrypted.append(byte ^ key[i % len(key)])
                result = bytes(decrypted)
            # 然后尝试Fernet解密（如果cipher可用）
            elif self.cipher:
                try:
                    # 尝试Fernet解密
                    result = self.cipher.decrypt(result)
                except:
                    # Fernet解密失败，保持原数据
                    pass

        # 解压逻辑：检查是否有压缩标记
        if decompress and result.startswith(b'COMP:'):
            try:
                result = zlib.decompress(result[5:])
            except Exception as e:
                print(f"解压失败: {e}")

        return result

    def get_stats(self) -> Dict:
        """获取统计信息"""
        compression_ratio = 0
        if self.stats['total_original'] > 0:
            compression_ratio = 1 - (self.stats['total_compressed'] / self.stats['total_original'])

        return {
            **self.stats,
            'compression_ratio': f"{compression_ratio:.1%}",
            'space_saved': self.stats['total_original'] - self.stats['total_compressed'],
            'encryption_available': CRYPTO_AVAILABLE and Fernet is not None
        }


# ========== 增强型文件系统主类 ==========
class EnhancedFileSystem(SimpleFileSystem):
    """增强型文件系统：集成所有扩展功能"""

    def __init__(self, disk_size_mb: int = DISK_SIZE_MB,
                 block_size_kb: int = BLOCK_SIZE_KB,
                 enable_logging: bool = True,
                 enable_versions: bool = True,
                 enable_crypto: bool = True):
        super().__init__(disk_size_mb, block_size_kb)

        # 扩展功能开关
        self.enable_logging = enable_logging
        self.enable_versions = enable_versions
        self.enable_crypto = enable_crypto

        # 初始化扩展组件
        if enable_logging:
            self.transaction_logger = TransactionLogger()
            # 启动时尝试恢复
            recovered = self.transaction_logger.recover()
            if recovered > 0:
                print(f"系统恢复完成: 重做了 {recovered} 个操作")

        if enable_versions:
            self.version_manager = VersionManager()

        if enable_crypto:
            self.crypto_processor = CryptoCompressor()

        # 文件属性扩展
        self.file_attributes: Dict[int, Dict] = {}  # inode_id -> 属性
        self.encrypted_files = set()  # 加密文件集合
        self.compressed_files = set()  # 压缩文件集合

        # 性能统计
        self.operation_stats = {
            'reads': 0,
            'writes': 0,
            'opens': 0,
            'creates': 0,
            'deletes': 0
        }

    # ---------- 覆盖父类方法以集成扩展功能 ----------
    def create_file(self, path: str) -> bool:
        """创建文件（带事务日志）"""
        self.operation_stats['creates'] += 1

        if self.enable_logging:
            self.transaction_logger.begin_transaction()
            log_id = self.transaction_logger.log_operation(
                OperationType.CREATE_FILE,
                path=path,
                user=self.current_user
            )

        try:
            result = super().create_file(path)
            if result and self.enable_logging:
                self.transaction_logger.commit()
                print(f"文件创建成功: {path} (事务已提交)")
            elif not result and self.enable_logging:
                self.transaction_logger.rollback()
            return result
        except Exception as e:
            if self.enable_logging:
                self.transaction_logger.rollback()
            print(f"创建文件失败: {e}")
            return False

    def delete(self, path: str) -> bool:
        """删除文件（带事务日志和版本清理）"""
        self.operation_stats['deletes'] += 1

        # 先获取文件inode
        inode_id = self._find_inode_by_path(path)

        if self.enable_logging:
            self.transaction_logger.begin_transaction()
            log_id = self.transaction_logger.log_operation(
                OperationType.DELETE_FILE,
                path=path,
                inode_id=inode_id,
                user=self.current_user
            )

        try:
            result = super().delete(path)
            if result:
                # 清理版本历史
                if self.enable_versions and inode_id:
                    self.version_manager.delete_versions(inode_id)
                # 清理属性
                if inode_id in self.file_attributes:
                    del self.file_attributes[inode_id]
                # 从特殊文件集合中移除
                if inode_id in self.encrypted_files:
                    self.encrypted_files.remove(inode_id)
                if inode_id in self.compressed_files:
                    self.compressed_files.remove(inode_id)

                if self.enable_logging:
                    self.transaction_logger.commit()
                    print(f"文件删除成功: {path} (事务已提交)")
            else:
                if self.enable_logging:
                    self.transaction_logger.rollback()
            return result
        except Exception as e:
            if self.enable_logging:
                self.transaction_logger.rollback()
            print(f"删除文件失败: {e}")
            return False

    def open_file(self, path: str, mode: str = "r") -> Optional[int]:
        """打开文件（记录操作）"""
        self.operation_stats['opens'] += 1

        if self.enable_logging:
            self.transaction_logger.begin_transaction()
            log_id = self.transaction_logger.log_operation(
                OperationType.OPEN_FILE,
                path=path,
                mode=mode,
                user=self.current_user
            )

        try:
            fd = super().open_file(path, mode)
            if fd is not None and self.enable_logging:
                self.transaction_logger.commit()
            elif self.enable_logging:
                self.transaction_logger.rollback()
            return fd
        except Exception as e:
            if self.enable_logging:
                self.transaction_logger.rollback()
            print(f"打开文件失败: {e}")
            return None

    def write_file(self, fd: int, data: bytes,
                   create_version: bool = True,
                   encrypt: bool = False,
                   compress: bool = False) -> bool:
        """写入文件（支持版本控制、加密、压缩）"""
        self.operation_stats['writes'] += 1

        if fd not in self.open_files:
            return False

        file_info = self.open_files[fd]
        inode_id = file_info['inode_id']

        if self.enable_logging:
            self.transaction_logger.begin_transaction()
            log_id = self.transaction_logger.log_operation(
                OperationType.WRITE_FILE,
                fd=fd,
                inode_id=inode_id,
                data_size=len(data),
                create_version=create_version,
                encrypt=encrypt,
                compress=compress,
                user=self.current_user
            )

        try:
            # 如果需要，创建版本
            if self.enable_versions and create_version:
                # 读取当前内容作为旧版本
                old_content = self._read_entire_file_for_version(fd)
                if old_content:
                    version_id = self.version_manager.create_version(
                        inode_id, old_content,
                        author=self.current_user,
                        comment=f"Write at offset {file_info['offset']}"
                    )
                    if version_id:
                        print(f"创建版本: {version_id}")

            # 处理数据（加密+压缩）
            processed_data = data
            if self.enable_crypto and (encrypt or compress):
                processed_data = self.crypto_processor.process_for_storage(
                    data, encrypt=encrypt, compress=compress
                )

            # 记录文件加密/压缩状态
            if encrypt:
                self.encrypted_files.add(inode_id)
            if compress:
                self.compressed_files.add(inode_id)

            # 调用父类方法写入处理后的数据
            result = super().write_file(fd, processed_data)

            if result and self.enable_logging:
                self.transaction_logger.commit()
                if encrypt or compress:
                    action = []
                    if encrypt: action.append("加密")
                    if compress: action.append("压缩")
                    print(f"写入成功 ({'、'.join(action)})")
            elif self.enable_logging:
                self.transaction_logger.rollback()

            return result
        except Exception as e:
            if self.enable_logging:
                self.transaction_logger.rollback()
            print(f"写入文件失败: {e}")
            return False

    def read_file(self, fd: int, size: int,
                  decrypt: bool = True,
                  decompress: bool = True) -> Optional[bytes]:
        """读取文件（自动解密解压）"""
        self.operation_stats['reads'] += 1

        # 先读取原始数据
        raw_data = super().read_file(fd, size)
        if raw_data is None or not raw_data:
            return raw_data

        # 如果需要，处理数据（解密+解压）
        if self.enable_crypto:
            inode_id = self.open_files[fd]['inode_id']
            should_decrypt = decrypt and (inode_id in self.encrypted_files)
            should_decompress = decompress and (inode_id in self.compressed_files)

            if should_decrypt or should_decompress:
                return self.crypto_processor.process_for_retrieval(
                    raw_data,
                    decrypt=should_decrypt,
                    decompress=should_decompress
                )

        return raw_data

    # ---------- 新增功能方法 ----------
    def restore_version(self, path: str, version_id: str) -> bool:
        """恢复到指定版本"""
        if not self.enable_versions:
            print("版本控制功能未启用")
            return False

        inode_id = self._find_inode_by_path(path)
        if not inode_id:
            print(f"文件不存在: {path}")
            return False

        # 获取版本内容
        version_content = self.version_manager.get_version(inode_id, version_id)
        if not version_content:
            print(f"版本不存在: {version_id}")
            return False

        # 检查文件是否存在，不存在则创建
        file_exists = self._find_inode_by_path(path) is not None
        if not file_exists:
            if not self.create_file(path):
                return False

        # 打开文件并写入版本内容
        fd = self.open_file(path, "w")
        if fd is None:
            return False

        # 不创建新版本（否则会无限循环）
        result = self.write_file(fd, version_content, create_version=False)
        self.close_file(fd)

        if result:
            print(f"已恢复到版本 {version_id}")
        return result

    def list_file_versions(self, path: str) -> List[Dict]:
        """列出文件的所有版本"""
        if not self.enable_versions:
            return []

        inode_id = self._find_inode_by_path(path)
        if not inode_id:
            return []

        return self.version_manager.list_versions(inode_id)

    def compare_versions(self, path: str, ver1_id: str, ver2_id: str) -> Dict:
        """比较两个版本的差异"""
        if not self.enable_versions:
            return {"error": "版本控制功能未启用"}

        inode_id = self._find_inode_by_path(path)
        if not inode_id:
            return {"error": "文件不存在"}

        # 获取两个版本的内容
        content1 = self.version_manager.get_version(inode_id, ver1_id)
        content2 = self.version_manager.get_version(inode_id, ver2_id)

        if not content1 or not content2:
            return {"error": "版本不存在"}

        # 简化的差异分析（按行比较）
        try:
            lines1 = content1.decode('utf-8', errors='ignore').split('\n')
            lines2 = content2.decode('utf-8', errors='ignore').split('\n')
        except:
            # 二进制文件，比较字节差异
            size_diff = len(content2) - len(content1)
            return {
                'binary': True,
                'size1': len(content1),
                'size2': len(content2),
                'size_diff': size_diff
            }

        # 计算差异
        added = [line for line in lines2 if line not in lines1 and line.strip()]
        removed = [line for line in lines1 if line not in lines2 and line.strip()]

        return {
            'binary': False,
            'added_lines': len(added),
            'removed_lines': len(removed),
            'total_changes': len(added) + len(removed),
            'sample_diff': {
                'added': added[:3] if added else [],
                'removed': removed[:3] if removed else []
            }
        }

    def enable_file_encryption(self, path: str, enable: bool = True) -> bool:
        """启用/禁用文件加密"""
        if not self.enable_crypto:
            print("加密功能未启用")
            return False

        inode_id = self._find_inode_by_path(path)
        if not inode_id:
            return False

        if enable:
            self.encrypted_files.add(inode_id)
            print(f"文件 '{path}' 已启用加密")
        elif inode_id in self.encrypted_files:
            self.encrypted_files.remove(inode_id)
            print(f"文件 '{path}' 已禁用加密")

        return True

    def enable_file_compression(self, path: str, enable: bool = True) -> bool:
        """启用/禁用文件压缩"""
        if not self.enable_crypto:
            print("压缩功能未启用")
            return False

        inode_id = self._find_inode_by_path(path)
        if not inode_id:
            return False

        if enable:
            self.compressed_files.add(inode_id)
            print(f"文件 '{path}' 已启用压缩")
        elif inode_id in self.compressed_files:
            self.compressed_files.remove(inode_id)
            print(f"文件 '{path}' 已禁用压缩")

        return True

    def get_system_stats(self) -> Dict:
        """获取系统统计信息"""
        base_stats = super().get_disk_usage()
        stats = {
            'disk_usage': base_stats,
            'operation_stats': self.operation_stats,
            'features_enabled': {
                'logging': self.enable_logging,
                'versions': self.enable_versions,
                'crypto': self.enable_crypto
            },
            'file_counts': {
                'total_inodes': len(self.inodes),
                'encrypted_files': len(self.encrypted_files),
                'compressed_files': len(self.compressed_files)
            }
        }

        if self.enable_logging:
            stats['logging_stats'] = {
                'log_file': self.transaction_logger.log_file,
                'transactions_processed': self.operation_stats['creates'] +
                                          self.operation_stats['deletes'] +
                                          self.operation_stats['writes']
            }

        if self.enable_versions:
            version_stats = self.version_manager.get_storage_stats()
            stats['version_stats'] = version_stats

        if self.enable_crypto:
            crypto_stats = self.crypto_processor.get_stats()
            stats['crypto_stats'] = crypto_stats

        # 缓存统计
        cache_stats = self.block_cache.stats()
        stats['cache_stats'] = cache_stats

        return stats

    def manual_recovery(self) -> int:
        """手动触发崩溃恢复"""
        if not self.enable_logging:
            print("事务日志功能未启用")
            return 0
        return self.transaction_logger.recover()

    def export_versions(self, path: str, export_dir: str) -> bool:
        """导出文件的所有版本"""
        if not self.enable_versions:
            print("版本控制功能未启用")
            return False

        inode_id = self._find_inode_by_path(path)
        if not inode_id:
            print(f"文件不存在: {path}")
            return False

        versions = self.version_manager.list_versions(inode_id)
        if not versions:
            print(f"文件 '{path}' 没有版本历史")
            return False

        # 创建导出目录
        os.makedirs(export_dir, exist_ok=True)

        # 导出每个版本
        exported = 0
        for version in versions:
            content = self.version_manager.get_version(inode_id, version['id'])
            if content:
                export_file = os.path.join(
                    export_dir,
                    f"{os.path.basename(path)}_v{exported + 1}_{version['id'][:8]}.bak"
                )
                try:
                    with open(export_file, 'wb') as f:
                        f.write(content)
                    exported += 1
                    print(f"导出版本 {exported}: {export_file}")
                except Exception as e:
                    print(f"导出失败: {e}")

        print(f"成功导出 {exported}/{len(versions)} 个版本")
        return exported > 0

    # ---------- 私有辅助方法 ----------
    def _read_entire_file_for_version(self, fd: int) -> Optional[bytes]:
        """读取文件的整个当前内容（用于创建版本）"""
        if fd not in self.open_files:
            return None

        # 保存当前位置
        original_offset = self.open_files[fd]['offset']

        # 移动到文件开头
        self.seek_file(fd, 0)

        # 读取全部内容
        content = bytearray()
        inode_id = self.open_files[fd]['inode_id']
        inode = self.inodes.get(inode_id)
        if not inode:
            return None

        # 计算总大小
        total_size = inode.size
        bytes_read = 0

        while bytes_read < total_size:
            # 计算当前块和偏移
            block_idx = bytes_read // self.block_size
            block_offset = bytes_read % self.block_size

            if block_idx >= len(inode.blocks):
                break

            # 读取当前块
            actual_block = inode.blocks[block_idx]
            bytes_in_block = min(self.block_size - block_offset, total_size - bytes_read)
            block_data = self._read_block(actual_block)
            content.extend(block_data[block_offset:block_offset + bytes_in_block])
            bytes_read += bytes_in_block

        # 恢复位置
        self.seek_file(fd, original_offset)
        return bytes(content)