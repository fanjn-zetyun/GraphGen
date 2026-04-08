# GraphGen 分区控数速查

## 这份文档给谁看

给接口调用方、平台接入方、任务编排方。

只回答 3 个问题：

1. 我该选哪种分区规则？
2. 我要更多或更少数据，调哪个参数？
3. 当前 `entrypoint.sh` 实际支持哪些参数？

## 一句话结论

如果你只是想控制最终数据集条数，优先这样用：

```text
少量稳定控数：bfs + aggregated
更多结构感：dfs + aggregated
兼顾语义密度：ece + aggregated
优先社区质量：leiden + aggregated
```

## 最重要的公式

```text
最终数据集条数 ≈ 社区数 × 每社区样本数
```

这里：

- 社区数由 `partition_method` 和对应分区参数决定
- 每社区样本数由 `mode` 决定

## 当前入口实际支持的分区参数

通过 `entrypoint.sh` 传 `GRAPHGEN_PARAMS` 时，当前可直接使用的分区规则只有这 4 种：

| partition_method | 主要控数参数 | 规律 |
|---|---|---|
| `bfs` | `bfs_max_units` | 越小条数越多 |
| `dfs` | `dfs_max_units` | 越小条数越多 |
| `ece` | `ece_max_units`、`ece_max_tokens` | 越小条数通常越多 |
| `leiden` | `leiden_max_size` | 越小条数通常越多 |

## 怎么选分区规则

### 1. `bfs`

最推荐的控数规则。

适合：

- 你最关心条数
- 你想快速试参
- 你想让条数变化尽量线性

怎么调：

- 想增大条数：减小 `bfs_max_units`
- 想减小条数：增大 `bfs_max_units`

推荐起手值：

- 想多一些：`1` 到 `3`
- 想中等：`5` 到 `10`
- 想少一些：`20` 到 `50`

### 2. `dfs`

和 `bfs` 很像，只是社区扩展路径不同。

适合：

- 你希望社区更像沿一条路径展开
- 你仍然想比较好地控制条数

怎么调：

- 想增大条数：减小 `dfs_max_units`
- 想减小条数：增大 `dfs_max_units`

### 3. `ece`

更偏“内容密度控制”，不是最线性的控数方法。

适合：

- 你不只想控条数，还想控制社区大小和 token 密度

怎么调：

- 想增大条数：
  - 减小 `ece_max_units`
  - 减小 `ece_max_tokens`
- 想减小条数：
  - 增大 `ece_max_units`
  - 增大 `ece_max_tokens`

提醒：

- `ece` 的条数不如 `bfs/dfs` 好预测

### 4. `leiden`

更偏图社区发现。

适合：

- 你更重视社区结构质量
- 你接受条数不是最容易精确控制

怎么调：

- 想增大条数：减小 `leiden_max_size`
- 想减小条数：增大 `leiden_max_size`

## 当前入口实际支持的生成模式

`mode` 直接决定“每个社区出几条”。

| mode | 当前每社区条数 |
|---|---:|
| `aggregated` | 1 |
| `atomic` | 1 |
| `multi_hop` | 1 |
| `cot` | 1 |
| `multi_choice` | 默认 5 |
| `multi_answer` | 默认 3 |
| `fill_in_blank` | 默认 5 |
| `true_false` | 默认 5 |
| `vqa` | 不固定 |

## 很关键的限制

当前 `entrypoint.sh -> yaml_builder.py` 这条链路里：

- `mode` 能传
- `data_format` 能传
- 但 `num_of_questions` 目前不会透传到 `generate` 节点

这意味着：

- `multi_choice` 现在默认每社区 5 条
- `multi_answer` 现在默认每社区 3 条
- `fill_in_blank` 现在默认每社区 5 条
- `true_false` 现在默认每社区 5 条

如果你想让调用方自己控制这些模式每社区到底出几条，需要改 `yaml_builder.py`。

## 推荐配方

### 配方 1：最稳的控数方式

```json
{
  "partition_method": "bfs",
  "bfs_max_units": 5,
  "mode": "aggregated"
}
```

适合：

- 你想让最终条数尽量可预测

### 配方 2：想明显增大条数

```json
{
  "partition_method": "bfs",
  "bfs_max_units": 1,
  "mode": "aggregated"
}
```

效果：

- 社区会更多
- 每社区 1 条
- 总条数明显增加

### 配方 3：想减少条数

```json
{
  "partition_method": "bfs",
  "bfs_max_units": 20,
  "mode": "aggregated"
}
```

效果：

- 社区更大
- 社区更少
- 总条数下降

### 配方 4：图不大，但还想放大量

```json
{
  "partition_method": "bfs",
  "bfs_max_units": 5,
  "mode": "multi_choice"
}
```

效果：

- 总条数约等于 `社区数 × 5`

## 实际调参顺序

最建议这样调：

1. 先用 `aggregated`
2. 分区先选 `bfs`
3. 通过 `bfs_max_units` 把社区数调到合适范围
4. 如果还嫌少，再改成多题模式

原因：

- 这条路径最简单
- 条数最好解释
- 试错成本最低

## 速查表

| 目标 | 推荐 |
|---|---|
| 想最快控数 | `bfs + aggregated` |
| 想保留路径感 | `dfs + aggregated` |
| 想兼顾 token 密度 | `ece + aggregated` |
| 想做社区发现 | `leiden + aggregated` |
| 图太小还想更多数据 | 保持分区不变，改 `multi_choice` / `true_false` 等多题模式 |

## 调用示例

### 示例 1：约束数据量偏小

```json
{
  "synthesizer_model": "your-model",
  "synthesizer_url": "http://your-llm/v1",
  "api_key": "your-key",
  "upload_file": "/workspace/input/demo.jsonl",
  "final_output_path": "/workspace/output/dataset",
  "partition_method": "bfs",
  "bfs_max_units": 20,
  "mode": "aggregated",
  "data_format": "Alpaca"
}
```

### 示例 2：尽量放大样本数

```json
{
  "synthesizer_model": "your-model",
  "synthesizer_url": "http://your-llm/v1",
  "api_key": "your-key",
  "upload_file": "/workspace/input/demo.jsonl",
  "final_output_path": "/workspace/output/dataset",
  "partition_method": "bfs",
  "bfs_max_units": 1,
  "mode": "aggregated",
  "data_format": "Alpaca"
}
```

### 示例 3：固定社区数后用多题模式放大

```json
{
  "synthesizer_model": "your-model",
  "synthesizer_url": "http://your-llm/v1",
  "api_key": "your-key",
  "upload_file": "/workspace/input/demo.jsonl",
  "final_output_path": "/workspace/output/dataset",
  "partition_method": "bfs",
  "bfs_max_units": 5,
  "mode": "multi_choice",
  "data_format": "Alpaca"
}
```

## 如果你只想记一句

优先用 `bfs + aggregated`，通过 `bfs_max_units` 控条数。

