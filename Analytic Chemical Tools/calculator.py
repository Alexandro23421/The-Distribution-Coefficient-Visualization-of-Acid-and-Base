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


# ================= 2. 符号微积分引擎 (核心修复区) =================
def eval_symbolic(expression, mode):
    # 统一构建 Python 可用的符号字典
    local_dict = {
        'x': sp.Symbol('x'), 'y': sp.Symbol('y'), 'z': sp.Symbol('z'), 'n': sp.Symbol('n'), 't': sp.Symbol('t'),
        'diff': sp.diff, 'integrate': sp.integrate, 'limit': sp.limit,
        'sin': sp.sin, 'cos': sp.cos, 'tan': sp.tan, 'exp': sp.exp, 'log': sp.log, 'sqrt': sp.sqrt
    }
    
    try:
        if mode == 'latex':
            # 1. 清洗字符
            expr_str = expression.replace('$', '').replace('\\left', '').replace('\\right', '').strip()
            
            # 2. 修复积分：自动把 dx 替换为 \, dx (解决 TokenError)
            expr_str = re.sub(r'([^\s\\])\s*d([a-zA-Z])', r'\1 \\, d\2', expr_str)
            
            # 3. 修复微分：将 \frac{d}{dx}(...) 转换为 diff(..., x)
            while True:
                match = re.search(r'\\frac\{d\}\{d([a-zA-Z])\}\s*\((.*?)\)', expr_str)
                if not match: break
                var = match.group(1)
                content = match.group(2)
                expr_str = expr_str.replace(match.group(0), f"diff({content}, {var})")
            
            # 4. 如果转换后带有 diff() 等函数，用 sympify 解析更稳定；否则用 parse_latex
            if any(func in expr_str for func in ['diff(', 'integrate(', 'limit(']):
                expr = sp.sympify(expr_str, locals=local_dict)
            else:
                expr = sp_parse_latex(expr_str)
        else:
            # Python 模式直接 sympify
            expr = sp.sympify(expression, locals=local_dict)
            
        result = expr.doit() if hasattr(expr, 'doit') else expr
        
        if result.is_number:
            return str(result.evalf(8)) 
        else:
            return sp.latex(result)
            
    except Exception as e:
        return f"符号解析错误: {str(e)}\n\n【提示】如果涉及微积分，请检查格式。LaTeX 积分推荐写为: \\int_{0}^{1} x^2 dx（程序已自动容错）。"


# ================= 3. 帮助文档界面 =================
class HelpWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("使用说明 / User Guide")
        self.geometry("650x500")
        self.transient(parent)
        self.grab_set()

        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        frame_cn = tk.Frame(notebook)
        notebook.add(frame_cn, text="中文说明")
        text_cn = self.create_text_widget(frame_cn)
        text_cn.insert(tk.END, self.get_chinese_guide())

        frame_en = tk.Frame(notebook)
        notebook.add(frame_en, text="English Guide")
        text_en = self.create_text_widget(frame_en)
        text_en.insert(tk.END, self.get_english_guide())

    def create_text_widget(self, parent):
        frame = tk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True)
        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text = tk.Text(frame, font=("微软雅黑", 10), wrap=tk.WORD, padx=10, pady=10, yscrollcommand=scrollbar.set)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=text.yview)
        return text

    def get_chinese_guide(self):
        return """【科学计算工具 使用说明】

本工具包含两种计算引擎：有效数字计算（数值）与符号计算（微积分）。

一、 有效数字计算（数值引擎）
1. 规则概述：
   - 修约规则：严格遵循“四舍六入五成双”。
   - 加减法：以小数点后位数最少的数据为准。
   - 乘除法：以有效数字位数最少的数据为准。
   - 精确常数：如 100、3 等整数，视为绝对精确，不限制最终结果的有效数字。
2. 示例：
   - LaTeX 格式：\\frac{50.00 \\times (27.80 - 24.39) \\times 0.1167}{1.3245}
   - Python 格式：50.00 * (27.80 - 24.39) * 0.1167 / 1.3245

二、 符号计算（微积分引擎）
1. 规则概述：
   - 调用 SymPy 符号计算库，支持微积分、极限、方程化简等。
   - 输出结果：如果是纯数字则计算数值；如果是公式，则输出 LaTeX 格式。
2. 示例：
   - LaTeX 格式：
     - 定积分：\\int_{0}^{1} x^2 dx
     - 极限：\\lim_{x \\to 0} \\frac{\\sin x}{x}
   - Python 格式：
     - 导数：diff(x**3, x)
     - 积分：integrate(x**2, x)

三、 其他功能
- 快捷按钮：点击输入框上方的运算符号按钮，可直接插入模板。
- 历史记录：右侧面板记录最近15条计算。双击历史记录可一键回填。
- 格式切换：使用上方单选框自由切换 LaTeX 和 Python 表达式输入。"""

    def get_english_guide(self):
        return """[Scientific Calculator User Guide]

This tool features two calculation engines: Significant Figures (Numeric) and Symbolic Calculus.

1. Significant Figures (Numeric Engine)
- Rounding Rule: "Round half to even" (Banker's rounding).
- Addition/Subtraction: Result limited by the least number of decimal places.
- Multiplication/Division: Result limited by the least number of significant figures.
- Exact Constants: Integers like 100 and 3 are considered exact and will not limit precision.
- Example:
  - LaTeX: \\frac{50.00 \\times (27.80 - 24.39) \\times 0.1167}{1.3245}
  - Python: 50.00 * (27.80 - 24.39) * 0.1167 / 1.3245

2. Symbolic Calculus (Symbolic Engine)
- Powered by SymPy. Supports integration, differentiation, limits, etc.
- Output: Evaluates to numeric if possible, otherwise returns LaTeX.
- Example:
  - LaTeX:
    - Integral: \\int_{0}^{1} x^2 dx
    - Limit: \\lim_{x \\to 0} \\frac{\\sin x}{x}
  - Python:
    - Derivative: diff(x**3, x)
    - Integral: integrate(x**2, x)

3. Other Features
- Shortcut Buttons: Click buttons above the input box to insert templates instantly.
- History: The right panel saves the last 15 calculations. Double-click to reload.
- Format Switch: Use the radio buttons to toggle between LaTeX and Python input."""


