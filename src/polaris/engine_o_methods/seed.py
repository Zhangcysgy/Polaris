"""引擎O — Sahara 种子方法数据

将 Sahara BET-逾渗湿度门控模型拆解为方法库首批种子数据：

    原子方法 (3):
    - atom_bet_isotherm:      BET多层吸附等温线计算
    - atom_percolation_2d:    二维逾渗电导率标度律
    - atom_rc_relaxation:     RC电荷弛豫

    编排条目 (1):
    - orch_bet_percolation_humidity_gating:  BET-逾渗湿度门控模型

    参数实例 (1):
    - param_sahara_dust_default:  Sahara沙尘默认参数 (c=10, h_c=2.0)
"""

from __future__ import annotations

from .library import MethodLibrary


def seed_sahara_methods(lib: MethodLibrary) -> list[str]:
    """将 Sahara BET-逾渗模型的子模块录入方法库。

    返回录入的方法 ID 列表。
    """
    ids = []

    # ================================================================
    # 原子方法 1: BET 多层吸附等温线
    # ================================================================
    aid1 = lib.add_method(
        name="BET多层吸附等温线计算",
        type="atom",
        description=(
            "使用 Brunauer-Emmett-Teller (BET) 方程从环境相对湿度 (RH) 计算固体表面"
            "吸附水膜的厚度 h(RH)。\n\n"
            "核心公式: V/V_m = c·RH / [(1-RH)(1-RH+c·RH)]\n"
            "膜厚: h(RH) = (V/V_m) · h_m\n\n"
            "参数:\n"
            "- c: BET常数 = exp[(E1-EL)/RT]，矿物依赖 (5~50)\n"
            "- h_m: 单分子层厚度 ≈ 0.28 nm\n\n"
            "适用范围: 0 < RH < 1，多层吸附区 (RH > 0.3) 最准确。\n"
            "参考文献: Brunauer et al. (1938) JACS 60, 309-319."
        ),
        domain="表面科学",
        variables=["相对湿度", "BET常数c", "单层厚度h_m", "水膜厚度h"],
    )
    ids.append(aid1)

    # ================================================================
    # 原子方法 2: 二维逾渗电导率标度律
    # ================================================================
    aid2 = lib.add_method(
        name="二维逾渗电导率标度律",
        type="atom",
        description=(
            "使用二维逾渗理论计算表面电导率 σ_s 随水膜厚度的变化。\n\n"
            "核心公式:\n"
            "  σ_s(h) = 0,                          h < h_c\n"
            "  σ_s(h) = σ_0 · ((h-h_c)/h_m)^t,     h ≥ h_c\n\n"
            "参数:\n"
            "- h_c: 逾渗阈值膜厚 (导电临界点) ≈ 2.0 个分子层\n"
            "- σ_0: 充分发育多层水膜的表面电导率 ≈ 10⁻⁷ S/m\n"
            "- t: 二维逾渗电导普适临界指数 = 1.3\n\n"
            "物理基础: 第一分子层被表面羟基强束缚→绝缘; "
            "第二分子层起支持可移动水合离子→导电。\n"
            "逾渗阈值以上的幂律增长是二维输运的普适行为。\n"
            "参考文献: Stauffer & Aharony (1994) Introduction to Percolation Theory."
        ),
        domain="凝聚态物理",
        variables=["水膜厚度h", "逾渗阈值h_c", "表面电导率σ_s", "普适指数t"],
    )
    ids.append(aid2)

    # ================================================================
    # 原子方法 3: RC 电荷弛豫
    # ================================================================
    aid3 = lib.add_method(
        name="RC电路电荷弛豫",
        type="atom",
        description=(
            "将带电颗粒建模为球形电容器，计算摩擦电荷通过表面水膜的泄漏效率。\n\n"
            "核心公式:\n"
            "  dQ/dt = -Q / τ(RH)\n"
            "  τ(RH) = ε₀·ε_r / σ_s(h(RH))\n"
            "  η(RH) = exp(-τ_coll / τ(RH))\n\n"
            "参数:\n"
            "- ε₀: 真空介电常数 = 8.854×10⁻¹² F/m\n"
            "- ε_r: 相对介电常数 ≈ 4.5 (石英)\n"
            "- τ_coll: 沙粒碰撞特征接触时间 ≈ 10⁻³ s\n\n"
            "η(RH) = 碰撞后保留的摩擦电荷比例。\n"
            "干燥极限 (h<h_c, σ_s=0): τ→∞, η=1（全保留）。\n"
            "湿润极限 (h≫h_c): τ短于τ_coll, η→0（全泄漏）。"
        ),
        domain="电学/气溶胶物理",
        variables=["电荷保留效率η", "弛豫时间τ", "表面电导率σ_s", "碰撞时间τ_coll"],
    )
    ids.append(aid3)

    # ================================================================
    # 编排条目: BET-逾渗湿度门控模型
    # ================================================================
    orch_id = lib.add_method(
        name="BET-逾渗湿度门控模型",
        type="orchestration",
        description=(
            "将 BET 吸附、二维逾渗和 RC 弛豫耦合为统一的湿度门控摩擦起电模型。\n\n"
            "串联逻辑:\n"
            "  输入: 环境相对湿度 RH\n"
            "  → [原子] BET吸附等温线 → 水膜厚度 h(RH)\n"
            "  → [原子] 二维逾渗标度律 → 表面电导率 σ_s(h)\n"
            "  → [原子] RC电荷弛豫 → 电荷保留效率 η(RH)\n"
            "  输出: η(RH) 曲线 + 临界湿度 RH_c\n\n"
            "RH_c 解析解: α(c-1)·RH_c² - [α(c-2)-c]·RH_c - α = 0\n"
            "  (其中 α = h_c/h_m = 2.0)\n\n"
            "验证: 三重一致——实验室 (Waitukaitis 2014)、风洞 (Kok & Renno 2012)、"
            "卫星因果推断 (Zhang 2025)。火星预测被 Chide et al. (2025) Nature 证实。"
        ),
        domain="大气科学",
        variables=["相对湿度RH", "电荷保留效率η", "临界湿度RH_c", "BET常数c", "逾渗阈值h_c"],
    )
    ids.append(orch_id)

    # ================================================================
    # 参数实例: Sahara 沙尘默认参数
    # ================================================================
    param_id = lib.add_method(
        name="Sahara沙尘默认参数集",
        type="parameter_instance",
        description=(
            "Sahara 混合矿物沙尘的 BET-逾渗湿度门控模型参数实例。\n\n"
            "参数值:\n"
            "- c = 10 (混合 Sahara 沙尘，介于石英 5 和方解石 50 之间)\n"
            "- h_m = 0.28 nm (单分子层厚度)\n"
            "- h_c = 2.0 × h_m = 0.56 nm (逾渗导电阈值)\n"
            "- t = 1.3 (二维逾渗电导普适临界指数)\n"
            "- σ₀ ≈ 10⁻⁷ S/m (大气CO₂溶解产生的H⁺/HCO₃⁻离子电导)\n"
            "- ε_r = 4.5 (石英相对介电常数)\n"
            "- τ_coll = 1 ms (沙粒碰撞特征接触时间)\n\n"
            "输出: RH_c ≈ 54%，η(RH) 在 40-65% RH 间从 ~1 骤降至 ~0。\n"
            "适用条件: 290K, 混合撒哈拉矿物沙尘, 粒径1-10μm。\n"
            "已知局限: 矿物非均质性(c在5-50间变化)使RH_c偏移±6%。"
        ),
        domain="大气科学",
        variables=["c=10", "h_c=0.56nm", "RH_c≈54%"],
        parent_id=orch_id,
    )
    ids.append(param_id)

    return ids


def seed_all(lib: MethodLibrary, approve: bool = True) -> dict:
    """录入全部种子数据，可选自动审批。

    Returns:
        {"atom": [id, ...], "orch": [id, ...], "param": [id, ...]}
    """
    ids = seed_sahara_methods(lib)

    if approve:
        # 自动审批种子数据为 verified（这是人类作者自己创建的方法）
        from .gate import Gate
        gate = Gate(lib.db)
        for mid in ids:
            lib.update_method(mid, status="pending_confirm")
            gate.approve(mid, confirmed_by="system（种子数据自动审批）")

    # 分类
    result = {"atom": [], "orch": [], "param": []}
    for mid in ids:
        entry = lib.get_method(mid)
        if entry:
            result[{"atom": "atom", "orchestration": "orch", "parameter_instance": "param"}
                   .get(entry.type, "atom")].append(mid)

    return result
