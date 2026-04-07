# GraphGen 知识图谱分区与数据集条数控制手册

## 目的

这份手册说明两件事：

1. 不同知识图谱分区规则如何影响 `generate` 阶段的输入社区数。
2. 如何通过分区参数和生成模式参数，控制最终落盘的数据集条数。

适用范围：

- `entrypoint.sh`
- `yaml_builder.py`
- 本地运行的 `graphgen.run_local`

## 先记住一条总公式

最终数据集条数，近似等于：

```text
最终样本数 = 社区数 × 每个社区产出的问答数 × 解析成功率
```

其中：

- 社区数：由分区规则决定。
- 每个社区产出的问答数：由生成模式决定。
- 解析成功率：取决于模型输出是否符合模板，实际可能小于 100%。

如果只看“如何控制条数”，最核心的是先分清：

- 分区规则控制“会切成多少个社区”
- 生成模式控制“每个社区会吐出几条样本”

## 生成模式对条数的影响

在默认链路里，`generate` 节点会对每个社区生成数据。不同 `mode` 下，每个社区理论产出条数如下。

| mode | 每个社区理论条数 | 主要控制参数 |
|---|---:|---|
| `aggregated` | 1 | 无 |
| `atomic` | 1 | 无 |
| `multi_hop` | 1 | 无 |
| `cot` | 1 | 无 |
| `multi_choice` | `num_of_questions` | `num_of_questions` |
| `multi_answer` | `num_of_questions` | `num_of_questions` |
| `fill_in_blank` | `num_of_questions` | `num_of_questions` |
| `true_false` | `num_of_questions` | `num_of_questions` |
| `vqa` | 由模型返回条数决定 | 无固定上限 |

经验上：

- 想精确控制总条数，优先用 `aggregated`、`atomic`、`multi_hop`、`cot` 这类“每社区 1 条”的模式。
- 想放大条数，再切换到 `multi_choice`、`multi_answer`、`fill_in_blank`、`true_false`，并调高 `num_of_questions`。

## 分区规则如何影响社区数

### 1. `bfs`

特点：

- 从随机种子出发，用 BFS 扩社区。
- 控制最直接。
- 最适合拿来“粗调总条数”。

关键参数：

- `bfs_max_units`

社区数的近似关系：

```text
社区数 ≈ 图中的总 unit 数 / bfs_max_units
```

这里的 `unit` 指：

- 一个节点
- 或一条边

所以：

- `bfs_max_units` 越小，社区越多，最终数据集条数通常越多。
- `bfs_max_units` 越大，社区越少，最终数据集条数通常越少。

实操建议：

- 想要更多样本：把 `bfs_max_units` 调到 `1`、`2`、`3`
- 想要更少样本：把 `bfs_max_units` 调到 `10`、`20`、`50`

适用场景：

- 你不关心社区质量，重点只是控制数据量。
- 你需要可预测、线性的调参手感。

### 2. `dfs`

特点：

- 和 `bfs` 一样，核心也是按固定 unit 数切社区。
- 区别只是扩展路径是 DFS，不是 BFS。

关键参数：

- `dfs_max_units`

社区数的近似关系：

```text
社区数 ≈ 图中的总 unit 数 / dfs_max_units
```

条数控制规律和 `bfs` 基本一致：

- `dfs_max_units` 越小，条数越多。
- `dfs_max_units` 越大，条数越少。

适用场景：

- 想保留更强的路径连续性。
- 希望一个社区更像沿着一条链路展开。

如果你的目标只是“好调条数”，通常优先选 `bfs`，因为它更直观。

### 3. `ece`

特点：

- 先按 unit 采样，再按 BFS 扩展。
- 同时受“最大 unit 数”和“最大 token 数”双重约束。
- 社区数比 `bfs`/`dfs` 更难精确预测。

关键参数：

- `ece_max_units`
- `ece_min_units`
- `ece_max_tokens`
- `ece_unit_sampling`

社区数的主要影响关系：

