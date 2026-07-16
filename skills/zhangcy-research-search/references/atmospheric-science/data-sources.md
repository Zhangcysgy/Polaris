# 大气科学数据源速查

## 再分析资料

| 数据集 | 机构 | 分辨率 | 时间范围 | 获取方式 |
|--------|------|--------|----------|----------|
| **ERA5** | ECMWF | 0.25°×0.25°, 1h | 1940-今 | cdsapi (Python) / Climate Data Store |
| **ERA5-Land** | ECMWF | 0.1°×0.1°, 1h | 1950-今 | cdsapi |
| **NCEP/NCAR Reanalysis I** | NOAA | 2.5°×2.5°, 6h | 1948-今 | NOAA PSL / IRIDL |
| **NCEP/DOE Reanalysis II** | NOAA | 2.5°×2.5°, 6h | 1979-今 | NOAA PSL |
| **JRA-55** | JMA | 1.25°×1.25°, 3h/6h | 1958-今 | JMA / DiCRA |
| **MERRA-2** | NASA | 0.5°×0.625°, 1h | 1980-今 | NASA GES DISC |
| **CFSR/CFSv2** | NOAA | ~0.5°, 1h/6h | 1979-今 | NOAA / NCAR |

## 气候模式

| 数据集 | 说明 | 获取方式 |
|--------|------|----------|
| **CMIP6** | 第六次耦合模式比对计划 | ESGF 节点 / Pangeo |
| **CMIP5** | 第五次耦合模式比对 | ESGF |
| **CORDEX** | 区域气候降尺度 | ESGF / CORDEX 网站 |
| **FGOALS-g3** | 中国科学院大气所模式 | CMIP6 ESGF |

## 观测数据

| 数据集 | 变量 | 分辨率 | 获取方式 |
|--------|------|--------|----------|
| **GPCP** | 全球降水 | 2.5°, 月/日 | NASA |
| ** TRMM (3B42)** | 热带降水 | 0.25°, 3h | NASA GES DISC (已退役) |
| **GPM (IMERG)** | 全球降水 | 0.1°, 30min | NASA GES DISC |
| **ISCCP** | 云量 | 2.5°, 3h | ISCCP 网站 |
| **CERES** | 辐射通量 | 1°, 月 | NASA CERES |
| **HadCRUT5** | 全球温度 | 5°, 月 | Met Office Hadley Centre |
| **NOAA OISST** | 海温 | 0.25°, 日 | NOAA PSL |
| **中国自动站降水** | 降水 | 站点 | 中国气象数据网 |

## 预报数据

| 系统 | 机构 | 分辨率 | 预报时效 | 获取方式 |
|------|------|--------|----------|----------|
| **GFS** | NCEP/NOAA | 0.25° | 16天 | NOAA NCEP |
| **ECMWF HRES** | ECMWF | 0.1° | 15天 | ECMWF (付费) |
| **CMA-GFS (GRAPES)** | CMA | 0.25° | 10天 | CMA 数值预报中心 |
| **ICON** | DWD | 0.0625° | 5-7天 | DWD OpenData |

## 关键 API

| 服务 | URL | 用途 |
|------|-----|------|
| **CDS API** | `cds.climate.copernicus.eu` | ERA5 / CORDEX 等 |
| **NOAA PSL** | `psl.noaa.gov` | NCEP 再分析、OISST |
| **NASA POWER** | `power.larc.nasa.gov` | 气象数据 API |
| **NASA GES DISC** | `disc.gsfc.nasa.gov` | MERRA-2、卫星数据 |
| **CMA 数据网** | `data.cma.cn` | 中国气象数据 |
