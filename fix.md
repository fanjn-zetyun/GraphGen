# GraphGen Bug Fix Report

## 问题背景

执行 `entrypoint.sh` 后流程报错退出，最终输出文件为空（0 bytes）。

---

## Bug 1：`<|>` 分隔符触发 API 内容审核

### 根本原因

KG 提取阶段向 LLM API 发送的 prompt 中包含 `<|>` 符号，例如：

```
将每个实体格式化为("entity"<|><entity_name><|><entity_type><|><entity_summary>)
```

baicaiinfer 的内容审核系统将 `<|>` 误判为不适当内容，返回：

```
Error code: 400 - {'message': 'The content contains inappropriate information and does not pass the review.'}
```

API 拦截后，`build_kg` 阶段提取到 0 个实体和关系，导致后续 partition → generate 全部产出空数据。

### 修复方法

将以下三个模板文件中 `FORMAT` 字典的 `tuple_delimiter` 从 `"<|>"` 改为 `"|||"`。

---

#### 文件 1：`graphgen/templates/kg/kg_extraction.py`

找到 `FORMAT` 字典，修改 `tuple_delimiter`：

```python
# 修改前
"FORMAT": {
    "tuple_delimiter": "<|>",
    ...
}

# 修改后
"FORMAT": {
    "tuple_delimiter": "|||",
    ...
}
```

同时，将该文件中两个中文示例（`-示例 1-` 和 `-示例 2-`）的内容替换为中性的科技/地理类文本，避免原有的鲁迅《孔乙己》片段和农业论文片段触发审核。

**示例 1** 替换为人工智能相关文本，包含以下实体和关系：
- 实体：人工智能、机器学习、深度学习、自然语言处理、神经网络、图像识别
- 关系：机器学习是人工智能的核心技术；深度学习是机器学习的子领域；等

**示例 2** 替换为北京地理/教育类文本，包含以下实体和关系：
- 实体：北京、中华人民共和国、华北平原、燕山山脉、北京大学、清华大学、海淀区、故宫博物院
- 关系：北京是首都；北京大学/清华大学位于海淀区；等

示例中所有分隔符同步使用新的 `|||`，例如：

```
("entity"|||"人工智能"|||"concept"|||"计算机科学的重要分支...")##
("relationship"|||"人工智能"|||"机器学习"|||"机器学习是人工智能的核心技术之一。")##
("content_keywords"|||"人工智能, 机器学习, 深度学习...")<|COMPLETE|>
```

---

#### 文件 2：`graphgen/templates/kg/kg_summarization.py`

找到 `FORMAT` 字典，修改 `tuple_delimiter`：

```python
# 修改前
"FORMAT": {
    "tuple_delimiter": "<|>",
    "record_delimiter": "##",
    "completion_delimiter": "<|COMPLETE|>",
}

# 修改后
"FORMAT": {
    "tuple_delimiter": "|||",
    "record_delimiter": "##",
    "completion_delimiter": "<|COMPLETE|>",
}
```

---

#### 文件 3：`graphgen/templates/kg/mm_kg_extraction.py`

找到 `FORMAT` 字典，修改 `tuple_delimiter`：

```python
# 修改前
"FORMAT": {
    "tuple_delimiter": "<|>",
    "record_delimiter": "##",
    "completion_delimiter": "<|COMPLETE|>",
    "entity_types": "...",
}

# 修改后
"FORMAT": {
    "tuple_delimiter": "|||",
    "record_delimiter": "##",
    "completion_delimiter": "<|COMPLETE|>",
    "entity_types": "...",
}
```

### 注意事项

- `record_delimiter`（`##`）和 `completion_delimiter`（`<|COMPLETE|>`）**不需要修改**，测试确认这两个符号不触发审核。
- 只有 `<|>` 这个特定符号会被拦截。
- 修改后 `tuple_delimiter` 的值会自动注入到所有 prompt 模板的 `{tuple_delimiter}` 占位符中，解析逻辑无需改动。

---

## Bug 2：entrypoint.sh 文件扩展名匹配错误

### 根本原因

`entrypoint.sh` 步骤 3 用 `*.json` 匹配 Ray 输出的文件，但 Ray 的 `write_json` 实际生成的是 `.jsonl` 扩展名的文件，例如：

```
/tmp/graphgen_workspace/output/1774878505/generate/generate_eb4c3271a7474061b3d84590d25f1601_000000_000000.jsonl
```

`*.json` 匹配不到任何文件，`cat` 输出为空，导致目标文件大小为 0，触发报错退出。

### 修复方法

修改 `entrypoint.sh` 中合并文件的那一行，同时匹配 `.jsonl` 和 `.json`：

```bash
# 修改前（第 129 行附近）
# 合并所有 JSON 文件并移动到指定路径
# Ray 的 write_json 会生成多个分片文件，需要合并
cat "${LATEST_OUTPUT}"/*.json > "$TARGET_PATH" 2>/dev/null || true

# 修改后
# 合并所有 JSON/JSONL 文件并移动到指定路径
# Ray 的 write_json 会生成多个分片文件（.jsonl 或 .json），需要合并
cat "${LATEST_OUTPUT}"/*.jsonl "${LATEST_OUTPUT}"/*.json > "$TARGET_PATH" 2>/dev/null || true
```

`2>/dev/null || true` 保证当某种扩展名不存在时不报错，行为不变。

---

## Bug 3：输出文件包含非标准字段 `_trace_id`

### 根本原因

`_trace_id` 是 GraphGen 内部用于追踪数据流转的元数据字段，在各算子之间传递。`generate_service.py` 将其写入每条结果记录，最终随数据一起落盘，导致输出文件中出现非标准字段：

```json
{"instruction": "...", "input": "", "output": "...", "_trace_id": "generate-xxx"}
```

标准 Alpaca 格式只包含 `instruction`、`input`、`output` 三个字段，`_trace_id` 不应出现在最终输出中。

### 修复方法

修改 `graphgen/engine.py`，在调用 `write_json` 写出文件之前，drop 掉所有以 `_` 开头的内部字段：

```python
# 修改前
ds = self.datasets[node.id]
ds.write_json(
    node_output_path,
    ...
)

# 修改后
ds = self.datasets[node.id]
# Drop internal metadata fields before writing final output
cols_to_drop = [c for c in ds.columns() if c.startswith("_")]
if cols_to_drop:
    ds = ds.drop_columns(cols_to_drop)
ds.write_json(
    node_output_path,
    ...
)
```

### 注意事项

- `_trace_id` 在内部流转（`base_operator.py` 的 `store` 方法、`generate_service.py`）中是必须的，**不能**在上游删除，只在最终写出时去掉。
- 用 `c.startswith("_")` 而非硬编码 `"_trace_id"`，可以一并过滤掉未来可能新增的其他内部字段。

---

## 修复验证

修复后重新执行 `bash entrypoint.sh`，流程正常完成：

```
build_kg:  34 entities, 35 relationships 提取成功
generate:  4 rows, 7.7KiB 数据写出
输出文件已保存到: /workspace/user-data/datasets/test/2026-03-30-19-55_27.json
GraphGen 完成
```

输出为标准 Alpaca 格式，每行一个 JSON 对象，仅包含 `instruction`、`input`、`output` 三个字段，无任何内部元数据字段。