"use client";

import { memo, useEffect, useMemo } from "react";
import {
  Background,
  Controls,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  type Node,
  type Edge,
  useNodesState,
  useEdgesState,
  useReactFlow,
  ReactFlowProvider,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import dagre from "dagre";
import type { TreeEdge, TreeNode } from "@/lib/types";

const NODE_WIDTH = 220;
const NODE_HEIGHT = 56;

type ChunkNodeData = {
  label: string;
  is_completed: boolean;
};

function ChunkNode({ data }: { data: ChunkNodeData }) {
  return (
    <div
      className={`rounded-lg border px-3 py-2 shadow-md transition-all duration-200 cursor-pointer ${
        data.is_completed
          ? "border-gold bg-gold/10 shadow-gold"
          : "border-border-gold bg-surface hover:border-gold/60 hover:shadow-gold"
      }`}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!bg-gold !border-gold/50 !w-2 !h-2"
      />
      <div className="flex items-center gap-2">
        {data.is_completed && (
          <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-gold-gradient text-xs text-void font-bold">
            ✓
          </span>
        )}
        <span
          className={`text-xs font-medium leading-tight ${
            data.is_completed ? "text-gold-light" : "text-cream"
          }`}
        >
          {data.label}
        </span>
      </div>
      <Handle
        type="source"
        position={Position.Bottom}
        className="!bg-gold !border-gold/50 !w-2 !h-2"
      />
    </div>
  );
}

const nodeTypes = { chunk: memo(ChunkNode) };

function layoutElements(
  nodes: TreeNode[],
  edges: TreeEdge[]
): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "TB", nodesep: 40, ranksep: 70 });

  nodes.forEach((n) => {
    g.setNode(n.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  });
  edges.forEach((e) => {
    g.setEdge(e.source, e.target);
  });

  dagre.layout(g);

  const flowNodes: Node[] = nodes.map((n) => {
    const pos = g.node(n.id);
    return {
      id: n.id,
      type: "chunk",
      position: {
        x: pos.x - NODE_WIDTH / 2,
        y: pos.y - NODE_HEIGHT / 2,
      },
      data: { label: n.heading, is_completed: n.is_completed },
    };
  });

  const flowEdges: Edge[] = edges.map((e, i) => ({
    id: `e-${i}`,
    source: e.source,
    target: e.target,
    animated: false,
    style: { stroke: "#6b5c3e", strokeWidth: 1.5 },
  }));

  return { nodes: flowNodes, edges: flowEdges };
}

function TreeCanvasInner({
  treeNodes,
  treeEdges,
  onNodeClick,
}: {
  treeNodes: TreeNode[];
  treeEdges: TreeEdge[];
  onNodeClick: (nodeId: string) => void;
}) {
  const { fitView } = useReactFlow();
  const layout = useMemo(
    () => layoutElements(treeNodes, treeEdges),
    [treeNodes, treeEdges]
  );
  const [nodes, setNodes, onNodesChange] = useNodesState(layout.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(layout.edges);

  useEffect(() => {
    setNodes(layout.nodes);
    setEdges(layout.edges);
    setTimeout(() => fitView({ padding: 0.2 }), 50);
  }, [layout, setNodes, setEdges, fitView]);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      nodeTypes={nodeTypes}
      onNodeClick={(_, node) => onNodeClick(node.id)}
      fitView
      minZoom={0.3}
      maxZoom={1.5}
      proOptions={{ hideAttribution: true }}
    >
      <Background color="#2a2418" gap={24} size={1} />
      <Controls />
      <MiniMap
        nodeColor="#c9a227"
        maskColor="rgba(5,5,5,0.85)"
        style={{ background: "#161616" }}
      />
    </ReactFlow>
  );
}

export default function TreeCanvas(props: {
  treeNodes: TreeNode[];
  treeEdges: TreeEdge[];
  onNodeClick: (nodeId: string) => void;
}) {
  return (
    <div className="h-full w-full bg-canvas">
      <ReactFlowProvider>
        <TreeCanvasInner {...props} />
      </ReactFlowProvider>
    </div>
  );
}
