import re
import ast
from decimal import Decimal, ROUND_DOWN, ROUND_UP
import decimal
import tkinter as tk
from tkinter import ttk, messagebox
import sympy as sp
from sympy.parsing.latex import parse_latex as sp_parse_latex
from collections import deque
import datetime

# --- 解决 Windows 高分屏下界面模糊和字体过小的问题 ---
import ctypes
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# --- 引入 Matplotlib ---
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
matplotlib.rcParams['axes.unicode_minus'] = False

decimal.getcontext().prec = 50

# ================= 1. 有效数字核心引擎 =================
class SigFigNumber:
    def __init__(self, val_str):
        self.val_str = str(val_str).strip()
        self.raw_val = Decimal(self.val_str)
        self.is_exact = False
        self.sigfigs = float('inf')
        self.decimals = float('inf')
        
        if 'e' in self.val_str.lower():
            mantissa = self.val_str.lower().split('e')[0]
            if '.' in mantissa:
                self.decimals = len(mantissa.split('.')[1])
                self.sigfigs = len(mantissa.replace('.', '').lstrip('0'))
            else:
                self.decimals = 0
                self.sigfigs = len(mantissa.lstrip('0'))
        elif '.' in self.val_str:
            self.decimals = len(self.val_str.split('.')[1])
            self.sigfigs = len(self.val_str.replace('.', '').lstrip('0'))
        else:
            self.is_exact = True

    @staticmethod
    def _custom_round(val, decimals):
        quant = Decimal(1).scaleb(-decimals)
        shifted = val.scaleb(decimals)
        s_shifted = str(shifted)
        
        if '.' in s_shifted:
            int_part, frac_part = s_shifted.split('.')
        else:
            int_part, frac_part = s_shifted, ''
            
        if len(frac_part) == 0: return val.quantize(quant, rounding=ROUND_DOWN)
        first_discarded = int(frac_part[0])
        
        if first_discarded < 5: return val.quantize(quant, rounding=ROUND_DOWN)
        elif first_discarded > 5: return val.quantize(quant, rounding=ROUND_UP)
        else:
            prev_digit = int(int_part[-1]) if int_part and int_part != '-' else 0
            return val.quantize(quant, rounding=ROUND_UP if prev_digit % 2 != 0 else ROUND_DOWN)

    @classmethod
    def _round_to_sigfigs(cls, val, sigfigs):
        if sigfigs == float('inf') or val == 0: return val
        exp = val.adjusted()
        return cls._custom_round(val, sigfigs - 1 - exp)

    def get_result(self):
        if self.is_exact: return self.raw_val
        return self._round_to_sigfigs(self.raw_val, self.sigfigs)

    def __add__(self, other):
        if self.is_exact and other.is_exact: return SigFigNumber(str(self.raw_val + other.raw_val))
        new_decimals = min(self.decimals, other.decimals) if not (self.is_exact or other.is_exact) else (other.decimals if self.is_exact else self.decimals)
        new_raw = self.raw_val + other.raw_val
        res = SigFigNumber(str(new_raw))
        res.is_exact, res.decimals = False, new_decimals
        rounded_val = self._custom_round(new_raw, new_decimals)
        s = str(rounded_val)
        res.sigfigs = len(s.replace('.', '').lstrip('0')) if '.' in s else len(s.lstrip('0'))
        return res

    def __sub__(self, other): return self.__add__(SigFigNumber(str(-other.raw_val)))

    def __mul__(self, other):
        if self.is_exact and other.is_exact: return SigFigNumber(str(self.raw_val * other.raw_val))
        new_sigfigs = min(self.sigfigs, other.sigfigs) if not (self.is_exact or other.is_exact) else (other.sigfigs if self.is_exact else self.sigfigs)
        new_raw = self.raw_val * other.raw_val
        res = SigFigNumber(str(new_raw))
        res.is_exact, res.sigfigs = False, new_sigfigs
        res.decimals = max(0, new_sigfigs - 1 - (new_raw.adjusted() if new_raw != 0 else 0))
        return res

    def __truediv__(self, other):
        if self.is_exact and other.is_exact: return SigFigNumber(str(self.raw_val / other.raw_val))
        new_sigfigs = min(self.sigfigs, other.sigfigs) if not (self.is_exact or other.is_exact) else (other.sigfigs if self.is_exact else self.sigfigs)
        new_raw = self.raw_val / other.raw_val
        res = SigFigNumber(str(new_raw))
        res.is_exact, res.sigfigs = False, new_sigfigs
        res.decimals = max(0, new_sigfigs - 1 - (new_raw.adjusted() if new_raw != 0 else 0))
        return res
        
    def __pow__(self, other):
        res_raw = self.raw_val ** other.raw_val
        if self.is_exact and other.is_exact: return SigFigNumber(str(res_raw))
        return self * SigFigNumber(str(res_raw))

    def __neg__(self):
        res = SigFigNumber(str(-self.raw_val))
        res.is_exact, res.sigfigs, res.decimals = self.is_exact, self.sigfigs, self.decimals
        return res

