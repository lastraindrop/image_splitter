"""Unit tests for Node Graph + Evaluator (engine/nodes.py + engine/evaluator.py)."""

import pytest

from image_splitter.engine.data_blocks import ImageDataBlock
from image_splitter.engine.evaluator import EvaluationCache, NodeGraph
from image_splitter.engine.nodes import (
    BlendNode,
    ColorAdjustNode,
    Connection,
    ImageInputNode,
    ImageOutputNode,
    Socket,
    SocketType,
)
from .conftest import make_rgb_image


# ---------------------------------------------------------------------------
# SocketType
# ---------------------------------------------------------------------------

def test_sockettype_values():
    """SocketType enum has IMAGE, MASK, VALUE, COLOR members."""
    assert SocketType.IMAGE is not None
    assert SocketType.MASK is not None
    assert SocketType.VALUE is not None
    assert SocketType.COLOR is not None


# ---------------------------------------------------------------------------
# Socket
# ---------------------------------------------------------------------------

def test_socket_creation():
    """Socket stores name, type, direction, and node reference."""
    node = ImageInputNode("test")
    sock = Socket("my_socket", SocketType.IMAGE, is_output=True, node=node)
    assert sock.name == "my_socket"
    assert sock.socket_type == SocketType.IMAGE
    assert sock.is_output is True
    assert sock.node is node
    assert sock.value is None


def test_socket_value_get_set():
    """Socket value property stores and retrieves values."""
    node = ImageInputNode("test")
    sock = Socket("s", SocketType.IMAGE, is_output=True, node=node)
    sock.value = 42
    assert sock.value == 42


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def test_connection_valid():
    """Connection links output → input of same type."""
    node_a = ImageInputNode("a")
    node_b = ImageInputNode("b")  # only for socket creation
    src = Socket("out", SocketType.IMAGE, is_output=True, node=node_a)
    dst = Socket("in", SocketType.IMAGE, is_output=False, node=node_b)
    conn = Connection(from_socket=src, to_socket=dst)
    assert conn.from_socket is src
    assert conn.to_socket is dst


def test_connection_type_mismatch():
    """Connection raises TypeError when socket types don't match."""
    node_a = ImageInputNode("a")
    node_b = ImageInputNode("b")
    src = Socket("out", SocketType.IMAGE, is_output=True, node=node_a)
    dst = Socket("in", SocketType.VALUE, is_output=False, node=node_b)
    with pytest.raises(TypeError):
        Connection(from_socket=src, to_socket=dst)


def test_connection_same_direction():
    """Connection raises ValueError when both sockets are outputs."""
    node = ImageInputNode("n")
    src = Socket("a", SocketType.IMAGE, is_output=True, node=node)
    dst = Socket("b", SocketType.IMAGE, is_output=True, node=node)
    with pytest.raises(ValueError):
        Connection(from_socket=src, to_socket=dst)


# ---------------------------------------------------------------------------
# BaseNode – properties & dirty tracking
# ---------------------------------------------------------------------------

def test_basenode_init():
    """BaseNode subclass initializes with name, empty sockets, dirty=True."""
    node = ImageInputNode("in1")
    assert node.name == "in1"
    assert node.is_dirty is True
    assert node._version == 0


def test_get_set_prop():
    """get_prop / set_prop store and retrieve node properties."""
    node = ImageInputNode("n")
    assert node.get_prop("source") is None
    node.set_prop("source", "my_block")
    assert node.get_prop("source") == "my_block"


def test_get_prop_default():
    """get_prop returns the default when key is not set."""
    node = ImageInputNode("n")
    assert node.get_prop("missing", "fallback") == "fallback"


def test_set_prop_marks_dirty():
    """set_prop marks node dirty when value changes."""
    node = ImageInputNode("n")
    node.mark_clean()
    assert not node.is_dirty
    node.set_prop("source", "block1")
    assert node.is_dirty


def test_set_prop_same_value_not_dirty():
    """set_prop does NOT mark dirty when value unchanged."""
    node = ImageInputNode("n")
    node.set_prop("source", "block1")
    node.mark_clean()
    node.set_prop("source", "block1")  # same value
    assert not node.is_dirty


def test_mark_clean():
    """mark_clean clears the dirty flag."""
    node = ImageInputNode("n")
    assert node.is_dirty
    node.mark_clean()
    assert not node.is_dirty


