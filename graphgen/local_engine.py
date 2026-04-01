import inspect
import json
import os
from collections import defaultdict, deque
from typing import Any, Callable, Dict, List, Set

import pandas as pd

from graphgen.bases import Config, Node
from graphgen.common.init_llm import init_llm
from graphgen.common.init_storage import init_storage
from graphgen.local_read import local_read
from graphgen.utils import logger


class LocalEngine:
    def __init__(self, config: Dict[str, Any], functions: Dict[str, Callable]):
        self.config = Config(**config)
        self.global_params = self.config.global_params
        self.functions = functions
        self.datasets: Dict[str, pd.DataFrame] = {}
        self.llm_actors = {}
        self.storage_actors = {}

        self._init_llms()
        self._init_storage()

    def _init_llms(self):
        self.llm_actors["synthesizer"] = init_llm("synthesizer")
        self.llm_actors["trainee"] = init_llm("trainee")

    def _init_storage(self):
        kv_namespaces, graph_namespaces = self._scan_storage_requirements()
        working_dir = self.global_params["working_dir"]

        for node_id in kv_namespaces:
            self.storage_actors[f"kv_{node_id}"] = init_storage(
                self.global_params["kv_backend"], working_dir, node_id
            )

        for ns in graph_namespaces:
            self.storage_actors[f"graph_{ns}"] = init_storage(
                self.global_params["graph_backend"], working_dir, ns
            )

    def _scan_storage_requirements(self) -> tuple[set[str], set[str]]:
        kv_namespaces = set()
        graph_namespaces = set()

        for node in self.config.nodes:
            op_name = node.op_name
            if self._function_needs_param(op_name, "kv_backend"):
                kv_namespaces.add(op_name)
            if self._function_needs_param(op_name, "graph_backend"):
                graph_namespaces.add("graph")
        return kv_namespaces, graph_namespaces

    def _function_needs_param(self, op_name: str, param_name: str) -> bool:
        if op_name not in self.functions:
            return False

        func = self.functions[op_name]

        if inspect.isclass(func):
            try:
                sig = inspect.signature(func.__init__)
                return param_name in sig.parameters
            except (ValueError, TypeError):
                return False

        try:
            sig = inspect.signature(func)
            return param_name in sig.parameters
        except (ValueError, TypeError):
            return False

    @staticmethod
    def _topo_sort(nodes: List[Node]) -> List[Node]:
        id_to_node: Dict[str, Node] = {}
        for n in nodes:
            id_to_node[n.id] = n

        indeg: Dict[str, int] = {nid: 0 for nid in id_to_node}
        adj: Dict[str, List[str]] = defaultdict(list)

        for n in nodes:
            nid = n.id
            deps: List[str] = n.dependencies
            uniq_deps: Set[str] = set(deps)
            for d in uniq_deps:
                if d not in id_to_node:
                    raise ValueError(
                        f"The dependency node id {d} of node {nid} is not defined in the configuration."
                    )
                indeg[nid] += 1
                adj[d].append(nid)

        zero_deg: deque = deque(
            [id_to_node[nid] for nid, deg in indeg.items() if deg == 0]
        )
        sorted_nodes: List[Node] = []

        while zero_deg:
            cur = zero_deg.popleft()
            sorted_nodes.append(cur)
            cur_id = cur.id
            for nb_id in adj.get(cur_id, []):
                indeg[nb_id] -= 1
                if indeg[nb_id] == 0:
                    zero_deg.append(id_to_node[nb_id])

        if len(sorted_nodes) != len(nodes):
            remaining = [nid for nid, deg in indeg.items() if deg > 0]
            raise ValueError(
                f"The configuration contains cycles, unable to execute. Remaining nodes with indegree > 0: {remaining}"
            )

        return sorted_nodes

    def _filter_kwargs(
        self,
        func_or_class: Callable,
        global_params: Dict[str, Any],
        func_params: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            sig = inspect.signature(func_or_class)
        except ValueError:
            return {}

        params = sig.parameters
        final_kwargs = {}

        has_var_keywords = any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()
        )
        valid_keys = set(params.keys())
        for k, v in global_params.items():
            if k in valid_keys:
                final_kwargs[k] = v

        for k, v in func_params.items():
            if k in valid_keys or has_var_keywords:
                final_kwargs[k] = v
        return final_kwargs

    def _get_input_dataset(self, node: Node, initial_df: pd.DataFrame) -> pd.DataFrame:
        deps = node.dependencies

        if not deps:
            return initial_df.copy()

        if len(deps) == 1:
            return self.datasets[deps[0]].copy()

        frames = [self.datasets[d] for d in deps]
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)

    def _apply_operator(
        self,
        operator: Callable,
        input_df: pd.DataFrame,
        batch_size: Any,
        aggregate: bool = False,
    ) -> pd.DataFrame:
        if input_df.empty and not aggregate:
            return pd.DataFrame()

        if aggregate or batch_size in (None, "default"):
            batches = [input_df]
        else:
            size = int(batch_size)
            batches = [input_df.iloc[i : i + size] for i in range(0, len(input_df), size)]

        outputs = []
        for batch in batches:
            if batch.empty and not aggregate:
                continue
            for out in operator(batch.copy()):
                if out is not None and not out.empty:
                    outputs.append(out)

        if not outputs:
            return pd.DataFrame()

        return pd.concat(outputs, ignore_index=True)

    def _save_output(self, node: Node, output_dir: str):
        node_output_path = os.path.join(output_dir, node.id)
        os.makedirs(node_output_path, exist_ok=True)

        ds = self.datasets[node.id].copy()
        cols_to_drop = [c for c in ds.columns if c.startswith("_")]
        if cols_to_drop:
            ds = ds.drop(columns=cols_to_drop)

        output_file = os.path.join(node_output_path, f"{node.id}.jsonl")
        with open(output_file, "w", encoding="utf-8") as f:
            for row in ds.to_dict(orient="records"):
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

        logger.info("Node %s output saved to %s", node.id, output_file)

    def _execute_node(self, node: Node, initial_df: pd.DataFrame):
        if node.op_name not in self.functions:
            raise ValueError(f"Operator {node.op_name} not found for node {node.id}")

        op_handler = self.functions[node.op_name]
        node_params = self._filter_kwargs(op_handler, self.global_params, node.params or {})

        if node.type == "source":
            if node.op_name != "read":
                raise ValueError(
                    f"Local runtime currently only supports 'read' as a source operator, got {node.op_name}."
                )
            self.datasets[node.id] = local_read(**node_params)
            return

        input_df = self._get_input_dataset(node, initial_df)

        if inspect.isclass(op_handler):
            operator = op_handler(**node_params)
        else:
            raise ValueError(
                f"Local runtime expects operator classes for non-source nodes, got {node.op_name}."
            )

        execution_params = node.execution_params or {}
        batch_size = execution_params.get("batch_size", "default")
        self.datasets[node.id] = self._apply_operator(
            operator,
            input_df,
            batch_size=batch_size,
            aggregate=node.type == "aggregate",
        )

    def execute(
        self, initial_df: pd.DataFrame, output_dir: str
    ) -> Dict[str, pd.DataFrame]:
        sorted_nodes = self._topo_sort(self.config.nodes)

        for node in sorted_nodes:
            logger.info("Executing node %s of type %s", node.id, node.type)
            self._execute_node(node, initial_df)
            if getattr(node, "save_output", False):
                self._save_output(node, output_dir)

        return self.datasets