# ================= 4. 主程序 GUI =================
class SigFigCalculatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("科学计算器 (有效数字 & 微积分)")
        self.root.geometry("950x680")
        self.root.configure(padx=15, pady=15)
        self.history_data = deque(maxlen=15)
        self.setup_ui()

    def setup_ui(self):
        left_frame = tk.Frame(self.root, width=550)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        tk.Label(left_frame, text="科学计算工具", font=("微软雅黑", 16, "bold")).pack(anchor=tk.W, pady=(0, 10))

        frame_opts = tk.Frame(left_frame)
        frame_opts.pack(fill=tk.X, pady=5)
        
        tk.Label(frame_opts, text="计算引擎:").grid(row=0, column=0, sticky="w")
        self.engine_var = tk.StringVar(value="numeric")
        tk.Radiobutton(frame_opts, text="有效数字 (数值)", variable=self.engine_var, value="numeric").grid(row=0, column=1, padx=5)
        tk.Radiobutton(frame_opts, text="符号计算 (微积分)", variable=self.engine_var, value="symbolic").grid(row=0, column=2, padx=5)

        tk.Label(frame_opts, text="输入格式:").grid(row=1, column=0, sticky="w", pady=(5, 0))
        self.mode_var = tk.StringVar(value="latex")
        tk.Radiobutton(frame_opts, text="LaTeX", variable=self.mode_var, value="latex").grid(row=1, column=1, padx=5, sticky="w")
        tk.Radiobutton(frame_opts, text="Python 表达式", variable=self.mode_var, value="python").grid(row=1, column=2, padx=5, sticky="w")

        frame_shortcuts = tk.LabelFrame(left_frame, text="快捷符号与运算 (自动匹配格式)", font=("微软雅黑", 9))
        frame_shortcuts.pack(fill=tk.X, pady=(10, 5))

        shortcuts = [
            ("积分 ∫", r"\int_{0}^{1} f(x) dx", "integrate(f(x), (x, 0, 1))", 11),
            ("不定积分", r"\int f(x) dx", "integrate(f(x), x)", 9),
            ("微分 d/dx", r"\frac{d}{dx}(f(x))", "diff(f(x), x)", 8),
            ("极限 lim", r"\lim_{x \to 0} f(x)", "limit(f(x), x, 0)", 7),
            ("分数 a/b", r"\frac{a}{b}", "(a/b)", 3),
            ("乘号 ×", r"\times ", "* ", 0),
            ("除号 ÷", r"\div ", "/ ", 0),
            ("平方 ²", r"^{2}", "**2", 0),
            ("根号 √", r"\sqrt{x}", "sqrt(x)", 2),
        ]

        for i, (text, latex_tpl, py_tpl, offset) in enumerate(shortcuts):
            btn = tk.Button(frame_shortcuts, text=text, font=("微软雅黑", 9), 
                            command=lambda t=text, l=latex_tpl, p=py_tpl, o=offset: self.insert_template(l, p, o))
            btn.grid(row=i // 5, column=i % 5, padx=3, pady=3, sticky="ew")

        for i in range(5):
            frame_shortcuts.grid_columnconfigure(i, weight=1)

        tk.Label(left_frame, text="输入表达式:").pack(anchor=tk.W, pady=(5, 0))
        self.input_text = tk.Text(left_frame, height=5, font=("Consolas", 12), wrap=tk.WORD)
        self.input_text.pack(fill=tk.X, pady=5)
        self.input_text.insert(tk.END, r"\int_{0}^{1} x^2 dx")

        frame_btns = tk.Frame(left_frame)
        frame_btns.pack(fill=tk.X, pady=10)
        tk.Button(frame_btns, text="清空输入", command=self.clear_input).pack(side=tk.LEFT)
        tk.Button(frame_btns, text="帮助 / Help", fg="gray", command=self.show_help).pack(side=tk.LEFT, padx=15)
        tk.Button(frame_btns, text="计算", font=("微软雅黑", 11, "bold"), bg="#4CAF50", fg="white", command=self.calculate).pack(side=tk.RIGHT)

        tk.Label(left_frame, text="计算结果:").pack(anchor=tk.W, pady=(10, 0))
        self.output_text = tk.Text(left_frame, height=4, font=("Consolas", 12, "bold"), fg="blue")
        self.output_text.pack(fill=tk.X, pady=5)
        self.output_text.config(state=tk.DISABLED)

        right_frame = tk.Frame(self.root, width=300)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y)

        tk.Label(right_frame, text="历史记录 (最近15条)", font=("微软雅黑", 12, "bold")).pack(anchor=tk.W)
        
        self.history_listbox = tk.Listbox(right_frame, font=("微软雅黑", 10), bg="#f0f0f0")
        self.history_listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        self.history_listbox.bind("<Double-Button-1>", self.load_history)

        tk.Button(right_frame, text="清空历史记录", fg="red", command=self.clear_history).pack(fill=tk.X)

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