def test_version_increment():
    """Version increments each time the node is marked dirty (only when not already dirty)."""
    node = ImageInputNode("n")
    assert node._version == 0
    node.set_prop("source", "b1")  # marks dirty
    v1 = node._version  # might have incremented
    node.mark_clean()
    node.set_prop("source", "b2")  # marks dirty again
    assert node._version > v1


def test_input_output_sockets():
    """ImageInputNode has one output socket; ImageOutputNode has one input."""
    in_node = ImageInputNode("in")
    out_node = ImageOutputNode("out")

    assert "image" in in_node.outputs
    assert len(in_node.inputs) == 0

    assert "image" in out_node.inputs
    assert len(out_node.outputs) == 0


# ---------------------------------------------------------------------------
# Concrete nodes – integration
# ---------------------------------------------------------------------------

class TestConcreteNodes:
    """Tests that exercise concrete node evaluation end-to-end."""

    def test_image_input_node(self):
        """ImageInputNode reads from a named ImageDataBlock."""
        ImageDataBlock(name="src", image=make_rgb_image(color=(0, 0, 255)))
        node = ImageInputNode("reader")
        node.set_prop("source", "src")
        node.evaluate()
        result = node.outputs["image"].value
        assert result is not None
        assert result.size == (100, 100)

        ImageDataBlock.clear_all()

    def test_image_input_node_missing_source(self):
        """ImageInputNode outputs None when source data block doesn't exist."""
        node = ImageInputNode("reader")
        node.set_prop("source", "nonexistent")
        node.evaluate()
        assert node.outputs["image"].value is None

    def test_image_output_node(self):
        """ImageOutputNode writes to a named ImageDataBlock."""
        ImageDataBlock(name="dst")
        node = ImageOutputNode("writer")
        node.set_prop("target", "dst")
        node.inputs["image"].value = make_rgb_image(color=(255, 0, 0))
        node.evaluate()

        result = ImageDataBlock.get_by_name("dst")
        assert result is not None
        assert result.is_loaded

        ImageDataBlock.clear_all()

    def test_color_adjust_node(self):
        """ColorAdjustNode passes through when all props are default (1.0)."""
        node = ColorAdjustNode("adjust")
        node.inputs["image"].value = make_rgb_image()
        node.evaluate()
        assert node.outputs["image"].value is not None
        assert node.outputs["image"].value.size == (100, 100)

    def test_blend_node(self):
        """BlendNode blends two images."""
        node = BlendNode("blender")
        node.inputs["image_a"].value = make_rgb_image(color=(255, 0, 0))
        node.inputs["image_b"].value = make_rgb_image(color=(0, 0, 255))
        node.set_prop("opacity", 0.5)
        node.evaluate()
        assert node.outputs["image"].value is not None


# ---------------------------------------------------------------------------
# NodeGraph – add / remove / connect
# ---------------------------------------------------------------------------

class TestNodeGraphBasic:
    """Tests for NodeGraph node and connection management."""

    def test_add_node(self):
        graph = NodeGraph()
        node = ImageInputNode("n1")
        graph.add_node(node)
        assert "n1" in graph.nodes

    def test_remove_node(self):
        graph = NodeGraph()
        n1 = ImageInputNode("n1")
        n2 = ImageInputNode("n2")
        graph.add_node(n1)
        graph.add_node(n2)
        graph.remove_node("n1")
        assert "n1" not in graph.nodes
        assert "n2" in graph.nodes

    def test_connect_valid(self):
        graph = NodeGraph()
        n1 = ColorAdjustNode("adjust")
        n2 = ImageOutputNode("out")
        graph.add_node(n1)
        graph.add_node(n2)
        conn = graph.connect("adjust", "image", "out", "image")
        assert len(graph.connections) == 1
        assert conn.from_socket.node.name == "adjust"
        assert conn.to_socket.node.name == "out"

    def test_connect_marks_dst_dirty(self):
        graph = NodeGraph()
        n1 = ColorAdjustNode("adjust")
        n2 = ImageOutputNode("out")
        graph.add_node(n1)
        graph.add_node(n2)
        n2.mark_clean()
        graph.connect("adjust", "image", "out", "image")
        assert n2.is_dirty

    def test_disconnect(self):
        graph = NodeGraph()
        n1 = ColorAdjustNode("a")
        n2 = ImageOutputNode("b")
        graph.add_node(n1)
        graph.add_node(n2)
        graph.connect("a", "image", "b", "image")
        assert len(graph.connections) == 1
        removed = graph.disconnect("a", "image", "b", "image")
        assert removed
        assert len(graph.connections) == 0


