import streamlit as st
import numpy as np
import plotly.graph_objects as go
import re

# 设置页面宽屏显示
st.set_page_config(page_title="多物质酸碱分布对比工具", layout="wide")

st.title("🧪 多物质酸碱分布系数对比可视化工具")
st.markdown("""
- **UI 升级**：图例已优化为 HTML 格式，支持完美的上下标显示（如 H₂CO₃）。
- **功能升级**：支持同时选择多种物质进行对比分析。
""")

# ==========================================
# 1. 数据库：存储常见酸碱数据
# ==========================================
ACID_BASE_DB = {
    # --- 无机酸 ---
    "碳酸 (H2CO3)": {"type": "acid", "pK_values": [6.35, 10.33], "formulas": ["H_2CO_3", "HCO_3^-", "CO_3^{2-}"]},
    "磷酸 (H3PO4)": {"type": "acid", "pK_values": [2.15, 7.20, 12.35], "formulas": ["H_3PO_4", "H_2PO_4^-", "HPO_4^{2-}", "PO_4^{3-}"]},
    "硫酸 (H2SO4)": {"type": "acid", "pK_values": [-3.0, 1.99], "formulas": ["H_2SO_4", "HSO_4^-", "SO_4^{2-}"]},
    "氢硫酸 (H2S)": {"type": "acid", "pK_values": [7.0, 12.9], "formulas": ["H_2S", "HS^-", "S^{2-}"]},
    
    # --- 有机酸 ---
    "乙酸 (CH3COOH)": {"type": "acid", "pK_values": [4.76], "formulas": ["CH_3COOH", "CH_3COO^-"]},
    "草酸 (H2C2O4)": {"type": "acid", "pK_values": [1.25, 4.14], "formulas": ["H_2C_2O_4", "HC_2O_4^-", "C_2O_4^{2-}"]},
    "柠檬酸 (H3Cit)": {"type": "acid", "pK_values": [3.13, 4.76, 6.40], "formulas": ["H_3Cit", "H_2Cit^-", "HCit^{2-}", "Cit^{3-}"]},
    "EDTA (H4Y)": {"type": "acid", "pK_values": [2.0, 2.67, 6.16, 10.26], "formulas": ["H_4Y", "H_3Y^-", "H_2Y^{2-}", "HY^{3-}", "Y^{4-}"]},
    
    # --- 氨基酸 ---
    "甘氨酸 (Gly)": {"type": "acid", "pK_values": [2.34, 9.60], "formulas": ["^+H_3N-CH_2-COOH", "^+H_3N-CH_2-COO^-", "H_2N-CH_2-COO^-"]},
    "谷氨酸 (Glu)": {"type": "acid", "pK_values": [2.19, 4.25, 9.67], "formulas": ["Glu^{+1}", "Glu^{0}", "Glu^{-1}", "Glu^{-2}"]},
    
    # --- 弱碱 ---
    "氨水 (NH3)": {"type": "base", "pK_values": [4.75], "formulas": ["NH_4^+", "NH_3"]},
    "甲胺 (CH3NH2)": {"type": "base", "pK_values": [3.36], "formulas": ["CH_3NH_3^+", "CH_3NH_2"]},
}

# ==========================================
# 2. 辅助函数：LaTeX 转 HTML
# ==========================================
def latex_to_html(latex_str):
    """
    将简单的 LaTeX 化学式转换为 HTML 字符串，以便 Plotly 图例渲染。
    处理 _{...} 为 <sub>...</sub>
    处理 ^{...} 或 ^char 为 <sup>...</sup>
    """
    if not isinstance(latex_str, str):
        return str(latex_str)
        
    html = latex_str
    
    # 处理下标 _{...}
    # 正则解释: _\{ 匹配 _{ , (.*?) 非贪婪匹配内容, \} 匹配 }
    html = re.sub(r'_\{(.*?)\}', r'<sub>\1</sub>', html)
    
    # 处理上标 ^{...}
    html = re.sub(r'\^\{(.*?)\}', r'<sup>\1</sup>', html)
    
    # 处理简单上标 ^char (例如 ^+)
    html = re.sub(r'\^([a-zA-Z0-9+\-])', r'<sup>\1</sup>', html)
    
    # 清理可能残留的反斜杠 (如果有的话)
    html = html.replace('\\', '')
    
    return html

# ==========================================
# 3. 核心数学计算
# ==========================================
def calculate_distribution(pH, pKas):
    H = 10 ** (-pH)
    Kas = [10 ** (-pKa) for pKa in pKas]
    n = len(Kas)
    
    denom = H ** n
    for i in range(1, n + 1):
        term = 1
        for j in range(i):
            term *= Kas[j]
        denom += term * (H ** (n - i))
    
    deltas = []
    for i in range(n + 1):
        num = 1
        for j in range(i):
            num *= Kas[j]
        num *= H ** (n - i)
        deltas.append(num / denom)
        
    return deltas

