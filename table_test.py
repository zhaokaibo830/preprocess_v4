from table.tools import table_extract

table_html = """
<table><tr><td rowspan=2 colspan=1>河段</td><td rowspan=2 colspan=1>冲淤量（万m）</td><td rowspan=1 colspan=3>冲淤厚度(m)</td></tr><tr><td rowspan=1 colspan=1>平均</td><td rowspan=1 colspan=1>最大</td><td rowspan=1 colspan=1>最大淤积部位及影响</td></tr><tr><td rowspan=1 colspan=1>全河段</td><td rowspan=1 colspan=1>-2267.6</td><td rowspan=1 colspan=1>-0.57</td><td rowspan=1 colspan=1>12.1</td><td rowspan=1 colspan=1>最大淤积厚度为12.1m，位于CY02（汇合口以下14km）深槽右侧，淤后高程133m左右，在通航及港口作业区域外，对通航无影响</td></tr><tr><td rowspan=1 colspan=1>朝天门汇口以上</td><td rowspan=1 colspan=1>-1881.7</td><td rowspan=1 colspan=1>-1.11</td><td rowspan=1 colspan=1>3.1</td><td rowspan=1 colspan=1>最大淤积厚度为3.1m，位于CY34（九龙坡河段）断面中部，淤后高程154m左右，对通航无影响</td></tr><tr><td rowspan=1 colspan=1>朝天门汇口以下</td><td rowspan=1 colspan=1>-96.2</td><td rowspan=1 colspan=1>-0.09</td><td rowspan=1 colspan=1>12.1</td><td rowspan=1 colspan=1>最大淤积厚度为12.1m，位于CY02（汇合口以下14km）深槽右侧，淤后高程133m左右，在通航及港口作业区域外，对通航无影响</td></tr><tr><td rowspan=1 colspan=1>嘉陵江</td><td rowspan=1 colspan=1>-289.7</td><td rowspan=1 colspan=1>-0.25</td><td rowspan=1 colspan=1>2.1</td><td rowspan=1 colspan=1>最大淤积厚度2.1m，位于CY43（嘉陵江，汇合口上游约1.2km）主槽内，淤后高程155.5m左右，对通航无影响</td></tr></table>
    """
print(table_extract(table_html=table_html, api_key="sk-734ae048099b49b5b4c7981559765228",
                    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1", model_name="qwen3-14b"))


# 输出结果如下：
# {'key_value': {'河段': '全河段', '冲淤量（万m）': -2267.6, '冲淤厚度': {'平均': -0.57, '最大': 12.1, '最大淤积部位及影响': '最大淤积厚度为12.1m，位于CY02（汇合口以下14km）深槽右侧，淤后高程133m左右，在通航及港口作业区域外，对通
# 航无影响'}, '朝天门汇口以上': {'冲淤量（万m）': -1881.7, '冲淤厚度': {'平均': -1.11, '最大': 3.1, '最大淤积部位及影响': '最大淤积厚度为3.1m，位于CY34（九龙坡河段）断面中部，淤后高程154m左右，对通航无影响'}}, '朝天门汇口以下': {'
# 冲淤量（万m）': -96.2, '冲淤厚度': {'平均': -0.09, '最大': 12.1, '最大淤积部位及影响': '最大淤积厚度为12.1m，位于CY02（汇合口以下14km）深槽右侧，淤后高程133m左右，在通航及港口作业区域外，对通航无影响'}}, '嘉陵江': {'冲淤量（万m
# ）': -289.7, '冲淤厚度': {'平均': -0.25, '最大': 2.1, '最大淤积部位及影响': '最大淤积厚度2.1m，位于CY43（嘉陵江，汇合口上游约1.2km）主槽内，淤后高程155.5m左右，对通航无影响'}}}, 'description': '该表格详细描述了不同河段的冲淤量及
# 冲淤厚度情况。全河段的冲淤量为-2267.6万立方米，平均冲淤厚度为-0.57米，最大淤积厚度为12.1米，最大淤积部位位于CY02（汇合口以下14公里）深槽右侧，淤后高程约为133米，该区域位于通航及港口作业区域外，对通航无影响。朝天门汇口以上的冲淤
# 量为-1881.7万立方米，平均冲淤厚度为-1.11米，最大淤积厚度为3.1米，最大淤积部位位于CY34（九龙坡河段）断面中部，淤后高程约为154米，对通航无影响。朝天门汇口以下的冲淤量为-96.2万立方米，平均冲淤厚度为-0.09米，最大淤积厚度同样为12.1米
# ，最大淤积部位与全河段相同，位于CY02深槽右侧，淤后高程约为133米，对通航无影响。嘉陵江段的冲淤量为-289.7万立方米，平均冲淤厚度为-0.25米，最大淤积厚度为2.1米，最大淤积部位位于CY43（嘉陵江，汇合口上游约1.2公里）主槽内，淤后高程约为
# 155.5米，对通航无影响。'}
