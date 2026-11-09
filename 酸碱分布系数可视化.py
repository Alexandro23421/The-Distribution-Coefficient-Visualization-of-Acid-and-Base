import streamlit as st
import numpy as np
import plotly.graph_objects as go
from scipy.optimize import brentq

st.set_page_config(page_title="酸碱分布系数与滴定曲线可视化", layout="wide")

st.title("🧪 酸碱分布系数与滴定曲线可视化工具")

tab_dist, tab_tit = st.tabs(["📈 分布系数", "🧪 滴定曲线与指示剂推荐"])

# ===================== 数据库 =====================
ACID_BASE_DB = {
    # ===== 一元弱酸 =====
    "乙酸 (CH3COOH)": {
        "type": "acid",
        "pKas": [4.76],
        "formulas": ["CH_3COOH", "CH_3COO^-"],
    },
    "甲酸 (HCOOH)": {
        "type": "acid",
        "pKas": [3.75],
        "formulas": ["HCOOH", "HCOO^-"],
    },
    "氢氟酸 (HF)": {
        "type": "acid",
        "pKas": [3.17],
        "formulas": ["HF", "F^-"],
    },
    "次氯酸 (HClO)": {
        "type": "acid",
        "pKas": [7.53],
        "formulas": ["HClO", "ClO^-"],
    },
    "氢氰酸 (HCN)": {
        "type": "acid",
        "pKas": [9.21],
        "formulas": ["HCN", "CN^-"],
    },
    "苯甲酸 (C6H5COOH)": {
        "type": "acid",
        "pKas": [4.20],
        "formulas": ["C_6H_5COOH", "C_6H_5COO^-"],
    },
    "苯酚 (C6H5OH)": {
        "type": "acid",
        "pKas": [9.95],
        "formulas": ["C_6H_5OH", "C_6H_5O^-"],
    },
    "甘氨酸 (H2NCH2COOH, 羧基pKa)": {
        "type": "acid",
        "pKas": [2.34],
        "formulas": ["^+H_3NCH_2COOH", "H_2NCH_2COOH"],
    },

    # ===== 二元弱酸 =====
    "碳酸 (H2CO3)": {
        "type": "acid",
        "pKas": [6.35, 10.33],
        "formulas": ["H_2CO_3", "HCO_3^-", "CO_3^{2-}"],
    },
    "草酸 (H2C2O4)": {
        "type": "acid",
        "pKas": [1.25, 4.14],
        "formulas": ["H_2C_2O_4", "HC_2O_4^-", "C_2O_4^{2-}"],
    },
    "亚硫酸 (H2SO3)": {
        "type": "acid",
        "pKas": [1.89, 7.21],
        "formulas": ["H_2SO_3", "HSO_3^-", "SO_3^{2-}"],
    },
    "硫化氢 (H2S)": {
        "type": "acid",
        "pKas": [7.00, 12.92],
        "formulas": ["H_2S", "HS^-", "S^{2-}"],
    },
    "酒石酸 (H2C4H4O6)": {
        "type": "acid",
        "pKas": [3.04, 4.37],
        "formulas": ["H_2A", "HA^-", "A^{2-}"],
    },
    "丙二酸 (H2C3H2O4)": {
        "type": "acid",
        "pKas": [2.83, 5.69],
        "formulas": ["H_2A", "HA^-", "A^{2-}"],
    },

    # ===== 三元弱酸 =====
    "磷酸 (H3PO4)": {
        "type": "acid",
        "pKas": [2.15, 7.20, 12.35],
        "formulas": ["H_3PO_4", "H_2PO_4^-", "HPO_4^{2-}", "PO_4^{3-}"],
    },
    "柠檬酸 (H3C6H5O7)": {
        "type": "acid",
        "pKas": [3.13, 4.76, 6.40],
        "formulas": ["H_3A", "H_2A^-", "HA^{2-}", "A^{3-}"],
    },

    # ===== 氨基酸（两性，用共轭酸pKa） =====
    "甘氨酸 (两性, pKa1=2.34, pKa2=9.60)": {
        "type": "acid",
        "pKas": [2.34, 9.60],
        "formulas": ["^+H_3NCH_2COOH", "H_2NCH_2COO^- (两性离子)", "H_2NCH_2COO^-"],
    },

    # ===== 弱碱（自动转共轭酸pKa） =====
    "氨水 (NH3)": {
        "type": "base",
        "pKb": 4.75,
        "formulas": ["NH_4^+", "NH_3"],
    },
    "甲胺 (CH3NH2)": {
        "type": "base",
        "pKb": 3.36,
        "formulas": ["CH_3NH_3^+", "CH_3NH_2"],
    },
    "吡啶 (C5H5N)": {
        "type": "base",
        "pKb": 8.77,
        "formulas": ["C_5H_5NH^+", "C_5H_5N"],
    },
    "羟胺 (NH2OH)": {
        "type": "base",
        "pKb": 8.04,
        "formulas": ["NH_3OH^+", "NH_2OH"],
    },
}



