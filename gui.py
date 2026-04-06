# image_splitter/gui.py
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import os
import ast
import platform
import subprocess
from PIL import Image, ImageTk
from image_splitter.core import process_image, register_all_processors
from image_splitter.engine.registry import ProcessorRegistry

class UITheme:
    """主题配置"""
    DARK_BG = "#1e1e1e"
    DARK_FG = "#d4d4d4"
    ACCENT = "#007acc"
    PRIMARY = "#3b82f6"
    SUCCESS = "#10b981"
    INFO = "#3b82f6"
    PANEL_BG = "#252526"

class ImageSplitterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Image Splitter Pro - 图像处理增强版")
        self.root.geometry("1100x750")
        self.theme = UITheme()
        
        # 1. 状态管理
        self.current_files = []
        self.current_orig_size = (0, 0)
        self.thumb_img = None
        self.tk_thumb = None
        self.preview_ratio = 1.0
        self.stop_event = threading.Event()
        self.dynamic_vars = {}
        
        # 2. 自动注册
        register_all_processors()
        
        # 3. 初始化 UI
        self._setup_style()
        self._create_widgets()

    def _setup_style(self):
        self.root.configure(bg=self.theme.DARK_BG)
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TFrame", background=self.theme.DARK_BG)
        style.configure("TLabel", background=self.theme.DARK_BG, foreground=self.theme.DARK_FG, font=("Microsoft YaHei UI", 10))
        style.configure("Primary.TButton", background=self.theme.PRIMARY, foreground="white", font=("Microsoft YaHei UI", 10, "bold"))
        style.map("Primary.TButton", background=[('active', '#2563eb')])

    def _create_widgets(self):
        # 左右分栏
        self.paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True)

        # --- 左侧控制面板 ---
        self.left_panel = tk.Frame(self.paned, bg=self.theme.PANEL_BG, width=320)
        self.paned.add(self.left_panel, weight=0)

        # 标题
        tk.Label(self.left_panel, text="操作配置", font=("Microsoft YaHei UI", 12, "bold"), 
                 bg=self.theme.PANEL_BG, fg=self.theme.PRIMARY).pack(pady=15, padx=20, anchor=tk.W)

        # 处理器选择
        tk.Label(self.left_panel, text="选择功能:", bg=self.theme.PANEL_BG).pack(padx=20, anchor=tk.W)
        self.active_processor_name = tk.StringVar()
        processors = [p.display_name for p in ProcessorRegistry.list_all()]
        self.processor_combo = ttk.Combobox(self.left_panel, textvariable=self.active_processor_name, values=processors, state="readonly")
        self.processor_combo.pack(fill=tk.X, padx=20, pady=5)
        self.processor_combo.bind("<<ComboboxSelected>>", self._on_processor_changed)
        if processors: self.processor_combo.current(0)

        # 动态参数容器
        self.props_frame = tk.Frame(self.left_panel, bg=self.theme.PANEL_BG)
        self.props_frame.pack(fill=tk.BOTH, expand=False, padx=20, pady=10)

        # 默认保存选项
        tk.Label(self.left_panel, text="输出配置:", bg=self.theme.PANEL_BG, fg=self.theme.PRIMARY).pack(padx=20, pady=(15, 5), anchor=tk.W)
        
        tk.Label(self.left_panel, text="命名模板:", bg=self.theme.PANEL_BG).pack(padx=20, anchor=tk.W)
        self.template_var = tk.StringVar(value="{filename}_{index}")
        tk.Entry(self.left_panel, textvariable=self.template_var, bg=self.theme.DARK_BG, fg="white", insertbackground="white").pack(fill=tk.X, padx=20, pady=5)

        # 底部按钮区
        self.bottom_btn_frame = tk.Frame(self.left_panel, bg=self.theme.PANEL_BG)
        self.bottom_btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=20, padx=20)
        
        self.btn_run = ttk.Button(self.bottom_btn_frame, text="🚀 运行任务", style="Primary.TButton", command=self.run_batch)
        self.btn_run.pack(fill=tk.X, pady=5)
        
        self.btn_stop = ttk.Button(self.bottom_btn_frame, text="⏹ 停止运行", state=tk.DISABLED, command=self.stop_tasks)
        self.btn_stop.pack(fill=tk.X, pady=5)

        # --- 右侧预览与列表 ---
        self.right_container = tk.Frame(self.paned, bg=self.theme.DARK_BG)
        self.paned.add(self.right_container, weight=1)

        # 画布与图片信息
        self.preview_frame = tk.Frame(self.right_container, bg=self.theme.DARK_BG, bd=1, relief=tk.SOLID)
        self.preview_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        self.info_label = tk.Label(self.preview_frame, text="请先选择图片文件", fg=self.theme.DARK_FG)
        self.info_label.pack(pady=5)

        self.canvas = tk.Canvas(self.preview_frame, bg="#101010", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # 文件列表区
        self.list_frame = tk.Frame(self.right_container, bg=self.theme.DARK_BG, height=150)
        self.list_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.btn_select = ttk.Button(self.list_frame, text="📂 选择图片 (支持多选/拖入)", command=self.select_files)
        self.btn_select.pack(side=tk.TOP, fill=tk.X)
        
        self.file_listbox = tk.Listbox(self.list_frame, bg=self.theme.PANEL_BG, fg=self.theme.DARK_FG, 
                                       borderwidth=0, height=5, selectbackground=self.theme.ACCENT)
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=5)
        self.file_listbox.bind("<<ListboxSelect>>", self._on_file_selected)

        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(self.right_container, length=100, mode='determinate', variable=self.progress_var)
        self.progress.pack(fill=tk.X, padx=20, pady=10)
        
        self.status_label = tk.Label(self.right_container, text="就绪", font=("Consolas", 9))
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X, padx=20)

        # 初始化参数列表
        self._on_processor_changed()

    def _on_processor_changed(self, event=None):
        """当处理器切换时，动态生成 UI 参数组件"""
        for child in self.props_frame.winfo_children():
             child.destroy()
        self.dynamic_vars = {}

        display_name = self.active_processor_name.get()
        processor = next((p for p in ProcessorRegistry.list_all() if p.display_name == display_name), None)
        if not processor: return

        for meta in processor.get_ui_metadata():
            frame = tk.Frame(self.props_frame, bg=self.theme.PANEL_BG)
            frame.pack(fill=tk.X, pady=2)
            tk.Label(frame, text=meta["label"], bg=self.theme.PANEL_BG, font=("Microsoft YaHei UI", 9)).pack(side=tk.LEFT)
            
            var = tk.StringVar(value=str(meta["default"]))
            self.dynamic_vars[meta["name"]] = var
            # 实时更新预览
            entry = tk.Entry(frame, textvariable=var, bg=self.theme.DARK_BG, fg="white", width=12, insertbackground="white")
            entry.pack(side=tk.RIGHT)
            entry.bind("<KeyRelease>", lambda e: self.fast_update_preview())

        self.fast_update_preview()

    def run_batch(self):
        if not self.current_files:
            messagebox.showwarning("提示", "请先选择需要处理的图片")
            return
            
        output_dir = filedialog.askdirectory(title="选择输出保存目录")
        if not output_dir: return

        # 构建配置
        display_name = self.active_processor_name.get()
        processor = next((p for p in ProcessorRegistry.list_all() if p.display_name == display_name), None)
        if not processor: return

        config = {k: v.get() for k, v in self.dynamic_vars.items()}
        config["output_dir"] = output_dir
        config["template"] = self.template_var.get()
        
        self.btn_run.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.stop_event.clear()
        
        threading.Thread(target=self.work_thread, args=(processor.name, config, output_dir), daemon=True).start()

    def work_thread(self, p_name, config, output_dir):
        total = len(self.current_files)
        success_count = 0
        
        from image_splitter.core import batch_process_images
        
        for i, (path, is_success, msg) in enumerate(batch_process_images(self.current_files, p_name, config)):
            if self.stop_event.is_set():
                self.root.after(0, lambda: self.finish_report(success_count, total, True))
                return

            if is_success: success_count += 1
            
            progress = (i + 1) / total * 100
            self.root.after(0, lambda p=progress, m=msg: self.update_progress(p, m))

        self.root.after(0, lambda: self.finish_report(success_count, total))
        # 完成后尝试打开目录
        try: os.startfile(output_dir) if platform.system() == "Windows" else None
        except: pass

    def update_progress(self, p, msg):
        self.progress_var.set(p)
        self.status_label.config(text=msg)

    def stop_tasks(self):
        if messagebox.askyesno("停止", "确定要中断正在运行的任务吗？"):
            self.stop_event.set()
            self.status_label.config(text="正在停止...")

    def fast_update_preview(self):
        """核心：通过操作符自带的渲染逻辑重绘预览"""
        if not self.thumb_img: return
        self.canvas.delete("overlay")
        
        display_name = self.active_processor_name.get()
        processor = next((p for p in ProcessorRegistry.list_all() if p.display_name == display_name), None)
        if not processor: return

        # 尺寸与位置计算
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        nw, nh = int(self.current_orig_size[0] * self.preview_ratio), int(self.current_orig_size[1] * self.preview_ratio)
        x0, y0 = (cw - nw) // 2, (ch - nh) // 2

        # 调用处理器自身的绘制逻辑
        processor.draw_preview(
            self.canvas, 
            thumb_size=(nw, nh), 
            canvas_pos=(x0, y0), 
            ratio=self.preview_ratio, 
            props=self.dynamic_vars, 
            theme=self.theme
        )

    def select_files(self):
        file_types = [("Images", "*.jpg *.jpeg *.png *.bmp *.webp"), ("All Files", "*.*")]
        files = filedialog.askopenfilenames(title="选择图片", filetypes=file_types)
        if files:
            self.current_files = list(files)
            self.file_listbox.delete(0, tk.END)
            for f in self.current_files:
                 self.file_listbox.insert(tk.END, os.path.basename(f))
            self.file_listbox.selection_set(0)
            self._on_file_selected()

    def _on_file_selected(self, event=None):
        selection = self.file_listbox.curselection()
        if not selection: return
        
        image_path = self.current_files[selection[0]]
        try:
            with Image.open(image_path) as img:
                self.current_orig_size = img.size
                img.verify() # 验证
                
            # 重新打开以便缩放
            with Image.open(image_path) as img:
                # 预生成一个略大于预览区的原比例缩略图，避免后续重复 IO
                # 同时处理包含透明通道的预览背景
                thumb = img.convert("RGBA")
                thumb.thumbnail((1200, 1200))
                self.thumb_img = thumb
            self._render_canvas()
        except:
            self.thumb_img = None
            self.canvas.delete("all")

    def _on_canvas_configure(self, event):
        self.root.after(50, self._render_canvas)

    def _render_canvas(self):
        if not self.thumb_img: return
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        if cw < 20 or ch < 20: return

        self.preview_ratio = min(cw / self.current_orig_size[0], ch / self.current_orig_size[1])
        nw, nh = int(self.current_orig_size[0] * self.preview_ratio), int(self.current_orig_size[1] * self.preview_ratio)

        display_img = self.thumb_img.resize((nw, nh), Image.Resampling.BILINEAR)
        self.tk_thumb = ImageTk.PhotoImage(display_img)

        self.canvas.delete("all")
        self.canvas.create_image(cw//2, ch//2, image=self.tk_thumb, tags="bg")
        self.fast_update_preview()

    def finish_report(self, s, total, aborted=False):
        self.btn_run.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)

        if aborted:
            msg = f"任务已中断！\n成功: {s} / {total}"
            self.status_label.config(text="任务已取消", foreground=self.theme.ACCENT)
        else:
            msg = f"任务完成！\n成功: {s} / {total}"
            self.status_label.config(text="任务已结束", foreground=self.theme.SUCCESS)
        messagebox.showinfo("任务报告", msg)

    def on_close(self):
        if self.btn_run['state'] == tk.DISABLED:
            if not messagebox.askyesno("退出", "任务正在运行，确定要强制退出吗？"):
                return
            self.stop_event.set()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ImageSplitterApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
