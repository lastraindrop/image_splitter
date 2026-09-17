"""NodeGraph evaluation engine and LRU evaluation cache.

Provides :class:`NodeGraph` to manage a DAG of nodes and evaluate them in
topological order, and :class:`EvaluationCache` for caching computed images
keyed by ``(node_name, node_version)``.
"""

from __future__ import annotations

from collections import deque
from typing import Optional

from PIL import Image

from image_splitter.engine.nodes import BaseNode, Connection


# ---------------------------------------------------------------------------
# NodeGraph
# ---------------------------------------------------------------------------

class NodeGraph:
    """Directed acyclic graph of processing nodes.

    Manages node registration, connections between them, and lazy (dirty-
    propagation) or forced evaluation.
    """

    def __init__(self) -> None:
        self.nodes: dict[str, BaseNode] = {}
        self.connections: list[Connection] = []

    # -- node management ----------------------------------------------------

    def add_node(self, node: BaseNode) -> None:
        """Register a node in the graph (keyed by ``node.name``)."""
        self.nodes[node.name] = node

    def remove_node(self, name: str) -> None:
        """Remove a node and all connections touching it."""
        if name not in self.nodes:
            return
        # Remove connections involving this node
        self.connections = [
            c for c in self.connections
            if c.from_socket.node.name != name and c.to_socket.node.name != name
        ]
        del self.nodes[name]

    # -- connection management ----------------------------------------------

    def connect(
        self,
        from_node: str,
        from_socket: str,
        to_node: str,
        to_socket: str,
    ) -> Connection:
        """Create a connection between two named node sockets.

        Returns:
            The new :class:`Connection`.

        Raises:
            KeyError: If a node or socket name is not found.
            ValueError / TypeError: Propagated from :class:`Connection`.
        """
        src_node = self.nodes[from_node]
        dst_node = self.nodes[to_node]
        src_sock = src_node.outputs[from_socket]
        dst_sock = dst_node.inputs[to_socket]

        conn = Connection(from_socket=src_sock, to_socket=dst_sock)
        src_sock.connections.append(conn)
        dst_sock.connections.append(conn)
        self.connections.append(conn)

        # Destination becomes dirty when wired to a new source
        dst_node.mark_dirty()
        return conn

    def disconnect(
        self,
        from_node: str,
        from_socket: str,
        to_node: str,
        to_socket: str,
    ) -> bool:
        """Remove a specific connection. Returns ``True`` if found and removed."""
        src_node = self.nodes.get(from_node)
        dst_node = self.nodes.get(to_node)
        if src_node is None or dst_node is None:
            return False

        src_sock = src_node.outputs.get(from_socket)
        dst_sock = dst_node.inputs.get(to_socket)
        if src_sock is None or dst_sock is None:
            return False

        for i, conn in enumerate(self.connections):
            if (
                conn.from_socket is src_sock
                and conn.to_socket is dst_sock
            ):
                src_sock.connections.remove(conn)
                dst_sock.connections.remove(conn)
                self.connections.pop(i)
                dst_node.mark_dirty()
                return True
        return False

    # -- topological sort (Kahn's algorithm) --------------------------------

    def _topological_order(self) -> list[BaseNode]:
        """Return nodes in evaluation order.

        Raises:
            ValueError: If the graph contains a cycle.
        """
        in_degree: dict[str, int] = {name: 0 for name in self.nodes}

        # Build adjacency list: src_node -> [dst_node, ...]
        adj: dict[str, list[str]] = {name: [] for name in self.nodes}
        for conn in self.connections:
            src = conn.from_socket.node.name
            dst = conn.to_socket.node.name
            adj.setdefault(src, []).append(dst)
            in_degree[dst] = in_degree.get(dst, 0) + 1

        queue: deque[str] = deque(
            name for name, deg in in_degree.items() if deg == 0
        )
        order: list[BaseNode] = []

        while queue:
            name = queue.popleft()
            order.append(self.nodes[name])
            for neighbour in adj.get(name, []):
                in_degree[neighbour] -= 1
                if in_degree[neighbour] == 0:
                    queue.append(neighbour)

        if len(order) != len(self.nodes):
            remaining = set(self.nodes) - {n.name for n in order}
            raise ValueError(
                f"Cycle detected in node graph involving: {', '.join(sorted(remaining))}"
            )

        return order

    # -- dirty propagation --------------------------------------------------

    def _propagate_dirty(self) -> set[str]:
        """BFS from every dirty node, marking downstream nodes dirty too.

        Returns:
            Set of node names that are now dirty.
        """
        dirty_names: set[str] = {
            name for name, node in self.nodes.items() if node.is_dirty
        }

        # Build forward adjacency from connections
        forward: dict[str, set[str]] = {name: set() for name in self.nodes}
        for conn in self.connections:
            forward[conn.from_socket.node.name].add(conn.to_socket.node.name)

        visited: set[str] = set(dirty_names)
        queue: deque[str] = deque(dirty_names)

        while queue:
            current = queue.popleft()
            for neighbour in forward.get(current, set()):
                if neighbour not in visited:
                    visited.add(neighbour)
                    self.nodes[neighbour].mark_dirty()
                    queue.append(neighbour)

        return visited

    # -- evaluation ---------------------------------------------------------

    def evaluate(self, force_all: bool = False) -> dict[str, bool]:
        """Evaluate dirty nodes in topological order.

        Args:
            force_all: If ``True``, every node is re-evaluated regardless
                of its dirty state.

        Returns:
            A dict mapping ``node_name`` → ``was_evaluated``.
        """
        # 1. Mark all dirty if forced
        if force_all:
            for node in self.nodes.values():
                node.mark_dirty()

        # 2. Propagate dirty flags downstream
        self._propagate_dirty()

        # 3. Topological sort
        ordered = self._topological_order()

        # 4. Evaluate each dirty node in order
        evaluated: dict[str, bool] = {}
        for node in ordered:
            if not node.is_dirty:
                evaluated[node.name] = False
                continue

            # Copy upstream socket values via connections into node inputs
            for sock in node.inputs.values():
                # Reset input value — will be overwritten by connected output
                sock.value = None
                for conn in sock.connections:
                    sock.value = conn.from_socket.value

            node.evaluate()
            node.mark_clean()
            evaluated[node.name] = True

        return evaluated


