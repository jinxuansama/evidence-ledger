# Evidence Ledger：研究证据台账

一个离线运行的研究引用检查工具。记录来源文件 SHA-256、原文摘录、
事实与解释的区别，以及 Markdown 正文中的显式引用。适合研究报告、
论文草稿和需要回溯来源的正式写作。

**通过检查只表示文件与引用一致，不代表事实正确，也不代表摘录足以支持结论。**
没有 `[[claim:ID]]` 标记的正文不会被检查；解释类条目必须写明推理依据。

Python 3.10 以上，无运行时第三方依赖，无须模型账号。从项目目录运行：

```sh
python -m pip install .
evidence-ledger audit examples/ledger.json --draft examples/draft.md
evidence-ledger hash examples/source.txt
python -m unittest discover -s tests -v
```

示例完全虚构。改动来源文件后，原来的摘要即失效，工具会报错。
原文须保存为 UTF-8 文本，路径必须位于台账目录内；不得擅自公开受版权或
保密约束的来源。初始版本不解析 PDF、不联网抓取、不自动判断语义。

退出码：0 为通过，1 为证据检查失败，2 为输入或文件错误。
详细字段见 [设计文档](docs/design.md)。MIT 开源，欢迎提交可复现的问题。