- `ece_max_units` 越小，社区数通常越多。
- `ece_max_tokens` 越小，社区更容易提前截断，社区数通常越多。
- `ece_min_units` 越大，小社区更可能被丢掉，社区数可能变少。
- `ece_unit_sampling` 主要影响抽样顺序，影响社区内容，条数影响通常次于前面三个参数。

可以把它理解为：

```text
社区数 ≈ 受 max_units 和 max_tokens 共同切分后的社区数
```

实操建议：

- 想明显增大条数：
  - 降低 `ece_max_units`
  - 降低 `ece_max_tokens`
- 想明显减小条数：
  - 提高 `ece_max_units`
  - 提高 `ece_max_tokens`
- 想减少碎片化：
  - 不要把 `ece_min_units` 设得太大

适用场景：

- 你既想控制条数，又想让社区大小更贴近内容密度。
- 你希望比 `bfs/dfs` 更“语义友好”一点，但接受条数不那么线性。

### 4. `leiden`

特点：

- 先用 Leiden 算法做社区发现，再按 `max_size` 切大社区。
- 更偏“图结构质量”，不是偏“条数线性控制”。

关键参数：

- `leiden_max_size`
- `leiden_use_lcc`
- `leiden_random_seed`

社区数的主要影响关系：

- `leiden_max_size` 越小，大社区会被切得越碎，最终条数越多。
- `leiden_max_size` 越大，切分越少，最终条数越少。
- `leiden_use_lcc=true` 时，只保留最大连通子图，通常会减少覆盖范围，条数可能变少。
- `leiden_random_seed` 会影响划分结果，但主要影响分区形态，不适合作为条数主调参数。

可以把它理解为：

```text
社区数 = Leiden 原始社区数 + 超大社区被 max_size 二次切分后的增量
```

实操建议：

- 想要更稳定地增加条数，优先调小 `leiden_max_size`
- 想要更少、更大的社区，调大 `leiden_max_size`

适用场景：

- 你优先看重社区结构质量，而不是只看数据量。
- 你做的是图社区级别的数据构造，不想用纯 BFS/DFS 生切。

## 目前 `entrypoint.sh` 已接线支持的分区规则

通过 `yaml_builder.py` 当前能直接使用的分区规则有：

- `ece`
- `bfs`
- `dfs`
- `leiden`

对应参数名：

| partition_method | 条数主控参数 |
|---|---|
| `ece` | `ece_max_units`、`ece_max_tokens` |
| `bfs` | `bfs_max_units` |
| `dfs` | `dfs_max_units` |
| `leiden` | `leiden_max_size` |

## 代码里有但当前入口未直接接线的规则

代码里还存在：

- `anchor_bfs`

它的控制规律和 `bfs` 类似，但有一个额外前提：

- 只有 anchor 节点才会成为种子

所以它的总条数上限更接近：

```text
社区数 <= anchor 节点数
```

再叠加 `max_units_per_community` 的影响。

这个规则适合图像/VQA 一类“围绕锚点生成”的任务，但当前 `yaml_builder.py` 没有把它暴露成 `partition_method` 选项。如果要用，需要额外改配置构造逻辑。

## 如何按目标条数调参

### 场景 1：想要尽量稳定地生成约 N 条数据

推荐：

- `mode=aggregated`
- 分区规则用 `bfs` 或 `dfs`

原因：

- 每个社区只生成 1 条，最容易反推。

调法：

1. 先跑一次，观察实际社区数。
2. 如果条数偏多，就调大 `bfs_max_units` 或 `dfs_max_units`。
3. 如果条数偏少，就调小 `bfs_max_units` 或 `dfs_max_units`。

经验公式：

```text
新的 max_units ≈ 旧的 max_units × 实际条数 / 目标条数
```

这是工程上的粗调公式，不保证一次命中，但通常够快。

### 场景 2：想在社区质量和条数之间折中

推荐：

- `mode=aggregated`
- 分区规则用 `ece` 或 `leiden`

调法：

