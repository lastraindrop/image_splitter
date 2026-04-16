# image_splitter/engine/dispatcher.py
import ast
from PIL import Image
from typing import Dict, Any, List, Tuple
from image_splitter.engine.registry import ProcessorRegistry

class CommandDispatcher:
    """
    Blender 式的命令解析与分发中心
    """

    @staticmethod
    def _parse_operator_token(token: str) -> Tuple[str, Dict[str, Any]]:
        try:
            node = ast.parse(token, mode="eval").body
        except SyntaxError as exc:
            raise ValueError(f"无效的命令语法: {token}") from exc

        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            raise ValueError(f"无效的操作符语法: {token}")
        if node.args:
            raise ValueError(f"当前仅支持关键字参数: {token}")

        props: Dict[str, Any] = {}
        for keyword in node.keywords:
            if keyword.arg is None:
                raise ValueError(f"不支持参数展开语法: {token}")
            try:
                props[keyword.arg] = ast.literal_eval(keyword.value)
            except (ValueError, SyntaxError) as exc:
                raise ValueError(f"参数 '{keyword.arg}' 的值无法解析: {token}") from exc

        return node.func.id, props

    @classmethod
    def parse_command(cls, cmd_str: str) -> List[Tuple[str, Dict[str, Any]]]:
        ops = []
        tokens = cmd_str.split('|')
        for token in tokens:
            token = token.strip()
            if not token:
                continue
            ops.append(cls._parse_operator_token(token))
        return ops

    @classmethod
    def execute_chain(cls, image: Image.Image, cmd_str: str) -> List[Image.Image]:
        if not ProcessorRegistry.list_all():
            from image_splitter.core import register_all_processors
            register_all_processors()

        ops = cls.parse_command(cmd_str)
        current_images = [image]
        
        for op_name, props in ops:
            processor = ProcessorRegistry.get(op_name)
            
            # 对参数进行类型清洗与默认值补全
            from image_splitter.engine.config_coercion import coerce_processor_config
            coerced_props = coerce_processor_config(processor, props)
            
            next_step_images = []
            for img in current_images:
                results = processor.process(img, coerced_props)
                for res_img, _ in results:
                    next_step_images.append(res_img)
                
                if img != image:
                    img.close()
            
            current_images = next_step_images
            
        return current_images
