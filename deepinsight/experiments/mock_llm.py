# mock_llm.py
# 作用：模拟一个“会在前几轮失败”的多模态大模型输出


def mock_chat_completion(messages):
    """
    模拟聊天式模型接口。
    为了测试反馈循环，这里故意设计为：
      - 第 1 轮：返回非法分子（无效 SMILES）
      - 第 2 轮：返回合法但目标不达标（QED 通常偏低）
      - 第 3 轮及以后：返回更可能达标的分子

    注意：返回文本中必须含有 <SMILES>...</SMILES> 标签。
    """
    # 用函数属性记录调用次数，不需要全局变量
    round_id = getattr(mock_chat_completion, "_round_id", 0) + 1
    mock_chat_completion._round_id = round_id

    if round_id == 1:
        # 非法示例：语法不完整，RDKit 通常会解析失败
        smiles = "C1=CC"
        response = f"我先给出一个候选分子：<SMILES>{smiles}</SMILES>"
        return response

    if round_id == 2:
        # 合法但通常 QED 不高，作为“达标前的失败样本”
        smiles = "CC(=O)Oc1ccccc1C(=O)O"  # 阿司匹林本体
        response = f"根据反馈调整后分子为：<SMILES>{smiles}</SMILES>"
        return response

    # 第 3 轮开始给一个更“药样性友好”且和阿司匹林骨架相近的候选
    smiles = "CC(=O)Oc1ccccc1C(=O)N"  # 与阿司匹林相近，通常相似度较高
    response = f"进一步优化后的候选：<SMILES>{smiles}</SMILES>"
    return response