- `ece`：
  - 先调 `ece_max_units`
  - 再调 `ece_max_tokens`
- `leiden`：
  - 主要调 `leiden_max_size`

经验上：

- 想增加条数，优先减小社区上限。
- 想减少条数，优先增大社区上限。

### 场景 3：图已经不大，但还想再放大量

推荐：

- 保持分区不变
- 改生成模式为多题模式

例如：

- `multi_choice`
- `multi_answer`
- `fill_in_blank`
- `true_false`

然后调：

- `num_of_questions`

这时：

```text
最终样本数 ≈ 社区数 × num_of_questions
```

## 推荐调参顺序

建议按这个顺序调：

1. 先定生成模式
2. 再定分区规则
3. 再调社区大小参数
4. 最后根据一次试跑结果回算

更具体地说：

1. 如果你想精确控制条数，先用单条模式：
   - `aggregated`
   - `atomic`
   - `multi_hop`
   - `cot`
2. 如果你想先控制社区数，优先选：
   - `bfs`
   - `dfs`
3. 如果你想先保证社区质量，再接受条数波动，选：
   - `ece`
   - `leiden`
4. 如果图本身太小、社区数上不去，再改成多题模式放大。

## 参数示例

### 例 1：想要更多条数，优先走 `bfs`

```json
{
  "partition_method": "bfs",
  "bfs_max_units": 1,
  "mode": "aggregated"
}
```

解释：

- 每个社区尽量小
- 每个社区生成 1 条
- 条数通常会比较多

### 例 2：想要更少条数，优先走 `bfs`

```json
{
  "partition_method": "bfs",
  "bfs_max_units": 20,
  "mode": "aggregated"
}
```

解释：

- 每个社区更大
- 社区数下降
- 总条数通常下降

### 例 3：想保留结构质量，用 `leiden`

```json
{
  "partition_method": "leiden",
  "leiden_max_size": 10,
  "mode": "aggregated"
}
```

解释：

- 先做社区发现
- 再把过大的社区切到最多 10 个节点
- 条数受图结构影响，比 `bfs` 更不线性

### 例 4：社区数不变，直接放大样本量

```json
{
  "partition_method": "bfs",
  "bfs_max_units": 5,
  "mode": "multi_choice",
  "num_of_questions": 5
}
```

解释：

- 假设最后切出 100 个社区
- 理论上大约得到 `100 × 5 = 500` 条

## 实操建议

如果你的目标只是“把条数控制在一个范围内”，推荐优先级如下：

1. `bfs + aggregated`
2. `dfs + aggregated`
3. `ece + aggregated`
4. `leiden + aggregated`
5. 在社区数稳定后，再切换到多题模式放大

原因很简单：

- `bfs/dfs` 的条数控制最直接
- `ece/leiden` 的社区质量通常更好，但条数更难精确预测

## 常见误区

### 误区 1：只调分区，不看生成模式

如果你把 `mode` 换成 `multi_choice`、`multi_answer`、`fill_in_blank`、`true_false`，总条数会被 `num_of_questions` 再乘一遍。

### 误区 2：把 `max_units` 理解成“节点数”

在 `bfs`、`dfs`、`ece` 里，unit 不是纯节点数，而是：

- 节点
- 边

所以一个 `max_units_per_community=10` 的社区，不一定等于 10 个节点。

### 误区 3：想用 `leiden` 精确控条数

`leiden` 更适合做结构化社区发现，不适合做最线性的条数控制。

### 误区 4：忽略模型解析失败

理论条数不等于实际条数。模型输出格式不合规时，样本会被丢弃。

## 最后给一个简单选择表

| 目标 | 推荐方案 |
|---|---|
| 最容易控条数 | `bfs + aggregated` |
| 想保留路径感 | `dfs + aggregated` |
| 想兼顾内容密度 | `ece + aggregated` |
| 想做图社区发现 | `leiden + aggregated` |
| 图太小但还想放大量 | 保持分区不变，改多题模式并调 `num_of_questions` |

