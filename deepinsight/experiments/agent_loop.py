# agent_loop.py
# 作用：串联 mock LLM + RDKit 工具评估，形成最多 5 轮的反馈闭环

import re
from pathlib import Path

from rdkit import Chem
from rdkit.Chem import AllChem, Draw

from deepinsight.config import REFERENCE_MOLECULE_IMAGE
from deepinsight.experiments.tools import evaluate_molecule
from deepinsight.experiments.mock_llm import mock_chat_completion


def save_molecule_image(smiles, image_path):
    """
    将 SMILES 生成 2D 结构图保存到本地文件。
    """
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"参考分子无效，无法绘图：{smiles}")

    # 计算 2D 坐标，便于画结构图
    AllChem.Compute2DCoords(mol)
    Draw.MolToFile(mol, str(image_path), size=(420, 320))


def extract_smiles(text):
    """
    从模型输出中提取 <SMILES>...</SMILES> 标签内容。
    """
    match = re.search(r"<SMILES>(.*?)</SMILES>", text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return match.group(1).strip()


def build_feedback(eval_result, target_qed, target_sim):
    """
    把工具评估结果转成下一轮给模型的文本反馈。
    """
    if not eval_result["valid"]:
        return f"Invalid molecule. Error: {eval_result['error']}"

    problems = []
    if eval_result["qed"] < target_qed:
        problems.append(f"QED is {eval_result['qed']:.3f}, need >= {target_qed:.3f}")
    if eval_result["similarity"] < target_sim:
        problems.append(f"Similarity is {eval_result['similarity']:.3f}, need >= {target_sim:.3f}")

    if not problems:
        return "Success: all constraints satisfied."

    return "Valid but " + "; ".join(problems)


def print_history(messages):
    """
    打印当前累积对话历史，便于观察“记忆”和反馈是如何叠加的。
    """
    role_map = {"system": "SYSTEM", "user": "USER", "assistant": "ASSISTANT"}
    print("\n----- 当前对话历史（累计）-----")
    for i, m in enumerate(messages, start=1):
        role = role_map.get(m["role"], m["role"].upper())
        print(f"[{i:02d}] {role}: {m['content']}")
    print("----- 对话历史结束 -----\n")


def main():
    # ===== 配置区 =====
    ref_smiles = "CC(=O)Oc1ccccc1C(=O)O"  # 阿司匹林
    target_qed = 0.60
    target_similarity = 0.40
    max_rounds = 5

    # 生成并保存参考分子的 2D 图片（模拟“视觉输入”）
    image_path = REFERENCE_MOLECULE_IMAGE.resolve()
    save_molecule_image(ref_smiles, image_path)

    # 初始化消息历史：包含系统设定 + 首条任务描述
    messages = [
        {
            "role": "system",
            "content": "你是分子优化助手。必须输出且仅输出一个 <SMILES>...</SMILES> 标签。",
        },
        {
            "role": "user",
            "content": (
                f"视觉输入图片路径：{image_path}\n"
                f"参考分子：{ref_smiles}\n"
                f"目标：QED >= {target_qed} 且 Similarity >= {target_similarity}。"
            ),
        },
    ]

    print("=" * 90)
    print("MVP Agent Loop 启动")
    print(f"参考分子图片已保存：{image_path}")
    print(f"约束条件：QED >= {target_qed}，Similarity >= {target_similarity}")
    print("=" * 90)

    success = False
    final_result = None
    final_smiles = None

    for round_idx in range(1, max_rounds + 1):
        print(f"\n{'=' * 30} Round {round_idx} {'=' * 30}")

        # 1) 调用模拟大模型
        llm_output = mock_chat_completion(messages)
        messages.append({"role": "assistant", "content": llm_output})

        print("[大模型输出]")
        print(llm_output)

        # 2) 解析 <SMILES> 标签
        gen_smiles = extract_smiles(llm_output)
        if gen_smiles is None:
            eval_result = {
                "valid": False,
                "qed": None,
                "similarity": None,
                "error": "模型输出中未找到 <SMILES>...</SMILES> 标签",
            }
        else:
            eval_result = evaluate_molecule(gen_smiles, ref_smiles)

        final_result = eval_result
        final_smiles = gen_smiles

        # 3) 打印工具反馈
        qed_str = f"{eval_result['qed']:.3f}" if eval_result["qed"] is not None else "N/A"
        sim_str = f"{eval_result['similarity']:.3f}" if eval_result["similarity"] is not None else "N/A"

        print("\n[工具反馈 RDKit]")
        print(f"- valid      : {eval_result['valid']}")
        print(f"- qed        : {qed_str}")
        print(f"- similarity : {sim_str}")
        print(f"- error      : {eval_result['error'] or 'None'}")

        # 4) 判断是否达标
        if (
            eval_result["valid"]
            and eval_result["qed"] >= target_qed
            and eval_result["similarity"] >= target_similarity
        ):
            success = True
            print("\n[状态] 成功：约束已满足，提前结束循环。")
            print_history(messages)
            break

        # 5) 构造反思反馈，喂给下一轮
        feedback_text = build_feedback(eval_result, target_qed, target_similarity)
        user_reflection = (
            f"第 {round_idx} 轮评估反馈：{feedback_text}\n"
            f"请根据反馈重新生成一个分子，只输出一个 <SMILES>...</SMILES>。"
        )
        messages.append({"role": "user", "content": user_reflection})

        print("\n[写回模型的反馈 Prompt]")
        print(user_reflection)

        # 打印累计历史，观察多轮上下文如何堆叠
        print_history(messages)

    print("\n" + "=" * 90)
    print("运行结束")
    print(f"是否成功：{success}")
    print(f"最终分子：{final_smiles}")
    if final_result is not None:
        print(f"最终评估：{final_result}")
    print("=" * 90)


if __name__ == "__main__":
    main()