class AstEvaluator(ast.NodeVisitor):
    def visit_Expression(self, node): return self.visit(node.body)
    def visit_BinOp(self, node):
        left, right = self.visit(node.left), self.visit(node.right)
        if isinstance(node.op, ast.Add): return left + right
        elif isinstance(node.op, ast.Sub): return left - right
        elif isinstance(node.op, ast.Mult): return left * right
        elif isinstance(node.op, ast.Div): return left / right
        elif isinstance(node.op, ast.Pow): return left ** right
        raise NotImplementedError("不支持的运算符")
    def visit_UnaryOp(self, node):
        operand = self.visit(node.operand)
        return -operand if isinstance(node.op, ast.USub) else operand
    def visit_Constant(self, node): return SigFigNumber(str(node.value))
    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id == 'SigFigNumber':
            return SigFigNumber(node.args[0].value)
        raise NotImplementedError()

def parse_latex_numeric(latex_str):
    s = latex_str.replace('\\times', '*').replace('\\div', '/').replace('\\left', '').replace('\\right', '').replace('$', '').replace(' ', '')
    s = re.sub(r'10\^\{([^}]+)\}', r'10**(\1)', s)
    s = re.sub(r'10\^(-?\d+)', r'10**(\1)', s)
    while '\\frac' in s:
        idx = s.find('\\frac')
        start_num = s.find('{', idx)
        brace = 0
        for i in range(start_num, len(s)):
            if s[i] == '{': brace += 1
            elif s[i] == '}':
                brace -= 1
                if brace == 0: break
        num = s[start_num+1:i]
        start_den = s.find('{', i)
        brace = 0
        for j in range(start_den, len(s)):
            if s[j] == '{': brace += 1
            elif s[j] == '}':
                brace -= 1
                if brace == 0: break
        den = s[start_den+1:j]
        s = s[:idx] + f'(({num})/({den}))' + s[j+1:]
    return s

def wrap_numbers(expr):
    return re.sub(r'(?<![\w\.\'])(-?\d*\.?\d+(?:[eE][+-]?\d+)?)', r"SigFigNumber('\1')", expr)

def eval_numeric(expression, mode):
    try:
        py_expr = parse_latex_numeric(expression) if mode == 'latex' else expression
        tree = ast.parse(wrap_numbers(py_expr), mode='eval')
        return format(AstEvaluator().visit(tree).get_result(), 'f')
    except Exception as e:
        return f"计算错误: {str(e)}"


# ================= 2. 符号微积分引擎 =================
def eval_symbolic(expression, mode):
    local_dict = {
        'x': sp.Symbol('x'), 'y': sp.Symbol('y'), 'z': sp.Symbol('z'), 'n': sp.Symbol('n'), 't': sp.Symbol('t'),
        'diff': sp.diff, 'integrate': sp.integrate, 'limit': sp.limit,
        'sin': sp.sin, 'cos': sp.cos, 'tan': sp.tan, 'exp': sp.exp, 'log': sp.log, 'sqrt': sp.sqrt
    }
    
    try:
        if mode == 'latex':
            expr_str = expression.replace('$', '').replace('\\left', '').replace('\\right', '').strip()
            expr_str = re.sub(r'([^\s\\])\s*d([a-zA-Z])', r'\1 \\, d\2', expr_str)
            
            while True:
                match = re.search(r'\\frac\{d\}\{d([a-zA-Z])\}\s*\((.*?)\)', expr_str)
                if not match: break
                var = match.group(1)
                content = match.group(2)
                expr_str = expr_str.replace(match.group(0), f"diff({content}, {var})")
            
            if any(func in expr_str for func in ['diff(', 'integrate(', 'limit(']):
                expr = sp.sympify(expr_str, locals=local_dict)
            else:
                expr = sp_parse_latex(expr_str)
        else:
            expr = sp.sympify(expression, locals=local_dict)
            
        result = expr.doit() if hasattr(expr, 'doit') else expr
        
        if result.is_number:
            return str(result.evalf(8)) 
        else:
            # 优化：使用 sp.pretty 生成漂亮的字符公式，并附带 LaTeX 源码
            pretty_result = sp.pretty(result)
            latex_result = sp.latex(result)
            return f"【符号解】\n{pretty_result}\n\n【LaTeX 源码(可复制)】\n{latex_result}"
            
    except Exception as e:
        return f"符号解析错误: {str(e)}"

