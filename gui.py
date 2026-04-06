# gui.py
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import subprocess
import platform
import time
from PIL import Image, ImageTk
from core import split_image_core
from models import SplitConfig
from typing import List, Optional, Tuple

class UITheme:
    """统一颜色与样式配置"""
    PRIMARY = "#1A73E8"     # Google Blue
    ACCENT = "#D93025"      # Google Red
    SUCCESS = "#1E8E3E"     # Google Green
    INFO = "#00B0FF"        # Azure
    BG_LIGHT = "#F8F9FA"    # Soft Gray
    BG_CANVAS = "#202124"   # Dark Mode Canvas (more premium)
    TEXT_MAIN = "#202124"
    TEXT_SUB = "#5F6368"
    BORDER = "#DADCE0"
    # 跨平台字体建议
    FONT_BOLD = ("Microsoft YaHei", "Segoe UI", "Helvetica", 11, "bold")
    FONT_NORMAL = ("Microsoft YaHei", "Segoe UI", "Helvetica", 9)
    FONT_TITLE = ("Microsoft YaHei", "Segoe UI", "Helvetica", 10, "bold")

class ImageSplitterApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("通用图像处理平台 v3.0 - Operator Engine")
        self.root.geometry("1150x750")
        self.root.minsize(900, 650)
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # 数据变量
        self.input_paths: List[str] = [] 
        self.output_dir = tk.StringVar()
        self.template_var = tk.StringVar(value="{filename}_{index}")
        
        # 动态属性存储 (Blender 式属性面板)
        self.dynamic_vars: Dict[str, tk.StringVar] = {}
        self.active_processor_name = tk.StringVar()
        
        # 预览相关
        self.current_orig_size: Tuple[int, int] = (0, 0)
        self.thumb_img: Optional[Image.Image] = None
        self.preview_ratio: float = 1.0
        self._resize_after_id: Optional[str] = None
        
        self.stop_event = threading.Event()
        self.theme = UITheme()
        
        self.setup_ui()
        self.bind_shortcuts()

    def bind_shortcuts(self):
        self.root.bind("<Return>", lambda e: self.run_batch())
        self.file_listbox.bind("<Delete>", lambda e: self.remove_selected_file())
        self.root.bind("<Control-a>", lambda e: self.file_listbox.select_set(0, tk.END))

    def setup_ui(self):
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # --- 左侧控制区 ---
        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=1)
        
        # 1. 任务选择与文件
        task_lf = ttk.LabelFrame(left_frame, text="1. 任务流配置 (Taskflow)", padding=10)
        task_lf.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(task_lf, text="当前操作符 (Active Operator):", font=self.theme.FONT_BOLD).pack(anchor=tk.W)
        self.proc_combo = ttk.Combobox(task_lf, textvariable=self.active_processor_name, state="readonly")
        from engine.registry import ProcessorRegistry
        processors = ProcessorRegistry.list_all()
        self.proc_combo['values'] = [p.display_name for p in processors]
        self.proc_combo.current(0)
        self.proc_combo.pack(fill=tk.X, pady=(2, 10))
        self.proc_combo.bind("<<ComboboxSelected>>", self.on_processor_change)

        btn_group = ttk.Frame(task_lf)
        btn_group.pack(fill=tk.X)
        ttk.Button(btn_group, text="➕ 添加素材", command=self.select_files).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_group, text="📁 导入目录", command=self.select_folder_input).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_group, text="🗑️ 清空", command=self.clear_files, width=5).pack(side=tk.LEFT, padx=2)
        
        self.file_listbox = tk.Listbox(task_lf, height=6, selectmode=tk.BROWSE, font=self.theme.FONT_NORMAL)
        self.file_listbox.pack(fill=tk.X, pady=5)
        self.file_listbox.bind("<<ListboxSelect>>", self.on_file_select)

        # 2. 动态参数面板 (Properties Panel)
        self.params_lf = ttk.LabelFrame(left_frame, text="2. 操作参数 (Properties)", padding=10)
        self.params_lf.pack(fill=tk.X, padx=5, pady=5)
        self.build_dynamic_params()

        # 3. 输出配置
        out_lf = ttk.LabelFrame(left_frame, text="3. 输出策略 (Export)", padding=10)
        out_lf.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(out_lf, text="命名模板:").pack(anchor=tk.W)
        ttk.Entry(out_lf, textvariable=self.template_var).pack(fill=tk.X, pady=2)
        
        ttk.Label(out_lf, text="输出目录:").pack(anchor=tk.W, pady=(10, 0))
        out_sel = ttk.Frame(out_lf)
        out_sel.pack(fill=tk.X)
        ttk.Entry(out_sel, textvariable=self.output_dir).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(out_sel, text="...", width=3, command=self.select_output).pack(side=tk.LEFT, padx=2)
        
        # 4. 指令日志区
        console_lf = ttk.LabelFrame(left_frame, text="指令控制台 (Log/Console)", padding=5)
        console_lf.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.console_text = tk.Text(console_lf, height=4, font=("Consolas", 9), bg="#1e1e1e", fg="#00FF00", padx=5, pady=5)
        self.console_text.pack(fill=tk.BOTH, expand=True)

        # 执行区域
        action_f = ttk.Frame(left_frame, padding=5)
        action_f.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.btn_run = tk.Button(
            action_f, text="🚀 运行操作 (Run Operator)", command=self.run_batch, 
            bg=self.theme.PRIMARY, fg="white", font=self.theme.FONT_BOLD, 
            height=2, activebackground="#174EA6", relief=tk.FLAT
        )
        self.btn_run.pack(fill=tk.X, pady=(10, 2))
        
        self.progress = ttk.Progressbar(action_f, mode='determinate')
        self.progress.pack(fill=tk.X)
        self.status_label = ttk.Label(action_f, text="等待输入...", foreground=self.theme.TEXT_SUB)
        self.status_label.pack(pady=5)

        # --- 右侧预览区 ---
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=2)
        
        self.info_label = ttk.Label(right_frame, text="实时画布预览", font=self.theme.FONT_TITLE)
        self.info_label.pack(pady=5)
        
        self.canvas = tk.Canvas(right_frame, bg=self.theme.BG_CANVAS, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

    def build_dynamic_params(self):
        """核心：动态构建 UI 参数组件"""
        for widget in self.params_lf.winfo_children():
            widget.destroy()
            
        from engine.registry import ProcessorRegistry
        display_name = self.active_processor_name.get()
        processor = next((p for p in ProcessorRegistry.list_all() if p.display_name == display_name), None)
        if not processor: return

        self.dynamic_vars = {}
        meta = processor.get_ui_metadata()
        
        for i, item in enumerate(meta):
            name, label, default = item["name"], item["label"], item["default"]
            ttk.Label(self.params_lf, text=f"{label}:").grid(row=i, column=0, sticky=tk.W, pady=3)
            var = tk.StringVar(value=str(default))
            self.dynamic_vars[name] = var
            ttk.Entry(self.params_lf, textvariable=var, width=25).grid(row=i, column=1, padx=10, sticky=tk.W)
            var.trace_add("write", lambda *args: self.fast_update_preview())
            var.trace_add("write", lambda *args: self.log_operator())

        self.log_operator()

    def on_processor_change(self, event):
        self.build_dynamic_params()
        self.fast_update_preview()

    def log_operator(self):
        """同步显示 Blender 式指令"""
        from engine.registry import ProcessorRegistry
        display_name = self.active_processor_name.get()
        processor = next((p for p in ProcessorRegistry.list_all() if p.display_name == display_name), None)
        if not processor: return
        
        params = [f"{k}={v.get()}" for k, v in self.dynamic_vars.items()]
        cmd = f"bpy.ops.{processor.name}({', '.join(params)})"
        self.console_text.delete("1.0", tk.END)
        self.console_text.insert(tk.END, cmd)

    def run_batch(self):
        if not self.input_paths:
            messagebox.showwarning("提示", "请先添加图片素材")
            return

        # 动态构造参数
        props = {}
        for k, v in self.dynamic_vars.items():
            val = v.get().strip()
            try:
                if val.isdigit(): props[k] = int(val)
                elif val.replace('.', '', 1).isdigit(): props[k] = float(val)
                elif val.startswith("(") or val.startswith("["): props[k] = eval(val)
                else: props[k] = val
            except: props[k] = val

        props["output_dir"] = self.output_dir.get()
        props["template"] = self.template_var.get()
        
        from engine.registry import ProcessorRegistry
        display_name = self.active_processor_name.get()
        processor = next((p for p in ProcessorRegistry.list_all() if p.display_name == display_name), None)

        self.btn_run.config(state=tk.DISABLED)
        self.progress['value'] = 0
        self.progress['maximum'] = len(self.input_paths)
        
        self.stop_event.clear()
        threading.Thread(target=self.work_thread, args=(list(self.input_paths), processor.name, props), daemon=True).start()

    def work_thread(self, paths, proc_name, props):
        from core import process_image
        success_count = 0
        
        for i, path in enumerate(paths):
            if self.stop_event.is_set(): break
            
            if self.root.winfo_exists():
                self.root.after(0, lambda p=path: self.status_label.config(text=f"正在执行: {os.path.basename(p)}"))
            
            success, _ = process_image(path, proc_name, props)
            if success: success_count += 1
            
            if self.root.winfo_exists():
                self.root.after(0, lambda: self.progress.step(1))
            
        if self.root.winfo_exists():
            self.root.after(0, lambda: self.finish_report(success_count, len(paths)))

    def fast_update_preview(self):
        if not self.thumb_img: return
        self.canvas.delete("overlay")
        
        if self.active_processor_name.get() == "网格切割 (Grid Splitter)":
            try:
                rows = int(self.dynamic_vars.get("rows").get() or 1)
                cols = int(self.dynamic_vars.get("cols").get() or 1)
                off_val = self.dynamic_vars.get("offsets").get() or "(0,0,0,0)"
                offsets = eval(off_val)
                
                cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
                nw, nh = int(self.current_orig_size[0] * self.preview_ratio), int(self.current_orig_size[1] * self.preview_ratio)
                x0, y0 = (cw - nw) // 2, (ch - nh) // 2
                
                cx1, cy1 = x0 + int(offsets[0] * self.preview_ratio), y0 + int(offsets[1] * self.preview_ratio)
                cx2, cy2 = x0 + nw - int(offsets[2] * self.preview_ratio), y0 + nh - int(offsets[3] * self.preview_ratio)
                
                if cx2 > cx1 and cy2 > cy1:
                    self.canvas.create_rectangle(cx1, cy1, cx2, cy2, outline=self.theme.ACCENT, width=2, dash=(4,4), tags="overlay")
                    for i in range(1, rows):
                        y = cy1 + (cy2 - cy1) * i / rows
                        self.canvas.create_line(cx1, y, cx2, y, fill=self.theme.INFO, tags="overlay")
                    for j in range(1, cols):
                        x = cx1 + (cx2 - cx1) * j / cols
                        self.canvas.create_line(x, cy1, x, cy2, fill=self.theme.INFO, tags="overlay")
            except: pass
    def select_files(self):
        file_types = [
            ("Images", "*.jpg *.jpeg *.png *.bmp *.webp"),
            ("JPEG", "*.jpg *.jpeg"),
            ("PNG", "*.png"),
            ("BMP", "*.bmp"),
            ("WebP", "*.webp"),
            ("All Files", "*.*")
        ]
        paths = filedialog.askopenfilenames(title="选择图片", filetypes=file_types)
        if paths:
            new_paths = [p for p in paths if p not in self.input_paths]
            self.input_paths.extend(new_paths)
            self.refresh_file_list()

    def select_folder_input(self):
        folder = filedialog.askdirectory()
        if folder:
            exts = ('.jpg', '.jpeg', '.png', '.bmp', '.webp')
            existing = set(self.input_paths)
            for dir_root, _, files in os.walk(folder):
                for f in files:
                    if f.lower().endswith(exts):
                        full_path = os.path.join(dir_root, f)
                        if full_path not in existing:
                            self.input_paths.append(full_path)
                            existing.add(full_path)
            self.refresh_file_list()

    def clear_files(self):
        self.input_paths = []
        self.thumb_img = None
        self.refresh_file_list()
        self.canvas.delete("all")

    def refresh_file_list(self):
        self.file_listbox.delete(0, tk.END)
        for p in self.input_paths:
            self.file_listbox.insert(tk.END, os.path.basename(p))
        if self.input_paths and not self.output_dir.get():
            self.output_dir.set(os.path.join(os.path.dirname(self.input_paths[0]), "split_output"))

    def select_output(self):
        path = filedialog.askdirectory()
        if path: self.output_dir.set(os.path.normpath(path))

    def on_file_select(self, event):
        selection = self.file_listbox.curselection()
        if selection:
            path = self.input_paths[selection[0]]
            self.load_preview_resource(path)

    def load_preview_resource(self, path: str):
        """仅在切换文件时加载原始资源并生成缩略图"""
        try:
            with Image.open(path) as img:
                self.current_orig_size = img.size
                # 预提取缩略图，避免后续频繁操作原图内存
                thumb = img.copy()
                thumb.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
                self.thumb_img = thumb
            self.load_preview_ui()
        except Exception as e:
            print(f"Failed to load image: {e}")
            self.thumb_img = None
            self.canvas.delete("all")

    def load_preview_ui(self):
        """同步画布尺寸并渲染缩略图"""
        if not self.thumb_img: return
        
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        if cw < 20 or ch < 20: return
        
        # 实际原图到当前画布的缩放比例
        self.preview_ratio = min(cw / self.current_orig_size[0], ch / self.current_orig_size[1])
        nw, nh = int(self.current_orig_size[0] * self.preview_ratio), int(self.current_orig_size[1] * self.preview_ratio)
        
        # 将缩略图再次 resize 到匹配画布的物理像素
        display_img = self.thumb_img.resize((nw, nh), Image.Resampling.BILINEAR)
        self.tk_thumb = ImageTk.PhotoImage(display_img)
        
        self.canvas.delete("all")
        self.canvas.create_image(cw//2, ch//2, image=self.tk_thumb, tags="bg")
        self.fast_update_preview()

    def fast_update_preview(self):
        """极速重绘：只涉及 Canvas 线条坐标更新"""
        if not self.thumb_img: return
        self.canvas.delete("overlay")
        
        try:
            def get_val(v, default=0):
                try: 
                    val = v.get().strip()
                    return int(val) if val else default
                except (ValueError, TypeError): 
                    return default

            rows, cols = max(1, get_val(self.rows_var, 3)), max(1, get_val(self.cols_var, 3))
            ol, ot, oright, ob = get_val(self.off_l), get_val(self.off_t), get_val(self.off_r), get_val(self.off_b)
            
            cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
            nw, nh = int(self.current_orig_size[0] * self.preview_ratio), int(self.current_orig_size[1] * self.preview_ratio)
            x0, y0 = (cw - nw) // 2, (ch - nh) // 2
            
            # 画布缩放后坐标
            cx1, cy1 = x0 + int(ol * self.preview_ratio), y0 + int(ot * self.preview_ratio)
            cx2, cy2 = x0 + nw - int(oright * self.preview_ratio), y0 + nh - int(ob * self.preview_ratio)
            
            if cx2 > cx1 and cy2 > cy1:
                # 计算切片预估尺寸
                target_w = (self.current_orig_size[0] - ol - oright) // cols
                target_h = (self.current_orig_size[1] - ot - ob) // rows
                self.info_label.config(text=f"预期切片尺寸: {target_w} x {target_h} px", foreground=self.theme.PRIMARY)

                # 绘制红虚线裁剪框
                self.canvas.create_rectangle(cx1, cy1, cx2, cy2, outline=self.theme.ACCENT, width=2, dash=(4,4), tags="overlay")
                # 绘制青色切割网格
                for i in range(1, rows):
                    y = cy1 + (cy2 - cy1) * i / rows
                    self.canvas.create_line(cx1, y, cx2, y, fill=self.theme.INFO, tags="overlay")
                for j in range(1, cols):
                    x = cx1 + (cx2 - cx1) * j / cols
                    self.canvas.create_line(x, cy1, x, cy2, fill=self.theme.INFO, tags="overlay")
            else:
                self.info_label.config(text="⚠️ 偏移超出图片范围", foreground=self.theme.ACCENT)
                self.canvas.create_text(cw//2, ch//2, text="⚠️ 偏移范围无效", fill=self.theme.ACCENT, font=("微软雅黑", 14, "bold"), tags="overlay")
        except Exception as e:
            self.info_label.config(text=f"参数错误: {e}", foreground=self.theme.ACCENT)

    def run_batch(self):
        if not self.input_paths:
            messagebox.showwarning("提示", "请先添加待处理的图片流")
            return
            
        try:
            config = SplitConfig(
                rows=int(self.rows_var.get()),
                cols=int(self.cols_var.get()),
                output_dir=self.output_dir.get(),
                template=self.template_var.get(),
                offsets=(
                    int(self.off_l.get() or 0), 
                    int(self.off_t.get() or 0), 
                    int(self.off_r.get() or 0), 
                    int(self.off_b.get() or 0)
                )
            )
        except ValueError as e:
            messagebox.showerror("参数错误", str(e))
            return
        except Exception as e:
            messagebox.showerror("运行错误", f"初始化配置失败: {e}")
            return

        self.btn_run.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.progress['value'] = 0
        self.progress['maximum'] = len(self.input_paths)
        
        self.stop_event.clear()
        args = {
            "paths": list(self.input_paths),
            "config": config
        }
        
        threading.Thread(target=self.work_thread, kwargs=args, daemon=True).start()

    def stop_task(self):
        if messagebox.askyesno("确认", "确定要中断当前处理任务吗？"):
            self.stop_event.set()
            self.status_label.config(text="正在停止...")

    def work_thread(self, paths, config: SplitConfig):
        success_count = 0
        is_aborted = False
        
        for i, path in enumerate(paths):
            if self.stop_event.is_set():
                is_aborted = True
                break
            
            # 安全更新 UI
            if self.root.winfo_exists():
                self.root.after(0, lambda p=path, idx=i, total=len(paths): 
                    self.status_label.config(text=f"正在切割: {os.path.basename(p)} ({idx+1}/{total})") if self.root.winfo_exists() else None)
            
            success, _ = split_image_core(path, config)
            if success: success_count += 1
            
            if self.root.winfo_exists():
                self.root.after(0, lambda: self.progress.step(1) if self.root.winfo_exists() else None)
            
        if self.root.winfo_exists():
            self.root.after(0, lambda: self.finish_report(success_count, len(paths), is_aborted) if self.root.winfo_exists() else None)

    def finish_report(self, s, total, aborted=False):
        if not self.root.winfo_exists(): return
        
        self.btn_run.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        
        if aborted:
            msg = f"任务已中途中断！\n成功: {s} / {total}\n请检查输出目录。"
            self.status_label.config(text="任务已取消", foreground=self.theme.ACCENT)
        else:
            msg = f"处理完成！\n成功: {s} / {total}\n结果已保存至输出目录。"
            self.status_label.config(text="任务已结束", foreground=self.theme.SUCCESS)
            
        messagebox.showinfo("任务报告", msg)
        
        out_path = self.output_dir.get()
        if os.path.exists(out_path):
            self.open_folder(out_path)

    def on_close(self):
        """处理窗口关闭事件"""
        if self.btn_run['state'] == tk.DISABLED:
            if not messagebox.askyesno("确认退出", "任务正在运行，确定退出？"):
                return
            self.stop_event.set()
        self.root.destroy()

    def open_folder(self, path):
        """跨平台打开目录"""
        try:
            curr_os = platform.system()
            if curr_os == "Windows":
                os.startfile(path)
            elif curr_os == "Darwin": # macOS
                subprocess.run(["open", path])
            else: # Linux
                subprocess.run(["xdg-open", path])
        except Exception:
            pass

if __name__ == "__main__":
    root = tk.Tk()
    app = ImageSplitterApp(root)
    root.mainloop()