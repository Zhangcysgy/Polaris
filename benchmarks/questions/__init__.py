"""
Polaris M0 摸底基准 —— 50 题气象编码测试

五大类 × 10 题，覆盖 LLM 在气象数据分析中的系统性错误类型。

用法:
    python benchmarks/scorer.py --list               # 列出全部50题
    python benchmarks/scorer.py --run Q001           # 运行单题
    python benchmarks/scorer.py --run-all            # 运行全部
    python benchmarks/scorer.py --category io        # 按类别运行

每道题的验证标准包含:
    - assertions:   代码中必须包含的 assert/check 语句
    - forbidden:    代码中禁止出现的错误模式
    - expected_output: 期望的输出特征
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Category(str, Enum):
    IO = "io"                      # 数据读取
    COORD = "coord"                # 坐标处理
    STAT = "stat"                  # 统计方法
    PHYSICS = "physics"            # 物理诊断
    VIZ = "viz"                    # 可视化


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


@dataclass
class Verification:
    """验证标准"""
    assertions: list[str] = field(default_factory=list)
    """代码中必须包含的 assert/try-except 语句。"""

    forbidden: list[str] = field(default_factory=list)
    """代码中禁止出现的错误模式。"""

    expected_keys: list[str] = field(default_factory=list)
    """输出结果中必须包含的键/字段。"""

    expected_range: Optional[str] = None
    """输出结果的数值范围（如 "0 < x < 500"）。"""

    notes: str = ""
    """额外的验证说明。"""


@dataclass
class Question:
    """一道测试题"""
    id: str                              # Q001-Q050
    category: Category
    difficulty: Difficulty
    title: str
    description: str                     # 给 LLM 的 Prompt
    verification: Verification
    context: str = ""                    # 额外上下文（如使用的数据集）
    known_llm_errors: list[str] = field(default_factory=list)
    """已知 LLM 在此类问题上常犯的错误。"""


# ═══════════════════════════════════════════════════════════════
# 50 道测试题
# ═══════════════════════════════════════════════════════════════

QUESTIONS: list[Question] = [
    # ============================================================
    # 第一类：数据读取（IO）— 10 题
    # ============================================================
    Question(
        id="Q001",
        category=Category.IO,
        difficulty=Difficulty.EASY,
        title="读取 NetCDF 并检查 NaN",
        description=(
            "读取 ERA5 月平均温度文件 'era5_t2m_monthly.nc'，"
            "检查变量 't2m' 是否包含 NaN 或 inf。"
            "如果包含，打印出 NaN 的格点数占比。"
        ),
        verification=Verification(
            assertions=[
                "检查 data 是否包含 NaN",
                "检查 data 是否包含 inf",
            ],
            expected_keys=["nan_count", "nan_ratio"],
            forbidden=[
                "没有 NaN 检查就直接计算",
                "使用 pandas.isna 检查 xarray 数据（应使用 np.isnan 或 xr.DataArray.isnull）",
            ],
            notes="这是气象数据读取的最基本操作，首次通过率应 >90%。",
        ),
        known_llm_errors=[
            "忘记检查 NaN，直接对数据做运算导致静默错误",
            "混淆 NaN 检查的 API（pandas vs xarray vs numpy）",
        ],
    ),

    Question(
        id="Q002",
        category=Category.IO,
        difficulty=Difficulty.EASY,
        title="读取多个 NetCDF 文件并沿时间维度拼接",
        description=(
            "ERA5 数据按月存储为 12 个文件：'era5_t2m_2023_01.nc' 至 'era5_t2m_2023_12.nc'。"
            "读取全部文件，沿时间维度拼接为一个 DataArray。"
            "检查拼接后的时间维度是否严格单调递增、无重复、无缺失。"
        ),
        verification=Verification(
            assertions=[
                "检查拼接后时间维度长度为 12",
                "检查时间是否单调递增（无乱序）",
                "检查是否存在重复时间步（如重复应报错）",
            ],
            expected_keys=["merged_data", "time_length"],
            forbidden=[
                "手动 list 12 个文件名（应使用 glob 或 pathlib 自动匹配）",
            ],
            notes="多文件拼接是气象数据分析中最常见的操作。",
        ),
        known_llm_errors=[
            "使用 xarray.open_mfdataset 时未指定 concat_dim，导致默认行为不符合预期",
            "时间维度的 dtype 不一致导致拼接失败",
        ],
    ),

    Question(
        id="Q003",
        category=Category.IO,
        difficulty=Difficulty.EASY,
        title="读取 GRIB 格式数据并转换",
        description=(
            "读取 GRIB 格式的气象数据文件 'forecast.grib2'（包含 500hPa 位势高度）。"
            "将其转换为 xarray DataArray，提取 'Geopotential Height' 变量。"
            "提示：使用 cfgrib 引擎。如果 cfgrib 不可用，报出明确的错误信息。"
        ),
        verification=Verification(
            assertions=[
                "使用 try-except 包裹 cfgrib 导入",
                "cfgrib 不可用时给出人类可读的错误信息（非 traceback）",
            ],
            expected_keys=["gh500"],
            notes="GRIB 是气象业务常用格式，但 cfgrib 安装常有依赖问题。",
        ),
        known_llm_errors=[
            "直接 import cfgrib 不做异常处理，导致环境不兼容时崩溃",
            "混淆 cfgrib 的 filter_by_keys 参数名",
        ],
    ),

    Question(
        id="Q004",
        category=Category.IO,
        difficulty=Difficulty.MEDIUM,
        title="下载 ERA5 数据（CDS API）并检查完整性",
        description=(
            "使用 CDS API (cdsapi) 下载 2023年6月北非区域（20°W-40°E, 10°N-40°N）的"
            "逐小时 2m 温度数据。下载完成后检查：\n"
            "1. 时间步数是否正确（6月有30天×24小时=720步）\n"
            "2. 经纬度范围是否与请求一致\n"
            "3. 是否有全为 NaN 的格点（可能是陆地掩码问题）"
        ),
        verification=Verification(
            assertions=[
                "检查 len(time) == 720",
                "检查经度范围 min_lon >= -20, max_lon <= 40",
                "检查纬度范围 min_lat >= 10, max_lat <= 40",
                "检查是否存在全 NaN 格点",
            ],
            expected_keys=["downloaded_data", "integrity_report"],
            notes="CDS API 下载是 ERA5 数据获取的标准路径。",
        ),
        known_llm_errors=[
            "CDS 请求格式中 区域指定方式错误（area: [N, W, S, E] 顺序易反）",
            "下载完成后不做完整性检查，后续分析在残缺数据上运行",
        ],
    ),

    Question(
        id="Q005",
        category=Category.IO,
        difficulty=Difficulty.MEDIUM,
        title="读取不规则网格数据并插值到规则网格",
        description=(
            "读取一个站点观测数据 CSV 文件 'station_obs.csv'（列：station_id, lat, lon, time, t2m）。"
            "站点分布不规则。使用最近邻方法将站点数据插值到 1°×1° 规则网格。"
            "检查：插值后是否有超过 30% 的格点为 NaN（说明站点覆盖不足）。"
        ),
        verification=Verification(
            assertions=[
                "检查插值后 NaN 占比，超过 30% 发出 Warning",
                "使用 scipy.interpolate.griddata 或类似方法",
            ],
            expected_keys=["gridded_data", "nan_coverage_ratio"],
            notes="站点到网格的插值是观测-模式对比的基础操作。",
        ),
        known_llm_errors=[
            "选择的插值方法不适合稀疏站点（线性插值在稀疏区产生极端外推）",
            "未检查插值质量就进行后续分析",
        ],
    ),

    Question(
        id="Q006",
        category=Category.IO,
        difficulty=Difficulty.EASY,
        title="检查时间序列的连续性",
        description=(
            "读取一个日平均温度 NetCDF 文件 'daily_t2m_2023.nc'。"
            "检查时间维度是否存在缺失日期（gap）。"
            "如有缺失，打印缺失日期的列表。"
        ),
        verification=Verification(
            assertions=[
                "计算出预期时间步数并对比实际步数",
                "识别具体缺失日期（非仅报告'有缺失'）",
            ],
            expected_keys=["missing_dates", "total_expected", "total_actual"],
            notes="时间连续性是气候分析的前提——缺失日期的线性插值可能掩盖极端事件。",
        ),
        known_llm_errors=[
            "使用 range 生成日期时忽略闰年",
            "pandas.date_range 和 xarray 的时间索引不兼容",
        ],
    ),

    Question(
        id="Q007",
        category=Category.IO,
        difficulty=Difficulty.EASY,
        title="处理 Scale/Offset 编码的 NetCDF",
        description=(
            "ERA5 的 NetCDF 文件使用 scale_factor 和 add_offset 进行压缩编码。"
            "读取变量 'tp'（总降水），确保解码后的数值正确。"
            "打印解码前后的数值范围和编码参数。"
        ),
        verification=Verification(
            assertions=[
                "确认打开了 decode_cf=True（或显式手动解码）",
                "打印 scale_factor 和 add_offset 的实际值",
                "检查解码后数值范围是否物理合理（降水 ≥0，日值 < 1000 mm）",
            ],
            expected_keys=["raw_min", "raw_max", "decoded_min", "decoded_max"],
            notes="xarray 默认自动解码，但手动读取时容易忘记。",
        ),
        known_llm_errors=[
            "手动 open_dataset 时未设 decode_cf=True，直接使用原始整数值",
            "降水单位混淆（m vs mm vs kg/m²）",
        ],
    ),

    Question(
        id="Q008",
        category=Category.IO,
        difficulty=Difficulty.MEDIUM,
        title="批量下载 + 断点续传",
        description=(
            "需要下载 1980-2023 年共 44 年的 ERA5 月平均数据。由于 CDS 限制，需要分多年请求。"
            "编写代码：\n"
            "1. 检查哪些年份已下载（断点续传）\n"
            "2. 仅下载缺失年份\n"
            "3. 所有年份下载完成后拼接\n"
            "4. 最终检查时间维度是否覆盖全部 44 年（528 个月）"
        ),
        verification=Verification(
            assertions=[
                "存在断点续传逻辑（检查已下载文件）",
                "最终时间维度长度 == 528",
                "下载过程中有异常处理和重试逻辑",
            ],
            expected_keys=["final_dataset"],
            forbidden=[
                "无断点续传——每次从头下载全部数据",
                "无异常处理——单个年份下载失败导致整个流程崩溃",
            ],
        ),
        known_llm_errors=[
            "未处理 CDS 请求排队/限速导致的超时",
            "下载失败后无重试——44年全跑完发现缺了3年",
        ],
    ),

    Question(
        id="Q009",
        category=Category.IO,
        difficulty=Difficulty.HARD,
        title="多源数据融合——不同网格对齐",
        description=(
            "有两个数据集：\n"
            "A) ERA5 0.25°×0.25° 全球网格（1440×721）\n"
            "B) 卫星观测 1°×1° 网格（360×180）\n"
            "将 A 保守重网格化（conservative remapping）到 B 的网格，"
            "确保全球平均在重网格化前后的差异 < 0.1%。"
            "使用 xesmf 或 CDO remapcon。"
        ),
        verification=Verification(
            assertions=[
                "全球平均在重网格化前后差异 < 0.1%",
                "重网格化使用面积权重（cos 纬度）",
                "输出网格与目标网格 B 完全一致",
            ],
            expected_keys=["remapped_data", "global_mean_diff_pct"],
            notes="不同分辨率数据对比时，保守重网格化是必须步骤。",
        ),
        known_llm_errors=[
            "使用简单双线性插值而非保守重网格化，导致通量计算不守恒",
            "未做面积权重校正",
        ],
    ),

    Question(
        id="Q010",
        category=Category.IO,
        difficulty=Difficulty.MEDIUM,
        title="读取 WRF 输出并提取诊断变量",
        description=(
            "WRF 输出文件 'wrfout_d01_2023-06-01_00:00:00' 包含扰动变量和基态变量。"
            "需要使用 wrf-python 库计算诊断变量：\n"
            "1. 从扰动位温 T + 基态 T0 → 绝对温度 (t_k)\n"
            "2. 从扰动气压 P + 基态 PB → 总气压 (p_full)\n"
            "3. 计算相对湿度 (rh)\n"
            "检查：rh 应在 [0, 100] 范围内。"
        ),
        verification=Verification(
            assertions=[
                "使用 wrf-python 或 wrf.getvar",
                "绝对温度 = T + T0（非 T_base + 300）",
                "rh 在 [0, 100] 范围内（超出应报 Warning）",
            ],
            expected_keys=["tk", "p_hpa", "rh"],
            notes="WRF 的扰动变量+基态变量拆分是初学者最常踩的坑。",
        ),
        known_llm_errors=[
            "忘记加基态温度 300K，直接用扰动位温",
            "混淆 wrf-python 的 getvar 参数名",
        ],
    ),

    # ============================================================
    # 第二类：坐标处理（COORD）— 10 题
    # ============================================================
    Question(
        id="Q011",
        category=Category.COORD,
        difficulty=Difficulty.EASY,
        title="经度从 0-360 转换为 -180-180",
        description=(
            "ERA5 使用 0-360° 经度系统。将 DataArray 的经度坐标从 [0, 360) "
            "转换为 [-180, 180)，并确保数据正确重排。"
            "验证：转换后 (lon=0, lat=0) 处的值与转换前一致。"
        ),
        verification=Verification(
            assertions=[
                "转换后经度范围是 [-180, 180)",
                "使用 xr.where 或 roll 方法（不是简单加减）",
                "验证特定格点值在转换前后一致",
            ],
            expected_keys=["converted_data"],
            forbidden=[
                "简单地 lon - 180（会导致180°附近数据错位）",
            ],
        ),
        known_llm_errors=[
            "直接 lon-180 不重排数据——这是最高频错误之一",
            "使用 np.where 处理 xarray DataArray 导致坐标丢失",
        ],
    ),

    Question(
        id="Q012",
        category=Category.COORD,
        difficulty=Difficulty.EASY,
        title="计算区域平均——必须加 cos(纬度) 权重",
        description=(
            "计算北半球中纬度（30°N-60°N）的区域平均温度。"
            "必须使用 cos(纬度) 作为面积权重——这是这道题的核心考点。"
            "对比：不加权重和加权重的结果差异。"
        ),
        verification=Verification(
            assertions=[
                "代码中必须出现 cos(lat) 或 np.cos(np.deg2rad(lat))",
                "输出加权和未加权的两个结果以便对比",
            ],
            expected_keys=["weighted_mean", "unweighted_mean", "difference"],
            forbidden=[
                "直接 .mean() 不加权重——这是气象分析最高频系统错误",
            ],
            notes="LLM 在此题上的首次通过率预计 < 30%——这是最高频遗漏。",
        ),
        known_llm_errors=[
            "直接 .mean(dim=['lat','lon']) 不加 cos 权重——最高频错误",
            "加了 cos 但忘记把纬度从度转为弧度",
            "对已加权的数据又加了一次权重",
        ],
    ),

    Question(
        id="Q013",
        category=Category.COORD,
        difficulty=Difficulty.MEDIUM,
        title="处理不同垂直坐标（气压层 vs 模式层）",
        description=(
            "有两个数据集：\n"
            "A) ERA5 气压层数据（37层，hPa）\n"
            "B) 模式层数据（137层，混合坐标）\n"
            "将模式层数据插值到标准气压层（1000, 850, 700, 500, 300, 200, 100, 50, 10 hPa）。"
            "使用对数气压插值（log-pressure interpolation）。"
        ),
        verification=Verification(
            assertions=[
                "使用对数气压插值（在 log(p) 空间插值）",
                "插值后检查气压层顺序（从地表到高空递减）",
                "检查外推警告（模式顶可能高于 10hPa）",
            ],
            expected_keys=["interpolated_data"],
            forbidden=["在气压空间线性插值（高层会严重失真）"],
        ),
        known_llm_errors=[
            "线性插值而非对数插值——高层误差大",
            "气压单位混淆（Pa vs hPa）",
        ],
    ),

    Question(
        id="Q014",
        category=Category.COORD,
        difficulty=Difficulty.EASY,
        title="时间坐标处理——理解 reference date",
        description=(
            "NetCDF 文件中的时间变量存储为 'hours since 1900-01-01'。"
            "将其转换为 Python datetime 对象，并提取年份和月份。"
            "检查：处理后的年份范围是否合理（如 1940-2023）。"
        ),
        verification=Verification(
            assertions=[
                "使用 xr.decode_cf 或 cftime 进行时间解码",
                "打印 reference date 确认理解正确",
                "检查年份范围是否在合理区间",
            ],
            expected_keys=["datetime_index", "year_range"],
            notes="时间坐标的 reference date 是初学者最困惑的点。",
        ),
        known_llm_errors=[
            "假设时间一定是 'hours since 1900-01-01'（不同数据集 reference date 不同）",
            "手动除以24而非使用 cftime.num2date",
        ],
    ),

    Question(
        id="Q015",
        category=Category.COORD,
        difficulty=Difficulty.MEDIUM,
        title="旋转风场——从地理坐标到局地坐标",
        description=(
            "CMIP6 某些模型的输出风场在旋转极坐标中。"
            "将旋转坐标中的 (u, v) 风场旋转回地理坐标。"
            "验证：旋转前后的风速大小（sqrt(u²+v²)）应守恒。"
        ),
        verification=Verification(
            assertions=[
                "旋转前后风速大小差异 < 1e-6",
                "正确使用旋转矩阵 [cos(θ), -sin(θ); sin(θ), cos(θ)]",
            ],
            expected_keys=["u_geo", "v_geo"],
        ),
        known_llm_errors=[
            "旋转角符号弄反",
            "忘记旋转格点经度也需要转换",
        ],
    ),

    Question(
        id="Q016",
        category=Category.COORD,
        difficulty=Difficulty.EASY,
        title="选择特定区域并处理边界",
        description=(
            "从全球数据中提取青藏高原区域（70°E-105°E, 25°N-45°N）。"
            "注意：ERA5 经度是 0-360，需要正确处理经度选择。"
            "在选择区域前，先检查请求的区域是否完全在数据范围内。"
        ),
        verification=Verification(
            assertions=[
                "先检查区域是否在数据范围内",
                "使用 .sel 时指定 method='nearest' 或处理边界外情况",
            ],
            expected_keys=["tibet_data"],
            notes="区域选择的边界处理是常见错误来源。",
        ),
        known_llm_errors=[
            "在 0-360 经度系统中直接用 70-105 选择（可能选到 70-105 的西半球部分）",
            ".sel 遇到不在数据范围内的坐标直接报错而非给出 warning",
        ],
    ),

    Question(
        id="Q017",
        category=Category.COORD,
        difficulty=Difficulty.HARD,
        title="处理不规则网格——卫星轨道数据",
        description=(
            "读取 MODIS Level-2 气溶胶产品（swath 数据，不规则网格）。"
            "每个像元有独立的经纬度（不是规则网格）。"
            "将其按 1°×1° 网格进行空间聚合（binning），"
            "计算每个格点内的有效观测数和中位数 AOD。"
        ),
        verification=Verification(
            assertions=[
                "使用 groupby_bins 或类似方法进行空间聚合",
                "每个格点输出观测数（便于后续质量筛选）",
                "AOD 值在物理合理范围 [0, 5] 内",
            ],
            expected_keys=["aod_median", "obs_count"],
            notes="卫星 swath 数据的处理比规则网格数据复杂一个量级。",
        ),
        known_llm_errors=[
            "将 swath 数据当作规则网格直接 reshape",
            "binning 边界处理不当导致数据丢失",
        ],
    ),

    Question(
        id="Q018",
        category=Category.COORD,
        difficulty=Difficulty.EASY,
        title="从经纬度索引中提取最接近的格点",
        description=(
            "给定一个站点列表（Sahara 5个站点的经纬度），从 ERA5 0.25° 网格中"
            "提取最接近每个站点的格点值。"
            "使用 .sel(method='nearest')。"
            "打印每个站点与其最近格点的距离（km），超过 50km 应报警。"
        ),
        verification=Verification(
            assertions=[
                "使用 .sel(method='nearest')",
                "计算站点-格点距离（Haversine 公式或等效）",
                "距离 > 50km 发出 Warning",
            ],
            expected_keys=["station_values", "station_grid_distances"],
        ),
        known_llm_errors=[
            "使用简单欧氏距离而非球面距离（高纬度误差大）",
            ".sel 未指定 method='nearest'，坐标不完全匹配时报错",
        ],
    ),

    Question(
        id="Q019",
        category=Category.COORD,
        difficulty=Difficulty.MEDIUM,
        title="从月数据计算季节平均",
        description=(
            "给定 1980-2023 年月平均温度数据，计算 JJA（6-8月）季节平均。"
            "正确使用 xarray 的 groupby('time.season')。"
            "注意：DJF 季节跨越年份边界（12月属于气象冬季），确保处理正确。"
        ),
        verification=Verification(
            assertions=[
                "使用 xarray groupby('time.season') 或等效方法",
                "检查 DJF 季节的年份标签是否合理（通常标记为 1-2月的年份）",
                "输出每年一个季节平均值（44个JJA值）",
            ],
            expected_keys=["jja_mean", "djf_mean"],
            notes="季节平均是气候分析的基本功。DJF 跨年边界是额外考点。",
        ),
        known_llm_errors=[
            "手动按月索引（month in [6,7,8]）而非用 groupby——代码冗长易错",
            "DJF 季节的年份标签错误（12月归入下一年还是今年）",
        ],
    ),

    Question(
        id="Q020",
        category=Category.COORD,
        difficulty=Difficulty.HARD,
        title="投影转换——等经纬度到极射投影",
        description=(
            "将 ERA5 全球 0.25° 等经纬度网格数据重新投影到北极极射赤面投影"
            "（North Polar Stereographic），标准纬线 60°N，中心经度 0°。"
            "使用 cartopy 或 pyproj 进行投影转换。"
            "验证：原始网格和投影网格的北极点（90°N）值应一致。"
        ),
        verification=Verification(
            assertions=[
                "使用 cartopy.crs 或 pyproj 进行投影转换",
                "北极点值在转换前后一致",
                "投影后无异常空洞或条纹",
            ],
            expected_keys=["projected_data", "crs_info"],
        ),
        known_llm_errors=[
            "使用默认投影参数而非指定的标准纬线和中心经度",
            "投影后坐标轴标签错误（xy 坐标被标注为经纬度）",
        ],
    ),

    # ============================================================
    # 第三类：统计方法（STAT）— 10 题
    # ============================================================
    Question(
        id="Q021",
        category=Category.STAT,
        difficulty=Difficulty.EASY,
        title="计算趋势 + 显著性检验",
        description=(
            "给定 1980-2023 年 JJA 季节平均温度时间序列（每年一个值）。"
            "计算线性趋势（°C/decade），并进行 Mann-Kendall 显著性检验。"
            "输出：趋势值、p-value、是否显著（α=0.05）。"
        ),
        verification=Verification(
            assertions=[
                "使用 scipy.stats.linregress 或 numpy.polyfit",
                "Mann-Kendall 检验使用 pymannkendall 或手动实现",
                "输出趋势的单位是 °C/decade（不是 °C/year）",
            ],
            expected_keys=["trend_per_decade", "p_value", "is_significant"],
            notes="趋势计算是最常见的统计分析，但单位转换常出错。",
        ),
        known_llm_errors=[
            "趋势单位错误——用 °C/year 而非 °C/decade",
            "线性回归的 p 值被误当作 Mann-Kendall 的 p 值",
        ],
    ),

    Question(
        id="Q022",
        category=Category.STAT,
        difficulty=Difficulty.EASY,
        title="计算相关系数 + 有效自由度校正",
        description=(
            "计算 Niño3.4 指数和东亚夏季降水指数之间的 Pearson 相关系数。"
            "两变量均为 44 年时间序列（1980-2023）。"
            "使用有效自由度（考虑自相关）进行显著性检验，而非 N=44。"
        ),
        verification=Verification(
            assertions=[
                "计算自相关以估计有效自由度 Neff",
                "使用 Neff（而非 N）计算 p-value",
                "Neff < N（自相关会降低有效自由度）",
            ],
            expected_keys=["correlation", "neff", "p_value_eff", "p_value_naive"],
            forbidden=["直接使用 N=44 计算显著性——这是经典错误"],
        ),
        known_llm_errors=[
            "直接用原始样本数 N 计算显著性——气象时间序列的自相关使有效自由度远小于N",
            "用 scipy.stats.pearsonr 的默认 p 值但不理解其假设（独立样本）",
        ],
    ),

    Question(
        id="Q023",
        category=Category.STAT,
        difficulty=Difficulty.MEDIUM,
        title="EOF 分析 + North 检验",
        description=(
            "对北太平洋（120°E-240°E, 20°N-60°N）月平均 SST 异常进行 EOF 分解。"
            "使用 North 检验（Rule of Thumb）确定显著的 EOF 模态数。"
            "输出前3个 EOF 的空间模态（EOFs）和对应的时间序列（PCs），"
            "以及每个模态的解释方差。"
        ),
        verification=Verification(
            assertions=[
                "在 EOF 前去除时间平均（计算 anomaly）",
                "应用 cos(纬度) 面积权重",
                "实现 North 检验（特征值误差范围计算）",
                "EOFs 和 PCs 的符号一致（EOF×PC 重构原始场）",
            ],
            expected_keys=["eofs", "pcs", "variance_ratio", "north_significant_modes"],
            notes="EOF 是气象领域最常用的降维方法。面积权重和 North 检验是区分初学者和熟手的关键。",
        ),
        known_llm_errors=[
            "不做面积权重——高纬度格点被过度代表",
            "不做 North 检验，主观选前2-3个模态",
            "EOF 和 PC 符号不一致导致重构失败",
        ],
    ),

    Question(
        id="Q024",
        category=Category.STAT,
        difficulty=Difficulty.MEDIUM,
        title="合成分析（Composite Analysis）+ 显著性",
        description=(
            "基于 Niño3.4 指数 > +0.5°C 筛选 El Niño 年（共8年），"
            "计算 El Niño 年冬季（DJF）500hPa 位势高度的合成平均异常。"
            "使用 t-test（Welch's t-test）检验合成异常是否显著，"
            "应用 FDR（False Discovery Rate）校正多重比较。"
        ),
        verification=Verification(
            assertions=[
                "使用 t-test 或 bootstrap 进行合成检验",
                "多重比较校正（FDR 或 Bonferroni）",
                "样本量（8个El Niño年）在报告中明确标注",
            ],
            expected_keys=["composite_anomaly", "p_values_fdr", "significant_mask"],
            forbidden=["不做多重比较校正——全球格点上万个，期望有5%假阳性"],
        ),
        known_llm_errors=[
            "不做多重比较校正——这是气象统计最高频遗漏之一",
            "用 Student's t-test 而非 Welch's t-test（假设方差齐性）",
        ],
    ),

    Question(
        id="Q025",
        category=Category.STAT,
        difficulty=Difficulty.HARD,
        title="Bootstrap 置信区间（自定义统计量）",
        description=(
            "给定 30 年的极端降水指数（年最大值），计算其 95% 置信区间。"
            "由于年最大值本身可能不服从正态分布，使用 Bootstrap 方法"
            "（10000次重采样）估计均值和 95 百分位数的置信区间。"
            "对比：Bootstrap 结果和基于正态假设的结果差异。"
        ),
        verification=Verification(
            assertions=[
                "Bootstrap 重采样次数 ≥ 1000",
                "同时报告百分位数法和 BCa 方法的置信区间",
                "对比正态假设和 Bootstrap 的区间宽度",
            ],
            expected_keys=["bootstrap_ci_mean", "bootstrap_ci_p95", "normal_ci"],
            notes="Bootstrap 是处理非正态分布的标准方法。BCa 方法修正偏差。",
        ),
        known_llm_errors=[
            "Bootstrap 重采样次数太少（<1000）导致区间不稳定",
            "混淆百分位数 Bootstrap 和 BCa Bootstrap",
        ],
    ),

    Question(
        id="Q026",
        category=Category.STAT,
        difficulty=Difficulty.EASY,
        title="线性回归 + 残差诊断",
        description=(
            "用 850hPa 风场作为预测因子，拟合站点 PM2.5 浓度的多元线性回归模型。"
            "输出回归系数、R²、调整 R²。"
            "进行残差诊断：\n"
            "1. 检验残差是否近似正态（QQ图或 Shapiro-Wilk 检验）\n"
            "2. 检验残差是否存在自相关（Durbin-Watson 检验）\n"
            "3. 检验是否存在多重共线性（VIF）"
        ),
        verification=Verification(
            assertions=[
                "使用 sklearn.LinearRegression 或 statsmodels.OLS",
                "残差正态性检验",
                "残差自相关检验",
                "VIF 多重共线性检验",
            ],
            expected_keys=["coefficients", "r2", "adj_r2", "dw_statistic", "vif"],
            notes="回归分析后不做残差诊断，等价于盲飞。",
        ),
        known_llm_errors=[
            "直接用 R² 而非调整 R²（变量增多时 R² 必然增加）",
            "不做 VIF——高度相关的预测因子导致系数不可解释",
        ],
    ),

    Question(
        id="Q027",
        category=Category.STAT,
        difficulty=Difficulty.MEDIUM,
        title="小波分析（Wavelet Analysis）",
        description=(
            "对 Niño3.4 指数（1870-2023 年月值）进行连续小波变换（CWT），"
            "使用 Morlet 小波。"
            "绘制小波功率谱，标注 95% 显著性区域和影响锥（Cone of Influence）。"
            "使用 pycwt 或类似库。"
        ),
        verification=Verification(
            assertions=[
                "使用 Morlet 小波（ω₀=6）",
                "标注 Cone of Influence（COI 外的结果不可靠）",
                "显著性检验基于红噪声背景假设",
            ],
            expected_keys=["wavelet_power", "periods", "coi", "significance_mask"],
            notes="小波分析是气候变率研究的标准工具。COI 标注是区分专业和业余的关键。",
        ),
        known_llm_errors=[
            "不标注 COI——长周期在时间序列两端不可靠",
            "显著性检验使用白噪声假设而非红噪声（气候时间序列通常是红噪声）",
        ],
    ),

    Question(
        id="Q028",
        category=Category.STAT,
        difficulty=Difficulty.HARD,
        title="经验正交函数（EEOF / 扩展EOF）",
        description=(
            "对热带太平洋 SST 异常（10°S-10°N, 150°E-90°W）进行扩展 EOF 分析，"
            "滞后窗口为 0, 3, 6, 9, 12 个月。"
            "EEOF 可以捕捉传播型信号（如 ENSO 的东传/西传特征）。"
            "解释第一模态的传播方向。"
        ),
        verification=Verification(
            assertions=[
                "正确构建滞后数据矩阵",
                "EEOF 的空间模态可以分解为各滞后时间的 pattern",
                "从 EEOF 模态中能提取传播方向和速度",
            ],
            expected_keys=["eeof_modes", "propagation_direction", "propagation_speed"],
            notes="EEOF 是 EOF 的扩展，适合分析传播型变率模态。",
        ),
        known_llm_errors=[
            "混淆 EOF 和 EEOF——直接将多滞后拼接当作多变量 EOF",
            "EEOF 模态的物理解释错误（将滞后当作独立空间维度）",
        ],
    ),

    Question(
        id="Q029",
        category=Category.STAT,
        difficulty=Difficulty.EASY,
        title="随机置换检验（Monte Carlo 显著性）",
        description=(
            "你发现撒哈拉沙尘 AOD 与北大西洋飓风频率的相关为 r=-0.45。"
            "使用随机置换检验（1000次随机打乱时间序列）构建 r 的零分布，"
            "判断 -0.45 是否显著（而非依赖 Pearson 的解析 p-value）。"
            "输出：原始 r、置换检验 p-value、零分布的 2.5 和 97.5 百分位数。"
        ),
        verification=Verification(
            assertions=[
                "置换次数 ≥ 1000",
                "每次置换独立打乱其中一个序列",
                "输出置换 p-value 和 Pearson 解析 p-value 对比",
            ],
            expected_keys=["original_r", "permutation_pvalue", "null_ci_low", "null_ci_high"],
            notes="随机置换检验是 Polaris 引擎二的核心方法论——不依赖分布假设。",
        ),
        known_llm_errors=[
            "同时打乱两个序列（而非仅打乱一个）——这不会破坏相关性",
            "置换次数太少（<100）导致 p-value 不稳定",
        ],
    ),

    Question(
        id="Q030",
        category=Category.STAT,
        difficulty=Difficulty.MEDIUM,
        title="去趋势 + 去季节循环（STL 分解）",
        description=(
            "对 1980-2023 年月平均温度时间序列使用 STL（Seasonal-Trend decomposition "
            "using LOESS）分解为趋势项、季节项和残差项。"
            "使用 statsmodels.tsa.seasonal.STL。"
            "验证：三项之和应等于原始序列（重构误差 < 1e-10）。"
        ),
        verification=Verification(
            assertions=[
                "使用 STL 分解（非简单移动平均去趋势）",
                "重构误差 < 1e-10",
                "季节项应为周期性的（每年重复）",
            ],
            expected_keys=["trend", "seasonal", "residual"],
            notes="STL 比简单去趋势/去季节更稳健，能处理变化的季节振幅。",
        ),
        known_llm_errors=[
            "使用简单滑动平均去趋势而非 STL——无法处理变化的季节振幅",
            "STL 参数 period=12 写错为 365",
        ],
    ),

    # ============================================================
    # 第四类：物理诊断（PHYSICS）— 10 题
    # ============================================================
    Question(
        id="Q031",
        category=Category.PHYSICS,
        difficulty=Difficulty.EASY,
        title="检查比湿非负——物理围栏",
        description=(
            "ERA5 再分析的比湿数据（'q'）因插值伪影可能出现微小负值。"
            "编写代码：\n"
            "1. 统计负比湿的格点占比\n"
            "2. 若占 < 0.1%，clip 为 0\n"
            "3. 若占 > 0.1%，发出 WARNING 并标注为可疑数据"
            "这是 Polaris 三级物理围栏（WARNING）的标准实现。"
        ),
        verification=Verification(
            assertions=[
                "统计负值占比",
                "分级处理：<0.1% clip，>0.1% WARNING",
                "不使用 assert——使用条件判断 + logging.warning",
            ],
            expected_keys=["negative_ratio", "action_taken"],
            forbidden=["直接 assert q >= 0——会误杀大量有效数据"],
        ),
        known_llm_errors=[
            "硬 assert q>=0——ERA5 确实有微小负比湿（插值伪影）",
            "不做分级处理——一刀切",
        ],
    ),

    Question(
        id="Q032",
        category=Category.PHYSICS,
        difficulty=Difficulty.EASY,
        title="计算 OLR 并检查物理范围",
        description=(
            "从 ERA5 的 'ttr'（TOA outgoing longwave radiation）变量计算 OLR。"
            "物理范围：OLR ∈ [50, 500] W/m²（极夜时可能低于 100，对流区可达 350）。"
            "标记超出范围的值，打印其位置和数值。"
            "不冻结进程——仅标记（WARNING 级别）。"
        ),
        verification=Verification(
            assertions=[
                "检查 OLR 是否在 [0, 600] 宽范围（允许极端值）",
                "检查 OLR 是否在 [50, 500] 常规范围",
                "超出范围时发出 WARNING 而非 REJECT",
            ],
            expected_keys=["olr_data", "outlier_count", "outlier_locations"],
            notes="OLR 范围检查是物理围栏的经典应用。极夜和深对流是边界情况。",
        ),
        known_llm_errors=[
            "硬编码 OLR ∈ [100, 400]——极夜 OLR 可低至 50 W/m²",
            "使用 REJECT 级别而非 WARNING——不应因少量边界值冻结整个分析",
        ],
    ),

    Question(
        id="Q033",
        category=Category.PHYSICS,
        difficulty=Difficulty.MEDIUM,
        title="计算静力平衡残差",
        description=(
            "使用 ERA5 气压层数据（位势高度 z 和温度 t），"
            "验证大气的静力平衡（hydrostatic balance）：\n"
            "∂Φ/∂p = -RT/p（或差分形式 Δz/Δln(p) ≈ -RT/g）。\n"
            "计算各气压层之间的静力残差，"
            "识别残差 > 15% 的格点和层次（标注为需要检查地形数据）。"
        ),
        verification=Verification(
            assertions=[
                "计算静力平衡残差（差值形式）",
                "残差 > 15% 时发出 REVIEW 级别警告",
                "特别标注近地层（可能受地形影响）",
            ],
            expected_keys=["residual_field", "high_residual_mask"],
            notes="静力平衡是大气基本约束。大残差通常指向地形处理问题或数据错误。",
        ),
        known_llm_errors=[
            "混淆 Δz/Δp 的正负号",
            "误差公式中遗漏气体常数 R 或重力加速度 g",
        ],
    ),

    Question(
        id="Q034",
        category=Category.PHYSICS,
        difficulty=Difficulty.MEDIUM,
        title="计算水平散度并检查质量守恒",
        description=(
            "从 ERA5 的风场 (u, v) 计算水平散度：\n"
            "div = ∂u/∂x + ∂v/∂y（球坐标中使用球谐展开或有限差分）。\n"
            "对全球积分检查质量守恒：∫ div dp dA ≈ 0。\n"
            "残差应小于大气总质量的 1%。"
        ),
        verification=Verification(
            assertions=[
                "使用球坐标的散度公式（包含 cos 纬度项和地球半径）",
                "全球积分残差 < 1%",
                "使用面积权重积分",
            ],
            expected_keys=["divergence", "global_integral", "mass_conservation_error"],
            notes="全球散度积分应近零——这是质量守恒的直接检验。",
        ),
        known_llm_errors=[
            "在等经纬度网格上直接用笛卡尔散度公式（忽略球面几何）",
            "忘记除以地球半径（∂u/∂λ 的单位是 m/s/rad，需要 a*cos(φ) 转换）",
        ],
    ),

    Question(
        id="Q035",
        category=Category.PHYSICS,
        difficulty=Difficulty.HARD,
        title="计算湿静力能并检验对流不稳定",
        description=(
            "从 ERA5 气压层数据计算湿静力能（MSE）：\n"
            "MSE = cp*T + g*z + Lv*q\n"
            "其中 cp=1004 J/(kg·K), Lv=2.5×10⁶ J/kg。\n"
            "检查 MSE 的垂直递减率：若 ∂MSE/∂p > 0（MSE 随高度递减），"
            "说明存在条件不稳定。标注不稳定层和格点。"
        ),
        verification=Verification(
            assertions=[
                "MSE 公式使用正确的常数（cp, g, Lv）",
                "MSE 垂直递减率计算正确（注意气压方向）",
                "识别条件不稳定区域",
            ],
            expected_keys=["mse_field", "instability_mask"],
            notes="湿静力能是诊断对流不稳定性的标准工具。",
        ),
        known_llm_errors=[
            "Lv 取值错误（不同温度下 Lv 不同，但此处使用常数近似）",
            "混淆 ∂MSE/∂p 的符号（气压递减方向）",
        ],
    ),

    Question(
        id="Q036",
        category=Category.PHYSICS,
        difficulty=Difficulty.MEDIUM,
        title="计算位涡（Potential Vorticity）",
        description=(
            "使用 ERA5 数据计算等熵位涡（IPV）：\n"
            "PV = -g * (ζ_θ + f) * ∂θ/∂p\n"
            "其中 ζ_θ 是等熵相对涡度，f 是科氏参数，θ 是位温。\n"
            "在 2 PVU 面（动力对流层顶）输出高度场。"
        ),
        verification=Verification(
            assertions=[
                "使用正确的 PV 公式（包含行星涡度和相对涡度）",
                "f = 2Ω sin(φ) 正确计算",
                "2 PVU = 2×10⁻⁶ K m²/(kg s)（单位转换）",
            ],
            expected_keys=["pv_field", "dynamical_tropopause_height"],
            notes="位涡是动力气象学的核心诊断量。2 PVU 面对应动力对流层顶。",
        ),
        known_llm_errors=[
            "PV 单位混淆（PVU = 10⁻⁶ K m²/(kg s)）",
            "∂θ/∂p 的差分方向和符号",
        ],
    ),

    Question(
        id="Q037",
        category=Category.PHYSICS,
        difficulty=Difficulty.EASY,
        title="从露点温度计算相对湿度",
        description=(
            "ERA5 提供 2m 露点温度（'d2m'）和 2m 温度（'t2m'）。"
            "使用 Bolton (1980) 公式从露点温度计算实际水汽压，"
            "从温度计算饱和水汽压，然后得到相对湿度（RH）。"
            "检查：RH 应在 [0, 100] 范围内。超范围的值 flag 为异常。"
        ),
        verification=Verification(
            assertions=[
                "使用 Bolton (1980) 或 Magnus 公式",
                "RH ∈ [0, 100] 检查",
                "公式中温度单位是 °C（注意 K→°C 转换）",
            ],
            expected_keys=["rh", "e_actual", "e_saturation"],
            forbidden=["混淆 °C 和 K——这是最常见错误"],
        ),
        known_llm_errors=[
            "温度不转换（K 直接代入 °C 公式）——这是最高频错误之一",
            "使用简化公式 es=6.112*exp(17.67*T/(T+243.5)) 但 T 是 K 而非 °C",
        ],
    ),

    Question(
        id="Q038",
        category=Category.PHYSICS,
        difficulty=Difficulty.MEDIUM,
        title="计算大气河流（AR）检测——IVT",
        description=(
            "从 ERA5 的比湿 q 和风场 (u,v) 计算垂直积分水汽通量（IVT）：\n"
            "IVT = |∫(q·V) dp/g| 从 1000 hPa 到 300 hPa。\n"
            "检测 IVT > 250 kg/(m·s) 的区域作为大气河流。"
            "验证：IVT 积分时应使用各气压层权重。"
        ),
        verification=Verification(
            assertions=[
                "垂直积分使用 ∫ dp/g（非简单求和）",
                "IVT 量纲正确：kg/(m·s)",
                "检查各层气压是否单调递减",
            ],
            expected_keys=["ivt", "ar_mask"],
            notes="IVT 是大气河流检测的标准诊断量。垂直积分方法是考点。",
        ),
        known_llm_errors=[
            "垂直积分用简单求和而非 ∫ dp/g——量纲错误",
            "IVT 阈值硬编码为 250（不同研究的阈值不同，应可配置）",
        ],
    ),

    Question(
        id="Q039",
        category=Category.PHYSICS,
        difficulty=Difficulty.HARD,
        title="辐射收支诊断——TOA 和地表",
        description=(
            "从 ERA5 计算大气层顶（TOA）和地表的辐射收支：\n"
            "TOA: R_toa = SSRD - STRD - SSR - STR（向下短波 - 向上短波 - 向上长波）\n"
            "地表: R_sfc = SSRD - SSR + STRD - STR\n"
            "大气辐射加热率 = (R_toa - R_sfc) / (dp/g) / cp\n"
            "检查：全球年平均 TOA 净辐射应接近 0（< 1 W/m² 为合理）。"
        ),
        verification=Verification(
            assertions=[
                "向下为正、向上为负的符号约定一致",
                "全球年平均 TOA 净辐射 < 1 W/m²",
                "大气加热率量纲为 K/day",
            ],
            expected_keys=["r_toa", "r_sfc", "heating_rate"],
            notes="辐射收支是气候系统的核心约束。TOA 近零是全球能量守恒的检验。",
        ),
        known_llm_errors=[
            "辐射通量的符号约定不一致（ERA5 向下为正）",
            "忘记区分 TOA 和地表的辐射变量名（ERA5 中变量名相似）",
        ],
    ),

    Question(
        id="Q040",
        category=Category.PHYSICS,
        difficulty=Difficulty.EASY,
        title="量纲分析——检查输出单位",
        description=(
            "给你的分析代码添加自动量纲检查：\n"
            "1. 温度：应为 K 或 °C（若 > 500 或 < 100，发出 WARNING）\n"
            "2. 降水量：应为 mm 或 kg/m²（若 < 0 或 > 10000/day，发出 WARNING）\n"
            "3. 风速：应为 m/s（若 > 200 m/s，发出 REJECT）\n"
            "4. 气压：应为 Pa 或 hPa（若为 hPa，值应在 [0, 1100] 范围）\n"
            "这是 Polaris 物理围栏装饰器的原型实现。"
        ),
        verification=Verification(
            assertions=[
                "四个变量的量纲检查全部实现",
                "使用分级响应（WARNING / REJECT）",
                "异常值时打印具体位置和数值",
            ],
            expected_keys=["dimension_check_report"],
            notes="量纲错误是 LLM 气象代码中第三高频率的错误类型。",
        ),
        known_llm_errors=[
            "混淆 Pa 和 hPa（差 100 倍）",
            "混淆降水量 mm 和 m（差 1000 倍）",
        ],
    ),

    # ============================================================
    # 第五类：可视化（VIZ）— 10 题
    # ============================================================
    Question(
        id="Q041",
        category=Category.VIZ,
        difficulty=Difficulty.EASY,
        title="绘制全球填色图 + 海岸线",
        description=(
            "绘制全球 2m 温度的等值填色图（contourf）。"
            "要求：\n"
            "1. 使用 cartopy PlateCarree 投影\n"
            "2. 添加海岸线（coastlines）\n"
            "3. 色标为 RdBu_r（冷暖色调）\n"
            "4. 经度标注在 -180-180 范围\n"
            "5. 色标标签包含单位（°C 或 K）"
        ),
        verification=Verification(
            assertions=[
                "使用 cartopy 的 PlateCarree 投影",
                "添加了 coastlines 或使用 cartopy.feature",
                "色标包含单位",
                "经度范围正确 [-180, 180] 或 [0, 360] 一致",
            ],
            expected_keys=["figure"],
            notes="全球填色图是最基础的可视化。经度范围和色标单位是常见遗漏。",
        ),
        known_llm_errors=[
            "不指定投影——地图变形",
            "混淆 cartopy 的 transform=ccrs.PlateCarree() 和 projection= 参数",
            "色标无单位",
        ],
    ),

    Question(
        id="Q042",
        category=Category.VIZ,
        difficulty=Difficulty.EASY,
        title="Hovmöller 图（经度-时间剖面）",
        description=(
            "绘制热带太平洋（5°S-5°N 平均）SST 异常的 Hovmöller 图"
            "（经度-时间剖面），展示 ENSO 的东传/西传特征。"
            "时间范围：1980-2023，经度范围：120°E-80°W。"
        ),
        verification=Verification(
            assertions=[
                "纬度平均正确（5°S-5°N 带平均）",
                "x 轴为经度，y 轴为时间（从下到上为从早到晚）",
                "色标标注单位（°C anomaly）",
            ],
            expected_keys=["hovmoller_figure"],
            notes="Hovmöller 图是展示纬向传播的标准工具。",
        ),
        known_llm_errors=[
            "y 轴时间方向反了（应是从下到上从早到晚）",
            "纬度平均时未对数据进行 anomaly 处理",
        ],
    ),

    Question(
        id="Q043",
        category=Category.VIZ,
        difficulty=Difficulty.MEDIUM,
        title="多面板图（subplot）——4 个季节",
        description=(
            "绘制 DJF, MAM, JJA, SON 四个季节的全球降水异常合成图（2×2 subplot）。"
            "要求：\n"
            "1. 四个面板共享同一个色标\n"
            "2. 每个面板标注季节名称\n"
            "3. 色标范围一致（保证四个面板可比）\n"
            "4. 使用 cartopy 投影"
        ),
        verification=Verification(
            assertions=[
                "2×2 subplot 布局",
                "四个面板共享同一色标范围（vmin/vmax 一致）",
                "每个面板有标题标注季节",
                "使用 cartopy 投影",
            ],
            expected_keys=["figure"],
            notes="多面板图需要统一色标范围——这是最常被遗漏的细节。",
        ),
        known_llm_errors=[
            "四个面板使用独立色标——视觉上不可比",
            "未使用 cartopy 投影——地图变形",
        ],
    ),

    Question(
        id="Q044",
        category=Category.VIZ,
        difficulty=Difficulty.MEDIUM,
        title="打点显著性——叠加 stippling",
        description=(
            "绘制回归系数的全球填色图，并在通过 95% 显著性检验的格点上叠加打点（stippling）。"
            "使用 contourf 绘制系数，使用 contour/contourf + hatches 或 scatter 绘制显著性打点。"
        ),
        verification=Verification(
            assertions=[
                "显著性检验应用到每个格点",
                "打点叠加在填色图之上",
                "颜色和打点同时可辨识",
            ],
            expected_keys=["figure"],
            notes="打点叠加是气象论文的标准可视化元素。",
        ),
        known_llm_errors=[
            "打点覆盖了填色图（透明度或绘图顺序问题）",
            "打点密度太高——整个图全是黑点",
        ],
    ),

    Question(
        id="Q045",
        category=Category.VIZ,
        difficulty=Difficulty.HARD,
        title="垂直剖面图——气压-纬度",
        description=(
            "绘制 30°N 纬圈平均的纬向风 (u) 气压-纬度剖面图。"
            "x 轴为纬度（90°S-90°N），y 轴为气压（1000-10 hPa，对数坐标，递减）。"
            "标注急流核心（jet core）位置。"
        ),
        verification=Verification(
            assertions=[
                "y 轴气压使用对数坐标（或显式标注 hPa 值）",
                "y 轴从下到上气压递减（1000 hPa 在底，10 hPa 在顶）",
                "标注急流核心",
            ],
            expected_keys=["figure", "jet_core_positions"],
            notes="垂直剖面图是展示大气三维结构的关键可视化。气压轴方向是考点。",
        ),
        known_llm_errors=[
            "y 轴气压递增而非递减（地表在顶）",
            "不对数化 y 轴——高层被压缩",
        ],
    ),

    Question(
        id="Q046",
        category=Category.VIZ,
        difficulty=Difficulty.EASY,
        title="Taylor Diagram（多模式评估）",
        description=(
            "你有 5 个 CMIP6 模型对全球降水的模拟结果。"
            "使用 Taylor Diagram 对比各模型与观测（GPCP）的相关性、标准差比值和均方根误差。"
            "标注每个模型点的名称。"
        ),
        verification=Verification(
            assertions=[
                "正确计算各模型的相关性",
                "正确计算各模型的标准差比值",
                "Taylor Diagram 的参考点（观测）在 x 轴 (1,0) 处",
            ],
            expected_keys=["taylor_figure"],
            notes="Taylor Diagram 是多模式评估的标准可视化。",
        ),
        known_llm_errors=[
            "相关性计算前未去季节循环",
            "标准差比值用错了分母（应该是 model_std / obs_std）",
        ],
    ),

    Question(
        id="Q047",
        category=Category.VIZ,
        difficulty=Difficulty.MEDIUM,
        title="风场矢量图（quiver / barbs）",
        description=(
            "绘制 850hPa 风场的矢量图。要求：\n"
            "1. 对风场数据进行稀疏化（每5个格点显示一个箭头，避免过度密集）\n"
            "2. 箭头长度与风速成正比\n"
            "3. 添加参考箭头（如 '10 m/s' 的参照）\n"
            "4. 底图为位势高度等值线"
        ),
        verification=Verification(
            assertions=[
                "风场稀疏化（slice 操作）",
                "参考箭头（quiverkey）",
                "底图位势高度等值线",
            ],
            expected_keys=["figure", "quiverkey"],
            notes="风场矢量图需要注意稀疏化和参考箭头。",
        ),
        known_llm_errors=[
            "不稀疏化——1000+个箭头全部画出，画面全黑",
            "quiver 的 scale 参数未调整——箭头过大或过小",
        ],
    ),

    Question(
        id="Q048",
        category=Category.VIZ,
        difficulty=Difficulty.MEDIUM,
        title="时间序列 + 趋势线 + 置信区间阴影",
        description=(
            "绘制 1980-2023 年全球平均温度异常的年际变化时间序列。"
            "叠加：\n"
            "1. 线性趋势线（虚线）\n"
            "2. 11年滑动平均（实线，红色）\n"
            "3. ±1σ 范围阴影\n"
            "标注趋势值（°C/decade）和对应的 p-value。"
        ),
        verification=Verification(
            assertions=[
                "线性趋势线正确绘制",
                "11年滑动平均（窗口正确）",
                "趋势值和 p-value 标注在图中",
            ],
            expected_keys=["figure"],
            notes="时间序列 + 趋势是气候变化研究的基础可视化。",
        ),
        known_llm_errors=[
            "滑动平均在序列两端产生 NaN，未处理导致图中断线",
            "趋势线标注的单位是 °C/year 而非 °C/decade",
        ],
    ),

    Question(
        id="Q049",
        category=Category.VIZ,
        difficulty=Difficulty.HARD,
        title="三维等熵面图（3D Isentropic Surface）",
        description=(
            "绘制 330K 等熵面的三维图，面上着色为气压（表示等熵面的起伏），"
            "叠加风场矢量。使用 matplotlib 的 3D axes 或 plotly。"
            "视角：从东南方向俯瞰北半球。"
        ),
        verification=Verification(
            assertions=[
                "等熵面正确插值（330K 面上的气压和风场）",
                "投影/视角合理（非默认视角）",
                "坐标轴标注正确",
            ],
            expected_keys=["figure"],
            notes="等熵面是展示大气三维动力结构的高级可视化。",
        ),
        known_llm_errors=[
            "等熵面插值方向错误（应在垂直方向搜索 330K 所在层）",
            "3D 视角默认值导致图形不可读",
        ],
    ),

    Question(
        id="Q050",
        category=Category.VIZ,
        difficulty=Difficulty.EASY,
        title="保存高分辨率图片（300 DPI）",
        description=(
            "将上述任意一张图保存为 PNG，要求：\n"
            "1. 分辨率 ≥ 300 DPI\n"
            "2. 使用 bbox_inches='tight' 避免裁剪\n"
            "3. 文件命名包含日期和变量名（如 '20260716_sst_trend.png'）\n"
            "4. 同时保存 PDF 矢量版本（可选，便于后期编辑）"
        ),
        verification=Verification(
            assertions=[
                "dpi=300 或更高",
                "bbox_inches='tight'",
                "文件名包含日期和变量名",
            ],
            expected_keys=["png_path"],
            notes="图片输出质量直接影响论文发表。300 DPI 是期刊最低要求。",
        ),
        known_llm_errors=[
            "保存时 dpi=72（默认值）——期刊要求 ≥300",
            "未使用 bbox_inches='tight'——标签被裁剪",
        ],
    ),
]


# ═══════════════════════════════════════════════════════════════
# 分类统计
# ═══════════════════════════════════════════════════════════════

def get_questions_by_category(category: Category | None = None) -> list[Question]:
    """按类别筛选题目。"""
    if category is None:
        return QUESTIONS
    return [q for q in QUESTIONS if q.category == category]


def get_question_by_id(qid: str) -> Question | None:
    """按 ID 获取单题。"""
    for q in QUESTIONS:
        if q.id == qid:
            return q
    return None


def print_summary() -> None:
    """打印题目概览。"""
    print(f"\n{'='*60}")
    print(f"  Polaris M0 摸底基准 — 50 题气象编码测试")
    print(f"{'='*60}\n")
    for cat in Category:
        qs = get_questions_by_category(cat)
        difficulties = {
            "easy": sum(1 for q in qs if q.difficulty == Difficulty.EASY),
            "medium": sum(1 for q in qs if q.difficulty == Difficulty.MEDIUM),
            "hard": sum(1 for q in qs if q.difficulty == Difficulty.HARD),
        }
        print(f"  {cat.value:8s}  {len(qs):2d} 题  "
              f"简单:{difficulties['easy']}  中等:{difficulties['medium']}  困难:{difficulties['hard']}")
    print(f"\n  {'总计':8s}  {len(QUESTIONS):2d} 题")
    print()


def print_questions(category: Category | None = None) -> None:
    """列出题目详情。"""
    qs = get_questions_by_category(category)
    for q in qs:
        print(f"\n{'─'*60}")
        print(f"  {q.id} [{q.difficulty.value}] {q.title}")
        print(f"  类别: {q.category.value}")
        print(f"  描述: {q.description[:120]}...")
        print(f"  已知 LLM 错误: {', '.join(q.known_llm_errors[:2])}")


if __name__ == "__main__":
    import sys

    if "--list" in sys.argv:
        print_summary()
        print_questions()
    elif "--category" in sys.argv:
        idx = sys.argv.index("--category")
        cat = Category(sys.argv[idx + 1]) if idx + 1 < len(sys.argv) else None
        print_questions(cat)
    else:
        print_summary()
