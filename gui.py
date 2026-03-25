# gui.py
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import sys
import threading
from PIL import Image, ImageTk
from core import split_image_core, batch_process_images

class ImageSplitterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("网格图片切割工具 v2.0 - 进阶增强版")
        self.root.geometry("1000x650")
        self.root.minsize(800, 600)
        
        # 数据变量
        self.input_paths = [] # 存储选中的所有文件路径
        self.output_dir = tk.StringVar()
        self.rows_var = tk.IntVar(value=3)
        self.cols_var = tk.IntVar(value=3)
        self.template_var = tk.StringVar(value="{filename}_{index}")
        
        # 偏移量变量
        self.off_l = tk.IntVar(value=0)
        self.off_t = tk.IntVar(value=0)
        self.off_r = tk.IntVar(value=0)
        self.off_b = tk.IntVar(value=0)
        
        # 预览相关
        self.current_preview_img = None
        self.tk_preview_img = None
        
        self.setup_ui()
        
        # 绑定重绘事件
        self.rows_var.trace_add("write", lambda *args: self.update_preview())
        self.cols_var.trace_add("write", lambda *args: self.update_preview())
        self.off_l.trace_add("write", lambda *args: self.update_preview())
        self.off_t.trace_add("write", lambda *args: self.update_preview())
        self.off_r.trace_add("write", lambda *args: self.update_preview())
        self.off_b.trace_add("write", lambda *args: self.update_preview())

    def setup_ui(self):
        # 主容器：左边控制，右边预览
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # --- 左侧控制区 ---
        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=1)
        
        # 1. 文件选择
        file_labelframe = ttk.LabelFrame(left_frame, text="1. 文件输入", padding=10)
        file_labelframe.pack(fill=tk.X, padx=5, pady=5)
        
        btn_group = ttk.Frame(file_labelframe)
        btn_group.pack(fill=tk.X)
        ttk.Button(btn_group, text="选择文件(多选)", command=self.select_files).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_group, text="选择文件夹", command=self.select_folder_input).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_group, text="清空列表", command=self.clear_files).pack(side=tk.LEFT, padx=2)
        
        self.file_listbox = tk.Listbox(file_labelframe, height=6)
        self.file_listbox.pack(fill=tk.X, pady=5)
        self.file_listbox.bind("<<ListboxSelect>>", self.on_file_select)
        
        # 2. 切割设置
        settings_frame = ttk.LabelFrame(left_frame, text="2. 切割与偏移设置", padding=10)
        settings_frame.pack(fill=tk.X, padx=5, pady=5)
        
        grid_sett = ttk.Frame(settings_frame)
        grid_sett.pack(fill=tk.X)
        ttk.Label(grid_sett, text="行数 (Rows):").grid(row=0, column=0, sticky=tk.W, pady=2)
        tk.Spinbox(grid_sett, from_=1, to=100, textvariable=self.rows_var, width=8).grid(row=0, column=1, padx=5)
        ttk.Label(grid_sett, text="列数 (Cols):").grid(row=0, column=2, sticky=tk.W, padx=10)
        tk.Spinbox(grid_sett, from_=1, to=100, textvariable=self.cols_var, width=8).grid(row=0, column=3, padx=5)
        
        # 偏移设置 (新功能)
        ttk.Label(settings_frame, text="边缘偏移 (像素): 左, 上, 右, 下").pack(fill=tk.X, pady=(10, 2))
        off_frame = ttk.Frame(settings_frame)
        off_frame.pack(fill=tk.X)
        for i, (lab, var) in enumerate([("L", self.off_l), ("T", self.off_t), ("R", self.off_r), ("B", self.off_b)]):
            ttk.Label(off_frame, text=lab).grid(row=0, column=i*2, padx=(5,2))
            ttk.Entry(off_frame, textvariable=var, width=5).grid(row=0, column=i*2+1)

        # 3. 命名与输出
        out_frame = ttk.LabelFrame(left_frame, text="3. 命名与输出", padding=10)
        out_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(out_frame, text="命名模板:").pack(anchor=tk.W)
        ttk.Entry(out_frame, textvariable=self.template_var).pack(fill=tk.X, pady=2)
        ttk.Label(out_frame, text="提示: {filename}, {index}, {row}, {col}", font=("", 8), foreground="gray").pack(anchor=tk.W)
        
        ttk.Label(out_frame, text="输出目录:").pack(anchor=tk.W, pady=(10, 0))
        out_sel = ttk.Frame(out_frame)
        out_sel.pack(fill=tk.X)
        ttk.Entry(out_sel, textvariable=self.output_dir).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(out_sel, text="浏览", width=5, command=self.select_output).pack(side=tk.LEFT, padx=2)
        
        # 执行按钮
        self.btn_run = tk.Button(left_frame, text="🚀 开始批量切割", command=self.run_batch, bg="#2196F3", fg="white", font=("微软雅黑", 12, "bold"), height=2)
        self.btn_run.pack(fill=tk.X, padx=5, pady=20)
        
        self.progress = ttk.Progressbar(left_frame, mode='determinate')
        self.progress.pack(fill=tk.X, padx=5)
        self.status_label = ttk.Label(left_frame, text="准备就绪")
        self.status_label.pack(pady=5)

        # --- 右侧预览区 ---
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=2)
        
        ttk.Label(right_frame, text="实时预览 (选中的图片)").pack(pady=5)
        self.canvas = tk.Canvas(right_frame, bg="#f0f0f0", highlightthickness=1, highlightbackground="#ccc")
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.canvas.bind("<Configure>", lambda e: self.update_preview())

    def select_files(self):
        paths = filedialog.askopenfilenames(title="选择图片文件", filetypes=[("图像文件", "*.jpg *.jpeg *.png *.bmp *.webp"), ("所有文件", "*.*")])
        if paths:
            self.input_paths.extend(list(paths))
            self.refresh_file_list()

    def select_folder_input(self):
        folder = filedialog.askdirectory(title="选择文件夹")
        if folder:
            for root, dirs, files in os.walk(folder):
                for f in files:
                    if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.webp')):
                        self.input_paths.append(os.path.join(root, f))
            self.refresh_file_list()

    def clear_files(self):
        self.input_paths = []
        self.refresh_file_list()
        self.canvas.delete("all")

    def refresh_file_list(self):
        self.file_listbox.delete(0, tk.END)
        for p in self.input_paths:
            self.file_listbox.insert(tk.END, os.path.basename(p))
        if self.input_paths and not self.output_dir.get():
            self.output_dir.set(os.path.join(os.path.dirname(self.input_paths[0]), "output"))

    def select_output(self):
        path = filedialog.askdirectory(title="选择保存目录")
        if path:
            self.output_dir.set(os.path.normpath(path))

    def on_file_select(self, event):
        selection = self.file_listbox.curselection()
        if selection:
            idx = selection[0]
            path = self.input_paths[idx]
            self.load_preview(path)

    def load_preview(self, path):
        try:
            self.current_preview_img = Image.open(path)
            self.update_preview()
        except:
            self.current_preview_img = None
            self.canvas.delete("all")

    def update_preview(self):
        if not self.current_preview_img:
            return
            
        self.canvas.delete("all")
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 10 or ch < 10: return
        
        # 计算缩放
        img_w, img_h = self.current_preview_img.size
        ratio = min(cw / img_w, ch / img_h)
        nw, nh = int(img_w * ratio), int(img_h * ratio)
        
        # 居中坐标
        x0 = (cw - nw) // 2
        y0 = (ch - nh) // 2
        
        resized = self.current_preview_img.resize((nw, nh), Image.LANCZOS)
        self.tk_preview_img = ImageTk.PhotoImage(resized)
        self.canvas.create_image(cw//2, ch//2, image=self.tk_preview_img)
        
        # 绘制偏移矩形
        try:
            ol, ot, oright, ob = self.off_l.get(), self.off_t.get(), self.off_r.get(), self.off_b.get()
            # 缩放到画布坐标
            sol, sot = ol * ratio, ot * ratio
            sor, sob = oright * ratio, ob * ratio
            
            # 画布上的有效裁剪框
            cx1, cy1 = x0 + sol, y0 + sot
            cx2, cy2 = x0 + nw - sor, y0 + nh - sob
            
            if cx2 > cx1 and cy2 > cy1:
                # 绘制灰色遮罩或边框表示偏移
                self.canvas.create_rectangle(cx1, cy1, cx2, cy2, outline="red", dash=(4,4))
                
                # 绘制网格线
                rows = self.rows_var.get()
                cols = self.cols_var.get()
                if rows > 0 and cols > 0:
                    for i in range(1, rows):
                        y = cy1 + (cy2 - cy1) * i / rows
                        self.canvas.create_line(cx1, y, cx2, y, fill="cyan")
                    for j in range(1, cols):
                        x = cx1 + (cx2 - cx1) * j / cols
                        self.canvas.create_line(x, cy1, x, cy2, fill="cyan")
        except:
            pass

    def run_batch(self):
        if not self.input_paths:
            messagebox.showwarning("警告", "请先选择需要处理的文件！")
            return
        if not self.output_dir.get():
            messagebox.showwarning("警告", "请选择保存目录！")
            return
            
        self.btn_run.config(state=tk.DISABLED)
        self.progress['value'] = 0
        self.progress['maximum'] = len(self.input_paths)
        
        # 使用线程处理防止 GUI 假死
        thread = threading.Thread(target=self.process_thread)
        thread.start()

    def process_thread(self):
        rows = self.rows_var.get()
        cols = self.cols_var.get()
        template = self.template_var.get()
        out_root = self.output_dir.get()
        offsets = (self.off_l.get(), self.off_t.get(), self.off_r.get(), self.off_b.get())
        
        success_count = 0
        for i, path in enumerate(self.input_paths):
            self.root.after(0, lambda v=i: self.status_label.config(text=f"正在处理: {os.path.basename(path)} ({v+1}/{len(self.input_paths)})"))
            
            success, msg = split_image_core(path, rows, cols, out_root, template, offsets)
            if success:
                success_count += 1
                
            self.root.after(0, lambda v=i+1: self.progress.step(1))
            
        self.root.after(0, lambda: self.finish_batch(success_count, len(self.input_paths)))

    def finish_batch(self, success, total):
        self.btn_run.config(state=tk.NORMAL)
        self.status_label.config(text="任务完成")
        messagebox.showinfo("任务完成", f"批量处理完成！\n成功: {success}\n失败: {total - success}\n保存至: {self.output_dir.get()}")
        if sys.platform == 'win32' and os.path.exists(self.output_dir.get()):
            os.startfile(self.output_dir.get())

if __name__ == "__main__":
    root = tk.Tk()
    app = ImageSplitterApp(root)
    root.mainloop()
