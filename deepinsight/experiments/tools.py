# tools.py
# 作用：用 RDKit 检查分子合法性，并计算 QED + Tanimoto 相似度

from rdkit import Chem, DataStructs
from rdkit.Chem import QED, AllChem


def evaluate_molecule(gen_smiles, ref_smiles):
    """
    评估生成分子质量。

    参数：
        gen_smiles: 模型生成的 SMILES 字符串
        ref_smiles: 参考分子（原始分子）的 SMILES 字符串

    返回：
        dict，固定包含 4 个字段：
        - valid: bool，生成分子是否有效
        - qed: float 或 None，QED 分值（仅在 valid=True 时有值）
        - similarity: float 或 None，与参考分子的 Tanimoto 相似度（仅在 valid=True 时有值）
        - error: str，错误信息（成功时为空字符串）
    """
    result = {
        "valid": False,
        "qed": None,
        "similarity": None,
        "error": "",
    }

    # 1) 解析参考分子（正常情况下应始终合法）
    ref_mol = Chem.MolFromSmiles(ref_smiles)
    if ref_mol is None:
        result["error"] = f"参考分子无效：{ref_smiles}"
        return result

    # 2) 解析生成分子
    gen_mol = Chem.MolFromSmiles(gen_smiles)
    if gen_mol is None:
        result["error"] = f"生成分子无效，无法解析 SMILES：{gen_smiles}"
        return result

    # 3) 额外做一次 sanitize，捕捉化合价等细节错误
    try:
        Chem.SanitizeMol(gen_mol)
    except Exception as e:
        result["error"] = f"生成分子 sanitize 失败：{str(e)}"
        return result

    # 4) 计算指标（QED + Morgan 指纹 Tanimoto）
    try:
        qed_value = float(QED.qed(gen_mol))

        # Morgan fingerprint 常用参数：radius=2, nBits=2048
        gen_fp = AllChem.GetMorganFingerprintAsBitVect(gen_mol, radius=2, nBits=2048)
        ref_fp = AllChem.GetMorganFingerprintAsBitVect(ref_mol, radius=2, nBits=2048)
        sim_value = float(DataStructs.TanimotoSimilarity(gen_fp, ref_fp))

        result["valid"] = True
        result["qed"] = qed_value
        result["similarity"] = sim_value
        result["error"] = ""
        return result
    except Exception as e:
        result["error"] = f"指标计算失败：{str(e)}"
        return result