# ================= 3. 帮助文档界面 =================
class HelpWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("使用说明 / User Guide")
        self.geometry("700x550")
        self.transient(parent)
        self.grab_set()

        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        frame_cn = tk.Frame(notebook)
        notebook.add(frame_cn, text="中文说明")
        text_cn = self.create_text_widget(frame_cn)
        text_cn.insert(tk.END, "【科学计算工具 使用说明】\n\n1. 支持有效数字运算与 SymPy 符号微积分。\n2. 输入时，下方会提供实时公式预览。\n3. 双击历史记录可一键回填。")

        frame_en = tk.Frame(notebook)
        notebook.add(frame_en, text="English Guide")
        text_en = self.create_text_widget(frame_en)
        text_en.insert(tk.END, "[Scientific Calculator User Guide]\n\n1. Supports Significant Figures & Symbolic Calculus.\n2. Real-time formula preview is available below the input box.\n3. Double-click history to reload.")

    def create_text_widget(self, parent):
        frame = tk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True)
        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        # 调大帮助文档字体
        text = tk.Text(frame, font=("微软雅黑", 11), wrap=tk.WORD, padx=10, pady=10, yscrollcommand=scrollbar.set)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=text.yview)
        return text


# ================= 4. 主程序 GUI =================
class SigFigCalculatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("科学计算器 (有效数字 & 微积分 & 实时预览)")
        self.root.geometry("1200x900") # 增大默认窗口尺寸
        self.root.configure(padx=20, pady=20) # 增大内边距
        self.history_data = deque(maxlen=15)
        self.preview_job = None
        self.setup_ui()

    def setup_ui(self):
        left_frame = tk.Frame(self.root, width=700)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 15))

        # 调大标题字体
        tk.Label(left_frame, text="科学计算工具", font=("微软雅黑", 20, "bold")).pack(anchor=tk.W, pady=(0, 15))

        frame_opts = tk.Frame(left_frame)
        frame_opts.pack(fill=tk.X, pady=5)
        
        # 调大单选按钮字体
        tk.Label(frame_opts, text="计算引擎:", font=("微软雅黑", 12)).grid(row=0, column=0, sticky="w")
        self.engine_var = tk.StringVar(value="symbolic")
        self.engine_var.trace_add("write", lambda *args: self.schedule_preview())
        tk.Radiobutton(frame_opts, text="有效数字 (数值)", variable=self.engine_var, value="numeric", font=("微软雅黑", 12)).grid(row=0, column=1, padx=10)
        tk.Radiobutton(frame_opts, text="符号计算 (微积分)", variable=self.engine_var, value="symbolic", font=("微软雅黑", 12)).grid(row=0, column=2, padx=10)

        tk.Label(frame_opts, text="输入格式:", font=("微软雅黑", 12)).grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.mode_var = tk.StringVar(value="latex")
        self.mode_var.trace_add("write", lambda *args: self.schedule_preview())
        tk.Radiobutton(frame_opts, text="LaTeX", variable=self.mode_var, value="latex", font=("微软雅黑", 12)).grid(row=1, column=1, padx=10, sticky="w", pady=(10, 0))
        tk.Radiobutton(frame_opts, text="Python 表达式", variable=self.mode_var, value="python", font=("微软雅黑", 12)).grid(row=1, column=2, padx=10, sticky="w", pady=(10, 0))

        # 调大快捷栏字体
        frame_shortcuts = tk.LabelFrame(left_frame, text="快捷符号与运算", font=("微软雅黑", 11))
        frame_shortcuts.pack(fill=tk.X, pady=(15, 10))

        shortcuts = [
            ("积分 ∫", r"\int_{0}^{1} f(x) dx", "integrate(f(x), (x, 0, 1))", 11),
            ("不定积分", r"\int f(x) dx", "integrate(f(x), x)", 9),
            ("微分 d/dx", r"\frac{d}{dx}(f(x))", "diff(f(x), x)", 8),
            ("极限 lim", r"\lim_{x \to 0} f(x)", "limit(f(x), x, 0)", 7),
            ("分数 a/b", r"\frac{a}{b}", "(a/b)", 3),
        ]

        for i, (text, latex_tpl, py_tpl, offset) in enumerate(shortcuts):
            btn = tk.Button(frame_shortcuts, text=text, font=("微软雅黑", 11), 
                            command=lambda t=text, l=latex_tpl, p=py_tpl, o=offset: self.insert_template(l, p, o))
            btn.grid(row=0, column=i, padx=5, pady=5, sticky="ew")
            frame_shortcuts.grid_columnconfigure(i, weight=1)

        # 调大输入框字体
        tk.Label(left_frame, text="输入表达式:", font=("微软雅黑", 12)).pack(anchor=tk.W, pady=(10, 0))
        self.input_text = tk.Text(left_frame, height=3, font=("Consolas", 16), wrap=tk.WORD)
        self.input_text.pack(fill=tk.X, pady=5)
        self.input_text.insert(tk.END, r"\int_{0}^{1} x^2 dx")
        self.input_text.bind("<KeyRelease>", lambda event: self.schedule_preview())

        # === 实时 LaTeX 预览区 ===
        frame_preview = tk.LabelFrame(left_frame, text="实时公式预览", font=("微软雅黑", 11))
        frame_preview.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # 增加画布高度
        self.fig, self.ax = plt.subplots(figsize=(6, 2), dpi=100)
        self.fig.patch.set_facecolor('#f0f0f0')
        self.ax.axis('off')
        self.canvas = FigureCanvasTkAgg(self.fig, master=frame_preview)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        frame_btns = tk.Frame(left_frame)
        frame_btns.pack(fill=tk.X, pady=15)
        tk.Button(frame_btns, text="清空输入", font=("微软雅黑", 11), command=self.clear_input).pack(side=tk.LEFT)
        tk.Button(frame_btns, text="帮助 / Help", font=("微软雅黑", 11), fg="gray", command=self.show_help).pack(side=tk.LEFT, padx=20)
        # 调大计算按钮
        tk.Button(frame_btns, text="计算", font=("微软雅黑", 14, "bold"), bg="#4CAF50", fg="white", padx=20, pady=5, command=self.calculate).pack(side=tk.RIGHT)

        tk.Label(left_frame, text="计算结果:", font=("微软雅黑", 12)).pack(anchor=tk.W, pady=(5, 0))
        # 调大输出框字体
        self.output_text = tk.Text(left_frame, height=3, font=("Consolas", 16, "bold"), fg="blue")
        self.output_text.pack(fill=tk.X, pady=5)
        self.output_text.config(state=tk.DISABLED)

        # --- 右侧历史记录区 ---
        right_frame = tk.Frame(self.root, width=350)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y)
        tk.Label(right_frame, text="历史记录 (最近15条)", font=("微软雅黑", 14, "bold")).pack(anchor=tk.W)
        # 调大历史记录框字体
        self.history_listbox = tk.Listbox(right_frame, font=("微软雅黑", 11), bg="#f4f4f4")
        self.history_listbox.pack(fill=tk.BOTH, expand=True, pady=10)
        self.history_listbox.bind("<Double-Button-1>", self.load_history)
        tk.Button(right_frame, text="清空历史记录", font=("微软雅黑", 11), fg="red", command=self.clear_history).pack(fill=tk.X)

        self.schedule_preview()

    def schedule_preview(self):
        if self.preview_job:
            self.root.after_cancel(self.preview_job)
        self.preview_job = self.root.after(300, self.update_preview)

    def update_preview(self):
        expr = self.input_text.get("1.0", tk.END).strip()
        mode = self.mode_var.get()
        
        self.ax.clear()
        self.ax.axis('off')

        if not expr:
            self.canvas.draw()
            return

        tex_str = expr
        if mode == 'python':
            try:
                local_dict = {
                    'x': sp.Symbol('x'), 'y': sp.Symbol('y'), 'z': sp.Symbol('z'), 'n': sp.Symbol('n'), 't': sp.Symbol('t'),
                    'diff': sp.diff, 'integrate': sp.integrate, 'limit': sp.limit,
                    'sin': sp.sin, 'cos': sp.cos, 'tan': sp.tan, 'exp': sp.exp, 'log': sp.log, 'sqrt': sp.sqrt
                }
                # 尝试对 Python 公式求值并转化为 LaTeX
                expr_obj = sp.sympify(expr, locals=local_dict)
                if hasattr(expr_obj, 'doit'):
                    expr_obj = expr_obj.doit()
                tex_str = sp.latex(expr_obj)
            except Exception:
                tex_str = expr

        # ==========================================
        # 🌟 终极核武级清洗：用正则表达式将不支持的命令彻底替换
        # ==========================================
        import re # 确保内部调用了 re
        
        # 1. 去除首位空白和 $
        tex_str = tex_str.strip().replace('$', '')
        
        # 2. 移除左右自适应括号
        tex_str = tex_str.replace(r'\left', '').replace(r'\right', '')
        
        # 3. 使用正则精准替换 \limits，即使是转义字符也能干掉
        tex_str = re.sub(r'\\limits', '', tex_str)
        
        # 4. 移除所有的细小排版空格 (\, \; \!) 以及多余的大括号
        tex_str = tex_str.replace(r'\,', ' ').replace(r'\;', ' ').replace(r'\!', ' ')
        tex_str = tex_str.replace('{(', '(').replace(')}', ')')
        
        # 5. 再次清理首尾空白
        tex_str = tex_str.strip()

        try:
            # 渲染前打印一下，看看清理后的结果到底是什么（可在终端看到）
            print(f"正在渲染的 LaTeX: {tex_str}")
            
            # 移除了 wrap=True，防止渲染失效
            self.ax.text(0.5, 0.5, f"${tex_str}$", fontsize=28, ha='center', va='center')
            self.canvas.draw()
        except Exception as e:
            # 如果依然解析失败，捕获异常并显示友好提示，绝对不让程序崩溃
            print(f"Matplotlib 渲染失败: {e}")
            self.ax.clear()
            self.ax.axis('off')
            self.ax.text(0.5, 0.5, "公式过于复杂，暂不支持预览\n(请直接点击计算获取结果)", fontsize=16, color='red', ha='center', va='center')
            self.canvas.draw()

    def insert_template(self, latex_tpl, py_tpl, offset):
        mode = self.mode_var.get()
        template = latex_tpl if mode == 'latex' else py_tpl
        cursor_pos = self.input_text.index(tk.INSERT)
        self.input_text.insert(tk.INSERT, template)
        if offset > 0:
            base_idx = self.input_text.index(f"{cursor_pos} + {len(template)} chars")
            target_idx = self.input_text.index(f"{base_idx} - {offset} chars")
            self.input_text.mark_set(tk.INSERT, target_idx)
        self.input_text.focus_set()
        self.schedule_preview()

    def show_help(self):
        HelpWindow(self.root)

    def set_output(self, text):
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete("1.0", tk.END)
        self.output_text.insert(tk.END, text)
        self.output_text.config(state=tk.DISABLED)

    def clear_input(self):
        self.input_text.delete("1.0", tk.END)
        self.set_output("")
        self.schedule_preview()

    def clear_history(self):
        self.history_data.clear()
        self.history_listbox.delete(0, tk.END)

    def load_history(self, event):
        selection = self.history_listbox.curselection()
        if selection:
            idx = selection[0]
            data = self.history_data[idx]
            self.engine_var.set(data['engine'])
            self.mode_var.set(data['mode'])
            self.input_text.delete("1.0", tk.END)
            self.input_text.insert(tk.END, data['input'])
            self.set_output(data['result'])
            self.schedule_preview()

    def calculate(self):
        expr = self.input_text.get("1.0", tk.END).strip()
        if not expr: return
        
        engine = self.engine_var.get()
        mode = self.mode_var.get()
        
        if engine == 'numeric':
            res = eval_numeric(expr, mode)
        else:
            res = eval_symbolic(expr, mode)
            
        self.set_output(res)
        self.save_to_history(expr, res, engine, mode)

    def save_to_history(self, expr, res, engine, mode):
        time_str = datetime.datetime.now().strftime("%H:%M:%S")
        engine_tag = "数值" if engine == 'numeric' else "符号"
        display_text = f"[{time_str}] [{engine_tag}] {expr[:20]}... -> {res[:15]}"
        
        if len(self.history_data) == 15:
            self.history_listbox.delete(0)
            
        self.history_data.append({
            'time': time_str, 'engine': engine, 'mode': mode,
            'input': expr, 'result': res
        })
        self.history_listbox.insert(tk.END, display_text)
        self.history_listbox.see(tk.END)

if __name__ == "__main__":
    root = tk.Tk()
    app = SigFigCalculatorApp(root)
    root.mainloop()