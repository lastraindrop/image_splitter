# gui.py
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import sys
import threading
from PIL import Image, ImageTk
from core import split_image_core
from typing import List, Optional, Tuple

class ImageSplitterApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("网格图片切割工具 v2.1 - 高性能重构版")
        self.root.geometry("1100x700")
        self.root.minsize(800, 600)
        
        # 数据变量
        self.input_paths: List[str] = [] 
        self.output_dir = tk.StringVar()
        self.rows_var = tk.StringVar(value="3")
        self.cols_var = tk.StringVar(value="3")
        self.template_var = tk.StringVar(value="{filename}_{index}")
        
        # 偏移量变量
        self.off_l = tk.StringVar(value="0")
        self.off_t = tk.StringVar(value="0")
        self.off_r = tk.StringVar(value="0")
        self.off_b = tk.StringVar(value="0")
        
        # 预览相关缓存 (针对性能优化)
        self.current_orig_size: Tuple[int, int] = (0, 0)
        self.thumb_img: Optional[Image.Image] = None
        self.tk_thumb: Optional[ImageTk.PhotoImage] = None
        self.preview_ratio: float = 1.0
        self._resize_after_id: Optional[str] = None  # 用于防抖
        
        self.setup_ui()
        
        # 绑定重绘事件: 仅在值变动时触发快速重绘
        for var in [self.rows_var, self.cols_var, self.off_l, self.off_t, self.off_r, self.off_b]:
            var.trace_add("write", lambda *args: self.fast_update_preview())

    def setup_ui(self):
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # --- 左侧控制区 ---
        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=1)
        
        # 1. 文件选择
        file_lf = ttk.LabelFrame(left_frame, text="1. 文件输入", padding=10)
        file_lf.pack(fill=tk.X, padx=5, pady=5)
        
        btn_group = ttk.Frame(file_lf)
        btn_group.pack(fill=tk.X)
        ttk.Button(btn_group, text="添加文件", command=self.select_files).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_group, text="选择文件夹", command=self.select_folder_input).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_group, text="清空列表", command=self.clear_files).pack(side=tk.LEFT, padx=2)
        
        self.file_listbox = tk.Listbox(file_lf, height=8, selectmode=tk.BROWSE)
        self.file_listbox.pack(fill=tk.X, pady=5)
        self.file_listbox.bind("<<ListboxSelect>>", self.on_file_select)
        
        # 2. 切割设置
        sett_lf = ttk.LabelFrame(left_frame, text="2. 切割与偏移设置", padding=10)
        sett_lf.pack(fill=tk.X, padx=5, pady=5)
        
        grid_f = ttk.Frame(sett_lf)
        grid_f.pack(fill=tk.X)
        ttk.Label(grid_f, text="行数 (Rows):").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(grid_f, textvariable=self.rows_var, width=8).grid(row=0, column=1, padx=5)
        ttk.Label(grid_f, text="列数 (Cols):").grid(row=0, column=2, sticky=tk.W, padx=10)
        ttk.Entry(grid_f, textvariable=self.cols_var, width=8).grid(row=0, column=3, padx=5)
        
        ttk.Label(sett_lf, text="裁剪偏移 (PX): 左, 上, 右, 下").pack(fill=tk.X, pady=(10, 2))
        off_f = ttk.Frame(sett_lf)
        off_f.pack(fill=tk.X)
        for i, (lab, var) in enumerate([("L", self.off_l), ("T", self.off_t), ("R", self.off_r), ("B", self.off_b)]):
            ttk.Label(off_f, text=lab).grid(row=0, column=i*2, padx=(5,2))
            ttk.Entry(off_f, textvariable=var, width=6).grid(row=0, column=i*2+1)

        # 3. 命名与输出
        out_lf = ttk.LabelFrame(left_frame, text="3. 命名与输出", padding=10)
        out_lf.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(out_lf, text="命名模板:").pack(anchor=tk.W)
        ttk.Entry(out_lf, textvariable=self.template_var).pack(fill=tk.X, pady=2)
        ttk.Label(out_lf, text="占位符: {filename}, {index}, {row}, {col}, {ext}", font=("", 8), foreground="#666").pack(anchor=tk.W)
        
        ttk.Label(out_lf, text="输出目录:").pack(anchor=tk.W, pady=(10, 0))
        out_sel = ttk.Frame(out_lf)
        out_sel.pack(fill=tk.X)
        ttk.Entry(out_sel, textvariable=self.output_dir).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(out_sel, text="浏览", width=5, command=self.select_output).pack(side=tk.LEFT, padx=2)
        
        # 执行区域
        action_f = ttk.Frame(left_frame, padding=5)
        action_f.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.btn_run = tk.Button(action_f, text="🚀 开始批量切割任务", command=self.run_batch, bg="#1976D2", fg="white", font=("", 11, "bold"), height=2)
        self.btn_run.pack(fill=tk.X, pady=10)
        
        self.progress = ttk.Progressbar(action_f, mode='determinate')
        self.progress.pack(fill=tk.X)
        self.status_label = ttk.Label(action_f, text="准备就绪", foreground="#555")
        self.status_label.pack(pady=5)

        # --- 右侧预览区 ---
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=2)
        
        ttk.Label(right_frame, text="实时网格预览", font=("", 10, "bold")).pack(pady=5)
        self.canvas = tk.Canvas(right_frame, bg="#E0E0E0", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

    def _on_canvas_configure(self, event):
        """防抖: 窗口拖拽期间合并多次 Configure 事件"""
        if self._resize_after_id is not None:
            self.root.after_cancel(self._resize_after_id)
        self._resize_after_id = self.root.after(150, self.load_preview_ui)

    def select_files(self):
        paths = filedialog.askopenfilenames(title="选择图片", filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.webp")])
        if paths:
            new_paths = [p for p in paths if p not in self.input_paths]
            self.input_paths.extend(new_paths)
            self.refresh_file_list()

    def select_folder_input(self):
        folder = filedialog.askdirectory()
        if folder:
            exts = ('.jpg', '.jpeg', '.png', '.bmp', '.webp')
            existing = set(self.input_paths)
            for root, _, files in os.walk(folder):
                for f in files:
                    if f.lower().endswith(exts):
                        full_path = os.path.join(root, f)
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
                thumb.thumbnail((1024, 1024), Image.LANCZOS)
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
        display_img = self.thumb_img.resize((nw, nh), Image.BILINEAR)
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
                # 绘制红虚线裁剪框
                self.canvas.create_rectangle(cx1, cy1, cx2, cy2, outline="#FF1744", width=2, dash=(4,4), tags="overlay")
                # 绘制青色切割网格
                for i in range(1, rows):
                    y = cy1 + (cy2 - cy1) * i / rows
                    self.canvas.create_line(cx1, y, cx2, y, fill="#00B0FF", tags="overlay")
                for j in range(1, cols):
                    x = cx1 + (cx2 - cx1) * j / cols
                    self.canvas.create_line(x, cy1, x, cy2, fill="#00B0FF", tags="overlay")
            else:
                self.canvas.create_text(cw//2, ch//2, text="⚠️ 偏移超出图片范围", fill="#D32F2F", font=("", 12, "bold"), tags="overlay")
        except (ValueError, TypeError, tk.TclError):
            pass

    def run_batch(self):
        if not self.input_paths:
            messagebox.showwarning("提示", "请先添加待处理的图片流")
            return
            
        try:
            rows = int(self.rows_var.get())
            cols = int(self.cols_var.get())
            offs = (
                int(self.off_l.get() or 0), 
                int(self.off_t.get() or 0), 
                int(self.off_r.get() or 0), 
                int(self.off_b.get() or 0)
            )
        except ValueError:
            messagebox.showerror("错误", "行列数和偏移量必须为有效整数")
            return

        self.btn_run.config(state=tk.DISABLED)
        self.progress['value'] = 0
        self.progress['maximum'] = len(self.input_paths)
        
        args = {
            "paths": list(self.input_paths),
            "rows": rows,
            "cols": cols,
            "out": self.output_dir.get(),
            "tmpl": self.template_var.get(),
            "offs": offs
        }
        
        threading.Thread(target=self.work_thread, kwargs=args, daemon=True).start()

    def work_thread(self, paths, rows, cols, out, tmpl, offs):
        success_count = 0
        from core import split_image_core
        
        for i, path in enumerate(paths):
            self.root.after(0, lambda p=path, idx=i, total=len(paths): self.status_label.config(text=f"正在切割: {os.path.basename(p)} ({idx+1}/{total})"))
            
            success, _ = split_image_core(path, rows, cols, out, tmpl, offs)
            if success: success_count += 1
            
            self.root.after(0, lambda: self.progress.step(1))
            
        self.root.after(0, lambda: self.finish_report(success_count, len(paths)))

    def finish_report(self, s, total):
        self.btn_run.config(state=tk.NORMAL)
        self.status_label.config(text="任务已结束")
        messagebox.showinfo("任务报告", f"处理完成！\n成功: {s} / {total}\n结果已保存至输出目录。")
        if sys.platform == 'win32' and os.path.exists(self.output_dir.get()):
            os.startfile(self.output_dir.get())

if __name__ == "__main__":
    root = tk.Tk()
    app = ImageSplitterApp(root)
    root.mainloop()