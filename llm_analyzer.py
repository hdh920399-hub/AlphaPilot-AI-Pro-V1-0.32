import os
import requests
import streamlit as st


class LLMAnalyzer:
    """
    大模型调用封装
    支持智谱（默认）、OpenAI
    """

    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "zhipu")
        self.api_key = os.getenv("ZHIPU_API_KEY", "")
        self.model = os.getenv("LLM_MODEL", "glm-4-flash")

    def get_completion(self, prompt, max_tokens=500):
        if not self.api_key:
            return "未配置 ZHIPU_API_KEY 环境变量。"
        if self.provider == "zhipu":
            return self._call_zhipu(prompt, max_tokens)
        elif self.provider == "openai":
            return self._call_openai(prompt, max_tokens)
        else:
            return f"不支持的 LLM provider: {self.provider}"

    def _call_zhipu(self, prompt, max_tokens):
        try:
            url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            data = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.7,
            }
            resp = requests.post(url, json=data, headers=headers, timeout=30)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"智谱调用失败: {e}"

    def _call_openai(self, prompt, max_tokens):
        try:
            import openai
            openai.api_key = self.api_key
            resp = openai.ChatCompletion.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content
        except Exception as e:
            return f"OpenAI 调用失败: {e}"