# ---------------------------------------------------------------------------
# EvaluationCache
# ---------------------------------------------------------------------------

class EvaluationCache:
    """Simple LRU cache for computed node output images.

    Entries are keyed by ``(node_name, node_version)``.  When the cache
    exceeds *max_entries* the oldest (least-recently-used) entry is evicted.
    """

    def __init__(self, max_entries: int = 50) -> None:
        self._max_entries: int = max_entries
        # OrderedDict preserves insertion order; we move accessed items to end
        from collections import OrderedDict
        self._store: OrderedDict[tuple[str, int], Image.Image] = OrderedDict()

    def get(self, node_name: str, version: int) -> Optional[Image.Image]:
        """Retrieve a cached image, or ``None`` if absent.

        A successful lookup promotes the entry to most-recently-used.
        """
        key = (node_name, version)
        if key in self._store:
            self._store.move_to_end(key)
            return self._store[key]
        return None

    def put(self, node_name: str, version: int, image: Image.Image) -> None:
        """Store an image, evicting the LRU entry if the cache is full."""
        key = (node_name, version)
        if key in self._store:
            self._store.move_to_end(key)
            self._store[key] = image
            return
        if len(self._store) >= self._max_entries:
            # P1-11: Close evicted image to prevent resource leaks.
            _, old_img = self._store.popitem(last=False)
            try:
                old_img.close()
            except Exception:
                pass
        self._store[key] = image

    def invalidate(self, node_name: str) -> None:
        """Remove all cache entries for a given node name.

        V16 (L-6): evicted images are closed, matching the eviction
        path in :meth:`put`.
        """
        keys_to_remove = [k for k in self._store if k[0] == node_name]
        for key in keys_to_remove:
            img = self._store.pop(key)
            try:
                img.close()
            except Exception:
                pass

    def clear(self) -> None:
        """Remove all entries from the cache (closing held images)."""
        while self._store:
            _, img = self._store.popitem()
            try:
                img.close()
            except Exception:
                pass

    def __len__(self) -> int:
        return len(self._store)

    def __repr__(self) -> str:
        return f"EvaluationCache(entries={len(self._store)}, max={self._max_entries})"