INDICATORS = {
    "甲基橙": (3.1, 4.4),
    "甲基红": (4.4, 6.2),
    "溴甲酚绿": (3.8, 5.4),
    "溴百里酚蓝": (6.0, 7.6),
    "百里酚蓝(第二变色)": (8.0, 9.6),
    "酚酞": (8.2, 10.0),
    "百里酚酞": (9.3, 10.5),
}

# ===================== 工具函数 =====================
def latex_to_html(formula: str) -> str:
    s = formula.replace(r"\mathrm{", "").replace("}", "")
    s = s.replace(r"^", "").replace(r"_", "_")
    parts = []
    i = 0
    while i < len(s):
        if s[i] == "_":
            i += 1
            if i < len(s) and s[i] == "{":
                j = s.index("}", i)
                parts.append(f"<sub>{s[i+1:j]}</sub>")
                i = j + 1
            else:
                j = i
                while j < len(s) and (s[j].isdigit() or s[j] in "+-"):
                    j += 1
                parts.append(f"<sub>{s[i:j]}</sub>")
                i = j
        elif s[i] == "^":
            i += 1
            if i < len(s) and s[i] == "{":
                j = s.index("}", i)
                parts.append(f"<sup>{s[i+1:j]}</sup>")
                i = j + 1
            else:
                j = i
                while j < len(s) and (s[j].isdigit() or s[j] in "+-"):
                    j += 1
                parts.append(f"<sup>{s[i:j]}</sup>")
                i = j
        else:
            parts.append(s[i])
            i += 1
    return "".join(parts)


def calculate_distribution(pH, pKas):
    H = 10 ** (-pH)
    Kas = [10 ** (-pKa) for pKa in pKas]
    n = len(Kas)
    denom = H ** n
    for i in range(1, n + 1):
        term = 1.0
        for j in range(i):
            term *= Kas[j]
        denom += term * (H ** (n - i))
    deltas = []
    for i in range(n + 1):
        num = 1.0
        for j in range(i):
            num *= Kas[j]
        num *= H ** (n - i)
        deltas.append(num / denom)
    return deltas

def calculate_concentrations(pH, pKas, Ca, Va, Vb):
    """返回 (形态浓度列表, 总浓度 Ct, 稀释后体积 Vt)"""
    Vt = Va + Vb
    if Vt <= 0:
        return [], 0.0, 0.0
    Ct = Ca * Va / Vt
    deltas = calculate_distribution(pH, pKas)
    concentrations = [d * Ct for d in deltas]
    return concentrations, Ct, Vt

