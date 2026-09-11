"""A small, explicit, deterministic state-graph engine (FR-9 AC1).

This is the LangGraph swap point: the PRD's primary choice is LangGraph
(§11.2), but the v1 core must run with zero heavyweight dependencies, so the
orchestrator is expressed against this minimal engine with the same semantics
(nodes, conditional fan-out from a router, shared typed state, full trace).
`backend/agents/graph_langgraph.py`-style adapters can replace `run()` without
touching node functions. Every node execution is inspectable and logged.
"""
from __future__ import annotations

END = "__end__"


class Graph:
    def __init__(self, name: str):
        self.name = name
        self.nodes: dict[str, callable] = {}
        self._entry: str | None = None
        self._edges: dict[str, str] = {}          # node -> single next node
        self._routers: dict[str, callable] = {}   # node -> fn(state) -> list[str]

    def add_node(self, name: str, fn: callable) -> "Graph":
        self.nodes[name] = fn
        return self

    def set_entry(self, name: str) -> "Graph":
        self._entry = name
        return self

    def add_edge(self, a: str, b: str) -> "Graph":
        self._edges[a] = b
        return self

    def add_router(self, node: str, fn: callable) -> "Graph":
        """fn(state) -> ordered list of node names to execute next (may be empty → END)."""
        self._routers[node] = fn
        return self

    def route(self, node: str, state: dict) -> list[str]:
        if node in self._routers:
            return list(self._routers[node](state))
        if node in self._edges:
            return [self._edges[node]]
        return []

    def run(self, state: dict, trace=None) -> dict:
        """Execute from the entry node, following routers deterministically.

        Level-order: all nodes of the current level (a router's fanned-out
        specialists) complete before any of their successors (the join node)
        runs. Duplicate successors are executed once. Each node mutates the
        shared state (LangGraph-style) and appends its own trace events.
        """
        if not self._entry:
            raise ValueError("graph has no entry node")
        level: list[str] = [self._entry]
        steps = 0
        while level:
            steps += 1
            if steps > 64:
                raise RuntimeError("orchestrator graph exceeded 64 levels (cycle?)")
            next_level: list[str] = []
            for node in level:
                if node == END:
                    continue
                fn = self.nodes.get(node)
                if fn is None:
                    raise KeyError(f"unknown graph node: {node}")
                fn(state)  # nodes append their own trace events
                for nxt in self.route(node, state):
                    if nxt != END and nxt not in next_level:
                        next_level.append(nxt)
            level = next_level
        return state
