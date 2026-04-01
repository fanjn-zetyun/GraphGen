# entrypoint.sh 修复记录

## 目标

修复 `entrypoint.sh` 执行时报错、卡住、超时的问题，并确保最终可以正常生成数据集文件。

---

## 实际排查过程

### 1. 先确认入口脚本是否能正常启动

检查了 [entrypoint.sh](/app/entrypoint.sh)、[yaml_builder.py](/app/yaml_builder.py)、[graphgen/run.py](/app/graphgen/run.py)、[graphgen/engine.py](/app/graphgen/engine.py) 以及容器内现有运行参数。

初步发现：

- `entrypoint.sh` 已经不是原始版本，里面有自定义的日志、Ray 清理和输出文件搬运逻辑。
- 但参数字段名已经和仓库里的旧调用方式不一致。
- 当前环境里的 `GRAPHGEN_PARAMS` 用的是：
  - `model_name`
  - `base_url`
  - `file_path_input`
  - `export_path`
- 而仓库内很多旧逻辑和测试脚本仍然在用：
  - `synthesizer_model`
  - `synthesizer_url`
  - `upload_file`

这会导致入口脚本和配置构建脚本在不同调用来源下表现不一致。

---

## 修复内容

### 修复 1：兼容新旧两套参数命名

修改文件：

- [entrypoint.sh](/app/entrypoint.sh)
- [yaml_builder.py](/app/yaml_builder.py)

处理内容：

- 支持同时读取以下两套字段别名：
  - `model_name` / `synthesizer_model`
  - `base_url` / `synthesizer_url`
  - `file_path_input` / `upload_file`
  - `export_path` / `final_output_path`
- 如果没有传 `export_path`，自动回退到默认输出目录：
  - `/workspace/user-data/datasets/graphgen_output`

结果：

- 当前环境传入的 `GRAPHGEN_PARAMS` 可以直接被识别。
- 旧脚本调用方式也不会因为字段名变化直接报错。

---

### 修复 2：修正 `eval` 导出环境变量的脆弱写法

修改文件：

- [entrypoint.sh](/app/entrypoint.sh)

问题：

- 原先入口脚本用 Python 打印 `export XXX=...` 后直接 `eval`。
- 如果 `api_key`、URL 或其他参数中包含 `$`、空格、特殊字符，shell 解析可能出错。

处理内容：

- 改成使用 `shlex.quote()` 生成 shell-safe 的导出语句。

结果：

- 参数中包含特殊字符时不会再破坏 shell 环境。

---

### 修复 3：给 Ray 清理过程加超时保护

修改文件：

- [entrypoint.sh](/app/entrypoint.sh)

问题：

- `ray stop --force` 在异常状态下可能卡住，导致入口脚本看起来像“超时”。

处理内容：

- 如果系统存在 `timeout` 命令，则使用：

```bash
timeout 20s ray stop --force
```

- 否则保持原来的兜底行为。

结果：

- 即使 Ray 残留状态异常，也不会无限阻塞入口脚本。

---

### 修复 4：关闭 Ray dashboard，减少容器内启动等待

修改文件：

- [graphgen/engine.py](/app/graphgen/engine.py)

问题：

- Ray dashboard 对批量数据生成没有必要。
- 在容器环境中它可能增加额外启动时间和不确定性。

处理内容：

- 将 `ray.init(include_dashboard=True)` 改为 `include_dashboard=False`。

结果：

- 启动更稳，更适合当前容器批处理场景。

---

### 修复 5：定位并绕开 RocksDB 在 Ray worker 中的崩溃

修改文件：

- [yaml_builder.py](/app/yaml_builder.py)

实际运行时发现：

- `entrypoint.sh` 能启动并进入主流程。
- 但第一次完整执行时，在 `read` 节点里创建 `KVStorageActor` 时出现 `SIGSEGV`。
- 崩溃点来自 `rocksdb` 后端，即 `rocksdict` 在 Ray worker 中直接崩溃。

错误现象：

- `KVStorageActor` 异常退出
- `ActorDiedError`
- worker 级别 `SIGSEGV`

处理内容：

- 入口生成的配置默认把：

```yaml
kv_backend: rocksdb
```

改为：

```yaml
kv_backend: json_kv
```

- 同时保留参数覆盖能力，如果后续外部明确传 `kv_backend` 仍可覆盖。

结果：

- 避开了 `rocksdict` 的原生扩展崩溃点。
- 流程可以稳定跑完整个生成链路。

---

## 验证过程

### 静态校验

执行过以下检查：

```bash
bash -n /app/entrypoint.sh
python3 -m py_compile /app/yaml_builder.py /app/graphgen/engine.py /app/graphgen/run.py
```

均通过。

---

### 参数兼容性验证

使用旧风格参数执行 `yaml_builder.py`，确认能够正常生成 `/tmp/graphgen_config.yaml`，并正确映射：

- 输入路径
- 输出路径
- 模型配置
- 生成模式

---

### 端到端运行验证

直接执行：

```bash
bash /app/entrypoint.sh
```

第一次运行结果：

- 配置生成成功
- `graphgen.run` 成功启动
- 在 `rocksdb` 存储 actor 处崩溃

修复 `kv_backend=json_kv` 后再次执行：

- `read` 成功
- `chunk` 成功
- `build_kg` 成功
- `partition` 成功
- `generate` 成功
- 输出文件合并成功
- `entrypoint.sh` 最终退出码为 `0`

---

## 最终产物

成功生成的数据集文件：

- [12313.jsonl](/workspace/user-data/dataset/12313/12313.jsonl)

文件校验结果：

- 文件存在
- 非空
- 内容为标准的 `instruction` / `input` / `output` 结构

示例首行内容已验证为有效 JSONL 记录。

---

## 本次实际修改的文件

- [entrypoint.sh](/app/entrypoint.sh)
- [yaml_builder.py](/app/yaml_builder.py)
- [graphgen/engine.py](/app/graphgen/engine.py)

---

## 最终结论

这次“执行 `entrypoint.sh` 报错、超时、无法生成数据集”的问题，实际由多层问题叠加导致：

1. 参数字段命名不兼容
2. shell `eval` 对特殊字符不安全
3. Ray 清理可能卡住
4. RocksDB 后端在 Ray worker 中发生 `SIGSEGV`

修复后，当前环境已经可以成功执行 `entrypoint.sh` 并生成目标数据集文件。