# ===================== 滴定核心算法 =====================
def _proton_balance(pH, pKas, Ca0, Va, Cb, Vb):
    H = 10 ** (-pH)
    OH = 1e-14 / H if H > 0 else 1e14
    Vt = Va + Vb
    if Vt <= 0:
        return 0.0
    Kas = [10 ** (-pKa) for pKa in pKas]
    n = len(Kas)
    denom = H ** n
    for i in range(1, n + 1):
        term = 1.0
        for j in range(i):
            term *= Kas[j]
        denom += term * (H ** (n - i))
    charge = 0.0
    for i in range(n + 1):
        num = 1.0
        for j in range(i):
            num *= Kas[j]
        num *= H ** (n - i)
        charge += (i - n) * num
    Ct = Ca0 * Va / Vt
    Cb_dil = Cb * Vb / Vt
    return Ct * charge / denom + H - OH - Cb_dil


def titration_curve(pKas, Ca, Va, Cb, n_points=400):
    total_acid_mol = Ca * Va
    Veq = total_acid_mol / Cb if Cb > 0 else 0.0
    V_max = max(Veq * 2.0, Va * 0.5 + 1.0)
    Vb_array = np.linspace(0.0, V_max, n_points)
    pH_array = []
    for Vb in Vb_array:
        try:
            root = brentq(
                _proton_balance,
                0.0,
                14.0,
                args=(pKas, Ca, Va, Cb, Vb),
                xtol=1e-12,
                maxiter=200,
            )
            pH_array.append(root)
        except ValueError:
            pH_array.append(np.nan)
    return Vb_array, np.array(pH_array), Veq


def titration_jump(pKas, Ca, Va, Cb, Veq):
    total_acid_mol = Ca * Va
    if Veq <= 0 or total_acid_mol <= 0:
        return None, None, None
    V_minus = Veq * 0.999
    V_plus = Veq * 1.001
    try:
        pH_minus = brentq(
            _proton_balance, 0.0, 14.0, args=(pKas, Ca, Va, Cb, V_minus), xtol=1e-12
        )
        pH_plus = brentq(
            _proton_balance, 0.0, 14.0, args=(pKas, Ca, Va, Cb, V_plus), xtol=1e-12
        )
    except ValueError:
        return None, None, None
    low, high = sorted([pH_minus, pH_plus])
    return low, high, Veq


def recommend_indicators(low, high):
    if low is None or high is None:
        return []
    rec = []
    for name, (a, b) in INDICATORS.items():
        if not (b < low or a > high):
            rec.append((name, a, b))
    return rec

def pH_to_Vb(pH_target, pKas, Ca, Va, Cb, Vb_array, pH_array):
    if len(pH_array) == 0:
        return None
    if pH_target < pH_array[0] or pH_target > pH_array[-1]:
        return None
    idx = np.searchsorted(pH_array, pH_target)
    if idx == 0:
        return Vb_array[0]
    if idx >= len(Vb_array):
        return Vb_array[-1]
    pH1, pH2 = pH_array[idx - 1], pH_array[idx]
    V1, V2 = Vb_array[idx - 1], Vb_array[idx]
    if abs(pH2 - pH1) < 1e-12:
        return V1
    return V1 + (V2 - V1) * (pH_target - pH1) / (pH2 - pH1)
# ===================== 侧边栏 =====================
with st.sidebar:
    st.header("参数设置")
    selected = st.selectbox("选择物质", list(ACID_BASE_DB.keys()))
    entry = ACID_BASE_DB[selected]
    is_base = entry["type"] == "base"
    pKas = entry["pKas"] if not is_base else [14.0 - entry["pKb"]]
    formulas = entry["formulas"]

    st.write("**各级 pKa 值:**")
    for i, pKa in enumerate(pKas):
        st.write(rf"- \(pK_{{a{i+1}}}: {pKa:.2f}\)")
    if is_base:
        st.info(f"弱碱，pKb = {entry['pKb']:.2f}，已转换为共轭酸 pKa = {pKas[0]:.2f}")

    st.divider()
    pH_slider = st.slider("拖动选择 pH", 0.0, 14.0, 7.0, 0.1)
    pH_input = st.number_input("精确输入 pH", 0.0, 14.0, float(pH_slider), 0.01)
    current_pH = pH_input

    st.divider()
    st.subheader("滴定参数设置")
    Ca = st.number_input("酸初始浓度 Ca (mol/L)", 1e-6, 10.0, 0.1, 0.01)
    Va = st.number_input("酸初始体积 Va (mL)", 0.1, 1000.0, 20.0, 0.1)
    Cb = st.number_input("NaOH 浓度 Cb (mol/L)", 1e-6, 10.0, 0.1, 0.01)

