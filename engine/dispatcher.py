# image_splitter/engine/dispatcher.py
import re
import ast
from PIL import Image
from typing import Dict, Any, List, Tuple
from image_splitter.engine.registry import ProcessorRegistry

class CommandDispatcher:
    """
    Blender 式的命令解析与分发中心
    """
    @classmethod
    def parse_command(cls, cmd_str: str) -> List[Tuple[str, Dict[str, Any]]]:
        ops = []
        tokens = cmd_str.split('|')
        for token in tokens:
            token = token.strip()
            match = re.match(r"(\w+)\((.*)\)", token)
            if match:
                op_name = match.group(1).strip()
                args_str = match.group(2).strip()
                
                props = {}
                if args_str:
                    pairs = re.finditer(r"(\w+)\s*=\s*([^,]+(?:\([^)]*\)[^,]*)?)", args_str)
                    for m in pairs:
                        k, v = m.group(1).strip(), m.group(2).strip()
                        try:
                            props[k] = ast.literal_eval(v)
                        except (ValueError, SyntaxError):
                            props[k] = v
                ops.append((op_name, props))
        return ops

    @classmethod
    def execute_chain(cls, image: Image.Image, cmd_str: str) -> List[Image.Image]:
        ops = cls.parse_command(cmd_str)
        current_images = [image]
        
        for op_name, props in ops:
            processor = ProcessorRegistry.get(op_name)
            next_step_images = []
            
            for img in current_images:
                results = processor.process(img, props)
                for res_img, _ in results:
                    next_step_images.append(res_img)
                
                if img != image:
                    img.close()
            
            current_images = next_step_images
            
        return current_images
