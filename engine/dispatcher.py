# image_splitter/engine/dispatcher.py
import re
from typing import Dict, Any, List, Tuple
from .registry import ProcessorRegistry
from .operator import Operator

class CommandDispatcher:
    """
    Blender 式的命令解析与分发中心
    支持格式: split(rows=3, cols=2) | resize(w=512, h=512)
    """
    @classmethod
    def parse_command(cls, cmd_str: str) -> List[Tuple[str, Dict[str, Any]]]:
        """
        解析 DSL 命令字符串
        """
        ops = []
        # 分隔管道符 |
        tokens = cmd_str.split('|')
        for token in tokens:
            token = token.strip()
            # 匹配 op_name(args)
            match = re.match(r"(\w+)\((.*)\)", token)
            if match:
                op_name = match.group(1)
                args_str = match.group(2)
                
                # 解析参数 k=v
                props = {}
                if args_str:
                    # 简单解析 k=v, k=v
                    for arg in args_str.split(','):
                        k, v = arg.split('=')
                        k = k.strip()
                        v = v.strip()
                        # 自动类型转换
                        if v.isdigit(): v = int(v)
                        elif v.replace('.', '', 1).isdigit(): v = float(v)
                        elif v.lower() in ('true', 'false'): v = v.lower() == 'true'
                        props[k] = v
                ops.append((op_name, props))
        return ops

    @classmethod
    def execute_chain(cls, image, cmd_str: str):
        """
        链式执行操作符
        """
        ops = cls.parse_command(cmd_str)
        current_images = [image]
        
        for op_name, props in ops:
            processor = ProcessorRegistry.get(op_name)
            next_step_images = []
            for img in current_images:
                # 适配原有的 BaseProcessor 结构
                # 未来我们可以全面迁移到 Operator 基类
                results = processor.process(img, props)
                # results 是 [(Image, Context), ...]
                next_step_images.extend([r[0] for r in results])
            current_images = next_step_images
            
        return current_images
