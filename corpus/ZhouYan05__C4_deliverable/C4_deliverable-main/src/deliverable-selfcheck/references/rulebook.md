# 平台提交规则速查（实测）

本文件是 `deliverable-selfcheck` 的规则依据，记录 EduSeed/Elite20 平台在
交付物校验与提交环节的实测行为。**规则可能随平台版本变化**，遇到不符时
以平台 `prepare-submission` / `submit` 的返回为准，并回来后修正本文件。

## 1. 交付物匹配：字面子串，不是模糊匹配

`check-deliverables` / `prepare-submission` 的 `requiredDeliverables`
通配符做的是**文件名字面子串匹配**：

| 要求 | 文件 | 平台判定 | 原因 |
| --- | --- | --- | --- |
| `*AI日志*` | `AI_工作日志与AAR.md` | ✗ 缺失 | 下划线把「AI」「日志」断开，文件名不含连续串 `AI日志` |
| `*AAR*` | `AI_工作日志与AAR.md` | ✓ 命中 | 文件名含连续串 `AAR` |
| `*skill说明*` | `ZhouYan05_C4_skill说明.md` | ✓ 命中 | 连续串存在 |

**实践结论**：一个文件要同时满足两类交付物，文件名必须**同时字面包含**
两组关键词。推荐起名：

```
AI_工作日志与AAR.md          -> 只匹配 *AAR*
AI日志与AAR.md              -> 同时匹配 *AI日志* 与 *AAR*   ← 推荐
```

判定方式：`check-deliverables {workdir, requiredDeliverables}` 返回
`missing` / `found` 两个数组；再跑 `prepare-submission`，看
`ready:false` + `actionItems:["补充交付物: *X*"]`。

> 注意：`prepare-submission` 顶层 `ok:true` **不代表可提交**，
> 必须看内层 `deliverables.ok` 与 `ready`。

## 2. 敏感信息过滤：标题/摘要里的「英文冒号 + 空格」

提交时服务端会对文本字段做敏感信息过滤。实测两类拦截：

1. **密钥形态**：`sk-...`、`api key: xxx`、`token: xxx` 等 → 直接拒绝。
2. **key-value 观感**：即使不是密钥，`词: 词` 这种「英文冒号 + 空格」的
   写法也可能被判为疑似密钥形态，整单被拒：

```json
{"error":"字段「projectTitle」提交内容疑似包含敏感信息（密钥/Token（sk- 或 api key 形态））。请脱敏后重新提交。"}
```

**修复**：把英文冒号 `:` 换成破折号 `-` 或全角冒号 `：`，其余内容不动。

**排查顺序**：当载荷里 `sk-` / `task-` / `key` / `token` 全无命中时，
优先怀疑标题/摘要里的 `word: word` 模式，而不是真密钥。

失败任务**不会落库**，修好后重提不算重复提交。

## 3. 其他必填项

- `submit-project` 除文档列出的字段外，服务端还强制要求
  `projectSummary`（项目简介）。缺失即失败：`"error":"缺少必填项：项目简介"`。
- 缺失交付物会触发 `red_flag: missing_artifacts`，
  使 `artifactCompleteness` 得分上限 ≤ 5/15。
  **不要用空文件或占位文件蒙混**——宁可少而实。

## 4. 提交后的状态

- `list-my-submissions` 返回记录含 `status` / `task_state`
  （如 `checked` / `pending_teacher_review`）。
- `get-evaluation {"submissionId":"..."}` 可拉取 AI 评审
  （`score_total` / `feedback` / `evaluator_type` / `evaluation_id`）。
- 权威成功信号：`get-task` 终态 result 里的 `submissionId`。

## 来源

以上均来自本人在 EduSeed Elite20 课程中的真实提交经历与错误返回原文，
非官方文档。规则会变，请以平台实际返回为准。
