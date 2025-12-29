# -*- coding: utf-8 -*-
from table.tools import table_extract
import json

table_html = """
<table><tr><td rowspan="5">基础案例电网装机、负荷和新能源资源参数</td><td>负荷</td><td colspan="3">负荷用电量13043亿kWh</td><td colspan="3">最大负荷22633万kW</td></tr><tr><td>系统预留备用</td><td colspan="6">400万kW</td></tr><tr><td>新能源资源小时数</td><td>风电12108h</td><td>风电22261h</td><td>风电31855h</td><td>光伏11401h</td><td>光伏21022h</td><td>光伏31042h</td></tr><tr><td>水电</td><td colspan="4">水电装机5650万kW</td><td colspan="2">水电发电量1987亿kWh</td></tr><tr><td>火电</td><td colspan="6">23000万kW</td></tr><tr><td rowspan="4">基础案例装机投资成本和运行成本</td><td>电源</td><td colspan="4">成本</td><td colspan="2">价格</td></tr><tr><td>火电</td><td colspan="4">装机投资成本燃煤单价平均煤耗发电运行成本碳捕集装置改造成本碳捕集装置运营成本</td><td colspan="2">6000元/kW1元/kg300g/kWh0.3元/kWh300万元/MW0.07元/kWh</td></tr><tr><td>新能源</td><td colspan="4">风电装机投资成本光伏装机投资成本储能装机投资成本储能容量投资成本</td><td colspan="2">6000元/kW4500元/kW500元/kW2000元/kWh</td></tr><tr><td>联络线</td><td colspan="4">联络线投资成本</td><td colspan="2">3000元/kW</td></tr><tr><td>电量占比</td><td>新能源发电量占比</td><td colspan="4">火电最小技术出力系数</td><td colspan="2">新能源预测误差</td></tr><tr><td rowspan="3">场景设置</td><td>25%</td><td colspan="4">0.4</td><td colspan="2">20%</td></tr><tr><td>40%</td><td colspan="4">0.2</td><td colspan="2">15%</td></tr><tr><td>50%</td><td colspan="4">0.2</td><td colspan="2">10%</td></tr></table>
"""
result = table_extract(table_html=table_html, api_key="sk-734ae048099b49b5b4c7981559765228",
                       base_url="https://dashscope.aliyuncs.com/compatible-mode/v1", model_name="qwen3-14b")
with open('test_result/data.json', 'w', encoding='utf-8') as json_file:
    json.dump(result, json_file, ensure_ascii=False, indent=4)

# 输出结果如下：
# {'key_value': {'河段': '全河段', '冲淤量（万m）': -2267.6, '冲淤厚度': {'平均': -0.57, '最大': 12.1, '最大淤积部位及影响': '最大淤积厚度为12.1m，位于CY02（汇合口以下14km）深槽右侧，淤后高程133m左右，在通航及港口作业区域外，对通
# 航无影响'}, '朝天门汇口以上': {'冲淤量（万m）': -1881.7, '冲淤厚度': {'平均': -1.11, '最大': 3.1, '最大淤积部位及影响': '最大淤积厚度为3.1m，位于CY34（九龙坡河段）断面中部，淤后高程154m左右，对通航无影响'}}, '朝天门汇口以下': {'
# 冲淤量（万m）': -96.2, '冲淤厚度': {'平均': -0.09, '最大': 12.1, '最大淤积部位及影响': '最大淤积厚度为12.1m，位于CY02（汇合口以下14km）深槽右侧，淤后高程133m左右，在通航及港口作业区域外，对通航无影响'}}, '嘉陵江': {'冲淤量（万m
# ）': -289.7, '冲淤厚度': {'平均': -0.25, '最大': 2.1, '最大淤积部位及影响': '最大淤积厚度2.1m，位于CY43（嘉陵江，汇合口上游约1.2km）主槽内，淤后高程155.5m左右，对通航无影响'}}}, 'description': '该表格详细描述了不同河段的冲淤量及
# 冲淤厚度情况。全河段的冲淤量为-2267.6万立方米，平均冲淤厚度为-0.57米，最大淤积厚度为12.1米，最大淤积部位位于CY02（汇合口以下14公里）深槽右侧，淤后高程约为133米，该区域位于通航及港口作业区域外，对通航无影响。朝天门汇口以上的冲淤
# 量为-1881.7万立方米，平均冲淤厚度为-1.11米，最大淤积厚度为3.1米，最大淤积部位位于CY34（九龙坡河段）断面中部，淤后高程约为154米，对通航无影响。朝天门汇口以下的冲淤量为-96.2万立方米，平均冲淤厚度为-0.09米，最大淤积厚度同样为12.1米
# ，最大淤积部位与全河段相同，位于CY02深槽右侧，淤后高程约为133米，对通航无影响。嘉陵江段的冲淤量为-289.7万立方米，平均冲淤厚度为-0.25米，最大淤积厚度为2.1米，最大淤积部位位于CY43（嘉陵江，汇合口上游约1.2公里）主槽内，淤后高程约为
# 155.5米，对通航无影响。'}