# ---------------------------------------------------------------------------
# Topological sort
# ---------------------------------------------------------------------------

def test_topological_order_linear():
    """Linear chain: A → B → C."""
    graph = NodeGraph()
    a = ColorAdjustNode("a")
    b = ColorAdjustNode("b")
    c = ImageOutputNode("c")
    c.set_prop("target", "__topo_test__")
    graph.add_node(a)
    graph.add_node(b)
    graph.add_node(c)
    graph.connect("a", "image", "b", "image")
    graph.connect("b", "image", "c", "image")

    order = graph._topological_order()
    names = [n.name for n in order]
    assert names.index("a") < names.index("b") < names.index("c")

    ImageDataBlock.clear_all()


def test_topological_order_diamond():
    """Diamond: A → B → D and A → C → D."""
    graph = NodeGraph()
    a = ColorAdjustNode("a")
    b = ColorAdjustNode("b")
    c = ColorAdjustNode("c")
    d = BlendNode("d")
    graph.add_node(a)
    graph.add_node(b)
    graph.add_node(c)
    graph.add_node(d)
    graph.connect("a", "image", "b", "image")
    graph.connect("a", "image", "c", "image")
    graph.connect("b", "image", "d", "image_a")
    graph.connect("c", "image", "d", "image_b")

    order = graph._topological_order()
    names = [n.name for n in order]
    assert names.index("a") < names.index("b")
    assert names.index("a") < names.index("c")
    assert names.index("b") < names.index("d")
    assert names.index("c") < names.index("d")


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def test_evaluate_force_all():
    """force_all=True evaluates every node."""
    ImageDataBlock(name="eval_in", image=make_rgb_image())
    graph = NodeGraph()

    inp = ImageInputNode("inp")
    inp.set_prop("source", "eval_in")
    adj = ColorAdjustNode("adj")
    out = ImageOutputNode("outp")
    out.set_prop("target", "eval_out")

    graph.add_node(inp)
    graph.add_node(adj)
    graph.add_node(out)
    graph.connect("inp", "image", "adj", "image")
    graph.connect("adj", "image", "outp", "image")

    result = graph.evaluate(force_all=True)
    assert result["inp"] is True
    assert result["adj"] is True
    assert result["outp"] is True

    output_block = ImageDataBlock.get_by_name("eval_out")
    assert output_block is not None
    assert output_block.is_loaded

    ImageDataBlock.clear_all()


def test_evaluate_only_dirty():
    """force_all=False only evaluates dirty nodes."""
    ImageDataBlock(name="dirty_in", image=make_rgb_image())
    graph = NodeGraph()

    inp = ImageInputNode("inp")
    inp.set_prop("source", "dirty_in")
    adj = ColorAdjustNode("adj")
    out = ImageOutputNode("outp")
    out.set_prop("target", "dirty_out")

    graph.add_node(inp)
    graph.add_node(adj)
    graph.add_node(out)
    graph.connect("inp", "image", "adj", "image")
    graph.connect("adj", "image", "outp", "image")

    # Mark everything clean except adj
    inp.mark_clean()
    adj.mark_dirty()  # already dirty from init, but be explicit
    out.mark_clean()

    result = graph.evaluate(force_all=False)
    assert result["inp"] is False  # clean, not evaluated
    assert result["adj"] is True  # dirty, evaluated
    # out was marked dirty by dirty propagation from adj (connected upstream)
    assert result["outp"] is True

    ImageDataBlock.clear_all()


def test_dirty_propagation():
    """Changing a node prop dirties downstream nodes."""
    ImageDataBlock(name="prop_in", image=make_rgb_image())
    graph = NodeGraph()

    inp = ImageInputNode("inp")
    inp.set_prop("source", "prop_in")
    adj = ColorAdjustNode("adj")
    out = ImageOutputNode("outp")
    out.set_prop("target", "prop_out")

    graph.add_node(inp)
    graph.add_node(adj)
    graph.add_node(out)
    graph.connect("inp", "image", "adj", "image")
    graph.connect("adj", "image", "outp", "image")

    # Evaluate once to clean everything
    graph.evaluate(force_all=True)
    assert not adj.is_dirty
    assert not out.is_dirty

    # Change a prop on adj → should dirty adj AND out
    adj.set_prop("brightness", 1.5)
    assert adj.is_dirty

    graph._propagate_dirty()
    assert out.is_dirty  # downstream of adj

    ImageDataBlock.clear_all()


# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------

def test_cycle_detection():
    """Graph with a cycle raises ValueError in topological sort."""
    graph = NodeGraph()
    a = ColorAdjustNode("a")
    b = ColorAdjustNode("b")
    graph.add_node(a)
    graph.add_node(b)
    graph.connect("a", "image", "b", "image")
    graph.connect("b", "image", "a", "image")

    with pytest.raises(ValueError, match="Cycle"):
        graph._topological_order()


# ---------------------------------------------------------------------------
# EvaluationCache
# ---------------------------------------------------------------------------

class TestEvaluationCache:
    """Tests for the LRU evaluation cache."""

    def test_put_and_get(self):
        cache = EvaluationCache(max_entries=10)
        img = make_rgb_image()
        cache.put("node1", 1, img)
        result = cache.get("node1", 1)
        assert result is img

    def test_get_missing(self):
        cache = EvaluationCache()
        assert cache.get("nope", 0) is None

    def test_version_key(self):
        """Different versions are different cache entries."""
        cache = EvaluationCache()
        img1 = make_rgb_image(color=(255, 0, 0))
        img2 = make_rgb_image(color=(0, 255, 0))
        cache.put("n", 1, img1)
        cache.put("n", 2, img2)
        assert cache.get("n", 1) is img1
        assert cache.get("n", 2) is img2

    def test_lru_eviction(self):
        """Oldest entry is evicted when cache exceeds max_entries."""
        cache = EvaluationCache(max_entries=3)
        for i in range(4):
            cache.put("n", i, make_rgb_image())
        assert len(cache) == 3
        # Version 0 should be evicted (oldest)
        assert cache.get("n", 0) is None
        assert cache.get("n", 3) is not None

    def test_invalidate(self):
        """invalidate removes all entries for a given node name."""
        cache = EvaluationCache()
        cache.put("a", 1, make_rgb_image())
        cache.put("a", 2, make_rgb_image())
        cache.put("b", 1, make_rgb_image())
        cache.invalidate("a")
        assert cache.get("a", 1) is None
        assert cache.get("a", 2) is None
        assert cache.get("b", 1) is not None

    def test_clear(self):
        """clear removes all entries."""
        cache = EvaluationCache()
        cache.put("x", 1, make_rgb_image())
        cache.put("y", 1, make_rgb_image())
        cache.clear()
        assert len(cache) == 0
        assert cache.get("x", 1) is None


class TestBranchingDAG:
    """Dirty propagation through branching (diamond) DAG topologies."""

    def test_branching_dirty_propagation(self):
        """When an upstream node goes dirty, ALL downstream branches
        should be marked dirty, not just one linear path."""
        from image_splitter.engine.nodes import (
            ColorAdjustNode, ImageInputNode, ImageOutputNode,
        )

        block = ImageDataBlock(name="branch_input", image=make_rgb_image(size=(20, 20)))

        graph = NodeGraph()
        inp = ImageInputNode("in")
        inp.set_prop("source", block.name)
        graph.add_node(inp)

        adj1 = ColorAdjustNode("adj1")
        adj2 = ColorAdjustNode("adj2")
        graph.add_node(adj1)
        graph.add_node(adj2)

        out1 = ImageOutputNode("out1")
        out1.set_prop("target", "branch_out1")
        out2 = ImageOutputNode("out2")
        out2.set_prop("target", "branch_out2")
        graph.add_node(out1)
        graph.add_node(out2)

        # in → adj1 → out1  (branch A)
        # in → adj2 → out2  (branch B)
        graph.connect("in", "image", "adj1", "image")
        graph.connect("in", "image", "adj2", "image")
        graph.connect("adj1", "image", "out1", "image")
        graph.connect("adj2", "image", "out2", "image")

        # Evaluate once
        result = graph.evaluate(force_all=True)
        assert result["in"] and result["adj1"] and result["adj2"]

        # Mark adj1 dirty — both adj1 AND out1 must be re-evaluated.
        # adj2 and out2 should remain clean.
        adj1.mark_dirty()
        result = graph.evaluate()
        assert result["adj1"], "adj1 must re-evaluate"
        assert result["out1"], "out1 (downstream of adj1) must re-evaluate"
        assert not result.get("adj2", True), "adj2 should stay clean"
        assert not result.get("out2", True), "out2 should stay clean"

        ImageDataBlock.clear_all()