# ===================== Tab 1：分布系数 =====================
with tab_dist:
    pH_array = np.linspace(0, 14, 500)
    delta_array = np.array([calculate_distribution(p, pKas) for p in pH_array]).T
    current_deltas = calculate_distribution(current_pH, pKas)

    fig = go.Figure()
    for i, formula in enumerate(formulas):
        fig.add_trace(
            go.Scatter(
                x=pH_array,
                y=delta_array[i],
                mode="lines",
                name=latex_to_html(formula),
                line=dict(width=3),
            )
        )
    fig.add_vline(x=current_pH, line_width=2, line_dash="dash", line_color="red")
    fig.update_layout(
        title=f"{selected} 的形态分布图",
        xaxis_title="pH",
        yaxis_title="分布系数 (δ)",
        yaxis_range=[-0.05, 1.05],
        hovermode="x unified",
        plot_bgcolor="white",
        xaxis=dict(showgrid=True, gridcolor="lightgray"),
        yaxis=dict(showgrid=True, gridcolor="lightgray"),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader(f"当前 pH = {current_pH:.2f} 下的各组分分布系数：")
    cols = st.columns(len(formulas))
    for i, formula in enumerate(formulas):
        with cols[i]:
            st.latex(rf"\delta = {current_deltas[i]:.4f}")
            st.progress(float(current_deltas[i]))

# ===================== Tab 2：滴定曲线与指示剂 =====================
with tab_tit:
    Ka1 = 10 ** (-pKas[0])
    titratable = Ca * Ka1 >= 1e-8

    if not titratable:
        st.warning(
            f"⚠️ 该酸无法准确滴定：Ca·Ka = {Ca * Ka1:.2e} < 1e-8。"
            "滴定突跃不明显，指示剂选择意义有限。"
        )

    Vb_array, pH_array, Veq = titration_curve(pKas, Ca, Va, Cb)
    low, high, Veq2 = titration_jump(pKas, Ca, Va, Cb, Veq)
    recs = recommend_indicators(low, high)

    fig_tit = go.Figure()
    fig_tit.add_trace(
        go.Scatter(
            x=Vb_array,
            y=pH_array,
            mode="lines",
            name="滴定曲线",
            line=dict(width=3, color="#1f77b4"),
        )
    )
    if Veq > 0:
        pH_eq = float(
            brentq(
                _proton_balance,
                0.0,
                14.0,
                args=(pKas, Ca, Va, Cb, Veq),
                xtol=1e-12,
            )
        )
        fig_tit.add_trace(
            go.Scatter(
                x=[Veq],
                y=[pH_eq],
                mode="markers+text",
                name="化学计量点",
                marker=dict(size=10, color="red"),
                text=[f"Veq={Veq:.2f} mL, pH={pH_eq:.2f}"],
                textposition="top right",
            )
        )
    if low is not None and high is not None:
        fig_tit.add_hrect(
            y0=low,
            y1=high,
            fillcolor="orange",
            opacity=0.15,
            line_width=0,
            annotation_text="滴定突跃范围",
            annotation_position="top left",
        )

    fig_tit.update_layout(
        title=f"{selected} 滴定曲线（NaOH 滴定）",
        xaxis_title="加入 NaOH 体积 Vb / mL",
        yaxis_title="pH",
        yaxis_range=[0, 14],
        hovermode="x unified",
        plot_bgcolor="white",
        xaxis=dict(showgrid=True, gridcolor="lightgray"),
        yaxis=dict(showgrid=True, gridcolor="lightgray"),
    )
    st.plotly_chart(fig_tit, use_container_width=True)

    st.subheader("滴定分析结果")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("化学计量点 Veq", f"{Veq:.3f} mL")
        if low is not None and high is not None:
            st.metric("滴定突跃范围", f"pH {low:.2f} ~ {high:.2f}")
        else:
            st.warning("未能计算滴定突跃范围。")
        st.metric("Ca·Ka", f"{Ca * Ka1:.2e}")

    with col2:
        if recs:
            st.success("✅ 推荐指示剂：")
            for name, a, b in recs:
                st.write(f"- **{name}**：pH {a} ~ {b}")
        else:
            st.warning("未找到合适的指示剂。")

# ===================== Tab 3：叠加视图 =====================
tab_dist, tab_tit, tab_conc = st.tabs(
    ["📈 分布系数", "🧪 滴定曲线与指示剂推荐", "📊 滴定曲线 + 各形态浓度叠加"]
)

with tab_conc:
    if not titratable:
        st.warning(
            f"⚠️ Ca·Ka = {Ca * Ka1:.2e} < 1e-8，滴定突跃不明显。"
            "叠加图仍可显示，但指示剂推荐意义有限。"
        )

    fig_conc = go.Figure()

    # 左轴：滴定曲线 pH
    fig_conc.add_trace(
        go.Scatter(
            x=Vb_array,
            y=pH_array,
            mode="lines",
            name="滴定曲线 (pH)",
            line=dict(width=3, color="#1f77b4"),
            yaxis="y1",
        )
    )

    # 右轴：各形态浓度 [mol/L]
    for i, formula in enumerate(formulas):
        conc_on_Vb = []
        for j, pH_val in enumerate(pH_array):
            if np.isnan(pH_val):
                conc_on_Vb.append(np.nan)
            else:
                Vb_now = Vb_array[j]
                concs, _, _ = calculate_concentrations(
                    pH_val, pKas, Ca, Va, Vb_now
                )
                conc_on_Vb.append(concs[i])

        fig_conc.add_trace(
            go.Scatter(
                x=Vb_array,
                y=conc_on_Vb,
                mode="lines",
                name=latex_to_html(formula),
                line=dict(width=2),
                yaxis="y2",
            )
        )

    # 计量点
    if Veq > 0:
        try:
            pH_eq = float(
                brentq(
                    _proton_balance,
                    0.0,
                    14.0,
                    args=(pKas, Ca, Va, Cb, Veq),
                    xtol=1e-12,
                )
            )
            fig_conc.add_trace(
                go.Scatter(
                    x=[Veq],
                    y=[pH_eq],
                    mode="markers",
                    name="化学计量点",
                    marker=dict(size=10, color="red"),
                    yaxis="y1",
                )
            )
        except ValueError:
            pass

    # 突跃范围
    if low is not None and high is not None:
        V_low = pH_to_Vb(low, pKas, Ca, Va, Cb, Vb_array, pH_array)
        V_high = pH_to_Vb(high, pKas, Ca, Va, Cb, Vb_array, pH_array)
        if V_low is not None and V_high is not None:
            fig_conc.add_vrect(
                x0=V_low,
                x1=V_high,
                fillcolor="orange",
                opacity=0.15,
                line_width=0,
                annotation_text="滴定突跃",
                annotation_position="top left",
            )

    fig_conc.update_layout(
        title=f"{selected} 滴定曲线 + 各形态浓度叠加",
        xaxis_title="加入 NaOH 体积 Vb / mL",
        yaxis=dict(
            title="pH",
            side="left",
            range=[0, 14],
            showgrid=True,
            gridcolor="lightgray",
        ),
        yaxis2=dict(
            title="浓度 / mol·L⁻¹",
            side="right",
            overlaying="y",
            showgrid=False,
        ),
        hovermode="x unified",
        plot_bgcolor="white",
        legend=dict(x=1.02, y=1),
    )

    st.plotly_chart(fig_conc, use_container_width=True)

    st.info(
        "左轴是 pH，右轴是各形态浓度。"
        "随着 NaOH 加入，曲线会同时体现稀释效应和酸碱形态转化。"
    )
