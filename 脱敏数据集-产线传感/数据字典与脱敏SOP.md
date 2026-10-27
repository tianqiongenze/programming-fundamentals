# 数据字典
| 字段 | 类型 | 说明 |
|------|------|------|
| station_id_pseudo | str | 伪匿名工位号 ST-00~04 |
| ts | str | 三种格式混杂时间戳(清洗练习点) |
| temp_c | float/空/N/A | 含缺失(空)、类型错(N/A)、越界(>120) |
| press_mpa | float | 0.3-0.6 |
| status | str | RUN/IDLE |

# 脱敏SOP(要点)
工位真名→ST编号伪匿名；班次人员信息已剔除；时间戳保留到分钟(泛化)。
