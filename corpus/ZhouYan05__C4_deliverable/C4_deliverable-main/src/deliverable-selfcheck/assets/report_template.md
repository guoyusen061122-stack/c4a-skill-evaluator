# 交付物自检报告（模板）

> 由 `deliverable-selfcheck` 生成。示例输出，正式报告请直接运行脚本。

- 目录: `<workdir>`
- 扫描文件数: `<n>`
- 结论: **READY / BLOCKED**

## 逐项核对

- [x] `<要求通配符>` -> `<命中文件>`
- [ ] `<要求通配符>` -> **缺失**（需字面含「<字面串>」）
      - 近似命中（平台不认）: `<文件名>`

## 风险与待办

- **LITERAL_MISMATCH** · `<要求>`
      - 这些文件按直觉通配符能命中、但文件名里不含连续字面串，平台会判为缺失
      - 下一步: 把文件名改成同时字面包含所需关键词的名字

- **EMPTY_FILE** · `<文件>`
      - 文件为 0 字节，平台可能视为无效交付
      - 下一步: 补内容，或删掉占位文件

- **MISSING_PREFIX** · `<文件>`
      - 顶层交付物文件名未包含命名前缀
      - 下一步: 重命名为 `<前缀>_...` 开头

- **SENSITIVE_SHAPE** · `projectTitle`
      - 出现「英文冒号+空格」的 key-value 观感片段
      - 下一步: 把英文冒号换成破折号或全角冒号，其余内容不动

## 机器可读形态

运行 `--json` 时输出：

```json
{
  "workdir": "...",
  "required": ["*AI日志*"],
  "fileCount": 5,
  "found": [{"required": "*AAR*", "literalCore": "AAR", "matched": ["AI日志与AAR.md"], "globOnly": []}],
  "missing": [{"required": "*AI日志*", "literalCore": "AI日志", "matched": [], "globOnly": ["AI_工作日志与AAR.md"]}],
  "warnings": [{"code": "LITERAL_MISMATCH", "item": "*AI日志*", "detail": "...", "action": "..."}],
  "verdict": "BLOCKED"
}
```
