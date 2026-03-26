import os
from pathlib import Path

import streamlit as st
from openai import OpenAI

from deepinsight.config import ROOT_DIR

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
ROLE_PROMPTS = {
    "投资者模式": "你是一名面向投资者的企业分析顾问。重点关注估值逻辑、成长性、风险收益比、资本市场预期和可投资性判断。回答要简洁、有结论，并用条目化方式呈现。",
    "管理者模式": "你是一名服务企业管理层的经营分析顾问。重点关注营收、利润、组织效率、现金流、运营改善建议和战略落地路径。回答要强调可执行性。",
    "监管机构模式": "你是一名服务监管机构的审慎分析顾问。重点关注合规性、风险外溢、信息披露质量、潜在异常交易、处罚与司法风险。回答要客观审慎。",
}


def get_client():
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("缺少 DEEPSEEK_API_KEY 环境变量。")
    return OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)


def build_system_prompt(role_name):
    base_prompt = (
        "你是一个顶级的企业运营分析与决策支持智能体。"
        "请使用专业、清晰、结构化的 Markdown 输出。"
        "当信息不足时，必须明确说明信息不足，不要编造。"
    )
    return f"{base_prompt}\n\n当前角色：{role_name}\n{ROLE_PROMPTS[role_name]}"


def call_deepseek(messages, model):
    client = get_client()
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.5,
        stream=False,
    )
    choice = response.choices[0] if response.choices else None
    if not choice or not choice.message:
        raise RuntimeError("DeepSeek 未返回有效消息。")
    content = choice.message.content or ""
    if not content.strip():
        raise RuntimeError("DeepSeek 返回内容为空。")
    return content


def init_state():
    if "persona_messages" not in st.session_state:
        st.session_state.persona_messages = []
    if "persona_role" not in st.session_state:
        st.session_state.persona_role = "投资者模式"


def render_sidebar():
    st.sidebar.title("角色配置")
    role = st.sidebar.radio("选择角色", list(ROLE_PROMPTS.keys()), index=list(ROLE_PROMPTS.keys()).index(st.session_state.persona_role))
    model = st.sidebar.selectbox("DeepSeek 模型", ["deepseek-chat", "deepseek-reasoner"], index=0 if DEFAULT_MODEL == "deepseek-chat" else 1)
    st.sidebar.markdown("### 当前角色说明")
    st.sidebar.info(ROLE_PROMPTS[role])
    if st.sidebar.button("清空对话"):
        st.session_state.persona_messages = []
    st.session_state.persona_role = role
    return role, model


def main():
    st.set_page_config(page_title="多角色企业分析助手", layout="wide")
    init_state()
    st.title("千人千面多角色路由系统")
    st.caption(f"DeepSeek Base URL: {DEEPSEEK_BASE_URL} | Project: {ROOT_DIR}")
    role, model = render_sidebar()

    for message in st.session_state.persona_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    user_input = st.chat_input("输入你的问题，例如：请从投资者角度分析这家公司")
    if not user_input:
        return

    st.session_state.persona_messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("DeepSeek 正在生成回复..."):
            try:
                messages = [{"role": "system", "content": build_system_prompt(role)}]
                messages.extend(st.session_state.persona_messages)
                answer = call_deepseek(messages, model)
            except Exception as exc:
                st.error(f"调用失败：{exc}")
                return
        st.markdown(answer)
        st.session_state.persona_messages.append({"role": "assistant", "content": answer})


if __name__ == "__main__":
    main()