# ==========================================
# 4. 侧边栏：多选与设置
# ==========================================
with st.sidebar:
    st.header("参数设置")
    
    # 多选物质
    selected_names = st.multiselect(
        "选择要对比的物质 (可多选)", 
        list(ACID_BASE_DB.keys()),
        default=["碳酸 (H2CO3)", "乙酸 (CH3COOH)"]
    )
    
    st.divider()
    
    # 全局 pH 控制
    pH_slider = st.slider("拖动选择 pH", 0.0, 14.0, 7.0, 0.1)
    pH_input = st.number_input("精确输入 pH", 0.0, 14.0, float(pH_slider), 0.01)
    
    current_pH = pH_input

# ==========================================
# 5. 数据处理与绘图
# ==========================================
if not selected_names:
    st.warning("请在左侧至少选择一种物质。")
else:
    # 生成 pH 数组
    pH_array = np.linspace(0, 14, 500)
    
    fig = go.Figure()
    
    # 定义颜色池，用于区分不同的物质
    substance_colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
    
    # 遍历选中的每种物质
    for idx, name in enumerate(selected_names):
        data = ACID_BASE_DB[name]
        raw_pKs = data["pK_values"]
        formulas = data["formulas"]
        sub_type = data["type"]
        
        # 处理 pKa/pKb
        if sub_type == 'base':
            effective_pKas = [14.0 - pk for pk in raw_pKs]
        else:
            effective_pKas = raw_pKs
            
        # 计算该物质的分布曲线
        delta_matrix = [calculate_distribution(p, effective_pKas) for p in pH_array]
        delta_matrix = np.array(delta_matrix).T 
        
        # 为该物质选择一个主色调
        base_color = substance_colors[idx % len(substance_colors)]
        
        # 为该物质的不同形态生成略有差异的颜色（可选，这里保持同色系或循环使用）
        # 为了清晰，我们让同一物质的不同形态使用相同颜色，但通过线型或透明度区分？
        # 不，通常不同形态用不同颜色更好区分，但不同物质之间也要区分。
        # 策略：每个物质分配一个主色，其内部形态使用该主色的不同深浅，或者直接使用循环色。
        # 这里简化：直接使用循环色，但在图例名称前加上物质名前缀，方便识别。
        
        for i, formula in enumerate(formulas):
            # 将 LaTeX 转为 HTML
            html_formula = latex_to_html(formula)
            
            # 构造图例名称： "物质名: 形态"
            # Plotly 支持 HTML 在 name 中吗？是的，只要 hoverlabel 等支持。
            # 实际上 Plotly 的 legend text 支持部分 HTML 标签如 <b>, <i>, <sub>, <sup>
            legend_name = f"<b>{name.split('(')[0]}</b>: {html_formula}"
            
            fig.add_trace(go.Scatter(
                x=pH_array, 
                y=delta_matrix[i], 
                mode='lines', 
                name=legend_name,
                line=dict(color=base_color, width=2, dash=['solid', 'dash', 'dot'][i % 3]), # 用线型区分同一物质的不同形态
                hovertemplate=f"<b>{name}</b><br>{html_formula}<br>pH: %{{x:.2f}}<br>δ: %{{y:.4f}}<extra></extra>"
            ))

    # 添加垂直参考线
    fig.add_vline(x=current_pH, line_width=2, line_dash="dash", line_color="red", annotation_text=f"pH={current_pH}")

    # 布局设置
    fig.update_layout(
        title="多物质形态分布对比",
        xaxis_title="pH",
        yaxis_title="分布系数 (δ)",
        yaxis_range=[-0.05, 1.05],
        hovermode="x unified",
        plot_bgcolor="white",
        xaxis=dict(showgrid=True, gridcolor='lightgray'),
        yaxis=dict(showgrid=True, gridcolor='lightgray'),
        legend=dict(
            orientation="h", # 水平图例，节省空间
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )

    st.plotly_chart(fig, use_container_width=True)

    # ==========================================
    # 6. 底部数据展示
    # ==========================================
    st.subheader(f"当前 pH = {current_pH:.2f} 下的各组分分布系数：")
    
    # 使用表格展示更清晰
    table_data = []
    for name in selected_names:
        data = ACID_BASE_DB[name]
        raw_pKs = data["pK_values"]
        formulas = data["formulas"]
        sub_type = data["type"]
        
        if sub_type == 'base':
            effective_pKas = [14.0 - pk for pk in raw_pKs]
        else:
            effective_pKas = raw_pKs
            
        current_deltas = calculate_distribution(current_pH, effective_pKas)
        
        for i, formula in enumerate(formulas):
            # 转换公式用于显示
            display_formula = formula.replace('_', '').replace('^', '').replace('{', '').replace('}', '')
            # 简单的清理，实际可以用 latex_to_html 但 st.table 不支持 html
            # 这里为了表格整洁，我们只做简单替换
            clean_formula = re.sub(r'[_^{}]', '', formula) 
            
            table_data.append({
                "物质": name.split('(')[0],
                "形态": clean_formula,
                "分布系数 (δ)": f"{current_deltas[i]:.4f}",
                "占比 (%)": f"{current_deltas[i]*100:.2f}%"
            })
            
    import pandas as pd
    df = pd.DataFrame(table_data)
    st.dataframe(df, hide_index=True, use_container_width=True)
