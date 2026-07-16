# 大气科学核心期刊白名单

用于 `--include-domains` 学术过滤，按出版社分组。

## AMS（American Meteorological Society）

| 期刊 | 缩写 | 影响因子 | 覆盖领域 | 域名 |
|------|------|----------|----------|------|
| Journal of Climate | JCLI | ~5.0 | 气候学、气候变化、气候诊断 | journals.ametsoc.org |
| Journal of the Atmospheric Sciences | JAS | ~3.0 | 大气动力学、辐射、云物理 | journals.ametsoc.org |
| Monthly Weather Review | MWR | ~3.5 | 天气预报、数值模拟、天气分析 | journals.ametsoc.org |
| Bulletin of the American Meteorological Society | BAMS | ~9.0 | 综合气象、政策、综述 | journals.ametsoc.org |
| Journal of Applied Meteorology and Climatology | JAMC | ~2.5 | 应用气象、遥感、气候应用 | journals.ametsoc.org |
| Weather and Forecasting | WAF | ~2.5 | 天气预报技术、预报验证 | journals.ametsoc.org |
| Journal of Atmospheric and Oceanic Technology | JTECH | ~2.5 | 大气探测技术、仪器 | journals.ametsoc.org |
| Journal of Hydrometeorology | JHM | ~3.5 | 水文气象、降水 | journals.ametsoc.org |
| Earth Interactions | EI | ~2.0 | 地球系统相互作用 | journals.ametsoc.org |
| Artificial Intelligence for the Earth Systems | AIES | 新刊 | AI 在地球科学中的应用 | journals.ametsoc.org |

## AGU（American Geophysical Union）

| 期刊 | 缩写 | 影响因子 | 覆盖领域 | 域名 |
|------|------|----------|----------|------|
| Geophysical Research Letters | GRL | ~5.0 | 地球科学快报（含大气） | agupubs.onlinelibrary.wiley.com |
| JGR-Atmospheres | JGRA | ~4.0 | 大气科学全领域 | agupubs.onlinelibrary.wiley.com |
| JGR-Oceans | JGRA | ~3.5 | 物理海洋 | agupubs.onlinelibrary.wiley.com |
| JGR-Earth Surface | JGRA | ~4.0 | 地表过程 | agupubs.onlinelibrary.wiley.com |
| Earth's Future | EF | ~7.0 | 地球未来、可持续发展 | agupubs.onlinelibrary.wiley.com |
| Reviews of Geophysics | RG | ~18.0 | 地球科学综述 | agupubs.onlinelibrary.wiley.com |

## Springer / Nature

| 期刊 | 缩写 | 影响因子 | 覆盖领域 | 域名 |
|------|------|----------|----------|------|
| Climate Dynamics | CLDY | ~4.5 | 气候动力学、模式、归因 | link.springer.com |
| Advances in Atmospheric Sciences | AAS | ~3.0 | 大气科学综合（中国主办） | link.springer.com |
| Theoretical and Applied Climatology | TAC | ~3.0 | 理论气候学、应用 | link.springer.com |
| Nature Climate Change | NCC | ~28.0 | 气候变化 | nature.com |
| Nature Geoscience | NGEO | ~18.0 | 地球科学综合 | nature.com |
| Nature Communications | NComm | ~16.0 | 综合（含大量大气论文） | nature.com |

## Elsevier

| 期刊 | 缩写 | 影响因子 | 覆盖领域 | 域名 |
|------|------|----------|----------|------|
| Atmospheric Research | ATMRES | ~5.5 | 大气研究、气溶胶、云 | sciencedirect.com |
| Atmospheric Environment | AE | ~4.5 | 大气环境、污染 | sciencedirect.com |
| Journal of Wind Engineering and Industrial Aerodynamics | JWEIA | ~3.5 | 风工程、边界层 | sciencedirect.com |
| Dynamics of Atmospheres and Oceans | DADO | ~2.0 | 大气海洋动力学 | sciencedirect.com |

## IOP / 其他

| 期刊 | 缩写 | 影响因子 | 覆盖领域 | 域名 |
|------|------|----------|----------|------|
| Environmental Research Letters | ERL | ~6.0 | 环境研究、气候变化 | iopscience.iop.org |
| Journal of the Meteorological Society of Japan | JMSJ | ~2.5 | 气象学（日本气象学会） | jstage.jst.go.jp |
| Quarterly Journal of the Royal Meteorological Society | QJRMS | ~4.0 | 气象学（英国皇家气象学会） | rmets.onlinelibrary.wiley.com |
| International Journal of Climatology | IJoC | ~3.5 | 气候学（RMetS） | rmets.onlinelibrary.wiley.com |
| Bulletin of the Russian Academy of Sciences: Atmospheric and Oceanic Physics | IAP | ~1.0 | 大气海洋物理 | link.springer.com |
| SOLA | SOLA | ~1.5 | 气象学快报（日本） | jstage.jst.go.jp |

## 中国主办/合作期刊

| 期刊 | 缩写 | 覆盖领域 | 语言 |
|------|------|----------|------|
| 大气科学（Chinese Journal of Atmospheric Sciences） | CJAS | 大气科学 | 中文/英文 |
| 气象学报（Acta Meteorologica Sinica） | AMS | 气象学 | 中文 |
| 应用气象学报 | JAM | 应用气象 | 中文 |
| 气候与环境研究 | C&ER | 气候环境 | 中文 |
| Journal of Meteorological Research | JMR | 气象研究（CMA） | 英文 |
| Science China Earth Sciences | SCES | 地球科学 | 英文 |

## 搜索引擎域白名单（完整）

```
--include-domains "journals.ametsoc.org,
agupubs.onlinelibrary.wiley.com,
nature.com,
link.springer.com,
sciencedirect.com,
iopscience.iop.org,
rmets.onlinelibrary.wiley.com,
jstage.jst.go.jp,
science.org,
pnas.org,
arxiv.org"
```

## 搜索技巧

- 使用期刊标准缩写（JCLI, GRL, AAS）作为关键词可以提升命中率
- AMS 期刊的 DOI 格式为 `10.1175/{缩写}-D-{年份}-{编号}.1`
- AGU 期刊的 DOI 格式为 `10.1029/{年份}{编号}`
- 在 OpenAlex 中可以用 `primary_location.source.issn` 字段过滤特定期刊
