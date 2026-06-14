"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import TreeCanvas from "@/components/TreeCanvas";
import AssessmentPanel from "@/components/AssessmentPanel";
import { fetchTree, generateAssessment } from "@/lib/api";
import type { GenerateAssessmentResponse, Step, TreeNode, TreeEdge } from "@/lib/types";

export default function SessionPage() {
  const params = useParams();
  const sessionId = params.id as string;

  const [treeNodes, setTreeNodes] = useState<TreeNode[]>([]);
  const [treeEdges, setTreeEdges] = useState<TreeEdge[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [assessmentData, setAssessmentData] =
    useState<GenerateAssessmentResponse | null>(null);
  const [step, setStep] = useState<Step>("idle");
  const [error, setError] = useState<string | null>(null);
  const [panelKey, setPanelKey] = useState(0);

  const loadTree = useCallback(async () => {
    const tree = await fetchTree(sessionId);
    setTreeNodes(tree.nodes);
    setTreeEdges(tree.edges);
  }, [sessionId]);

  useEffect(() => {
    loadTree().catch((err) => {
      const message = err instanceof Error ? err.message : "Failed to load tree";
      setError(
        message.includes("not found")
          ? "This session expired or the server restarted before sessions were saved. Upload the PDF again."
          : message
      );
    });
  }, [loadTree]);

  async function handleNodeClick(nodeId: string) {
    setSelectedNodeId(nodeId);
    setAssessmentData(null);
    setError(null);
    setStep("loading");
    setPanelKey((k) => k + 1);

    try {
      const data = await generateAssessment(sessionId, nodeId);
      setAssessmentData(data);
      setStep("mcq");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generation failed");
      setStep("error");
    }
  }

  function handleComplete(nodeId: string) {
    setTreeNodes((prev) =>
      prev.map((n) => (n.id === nodeId ? { ...n, is_completed: true } : n))
    );
  }

  return (
    <div className="flex flex-1 flex-col min-h-0 bg-void">
      <header className="flex items-center justify-between border-b border-border-gold bg-panel px-6 py-3 shadow-panel">
        <div className="flex items-center gap-3">
          <div className="h-7 w-7 rounded-full border border-gold/40 bg-gold/10 flex items-center justify-center">
            <span className="text-gold text-xs">◈</span>
          </div>
          <div>
            <h1 className="font-display text-base font-semibold text-cream">
              Learning Tree
            </h1>
            <p className="text-gold-muted text-xs">
              Session {sessionId.slice(0, 8)}…
            </p>
          </div>
        </div>
        <span className="rounded-full border border-border-gold bg-surface px-3 py-1 text-xs text-parchment">
          {treeNodes.length} nodes · click to assess
        </span>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <div className="flex-[3] border-r border-border-gold">
          <TreeCanvas
            treeNodes={treeNodes}
            treeEdges={treeEdges}
            onNodeClick={handleNodeClick}
          />
        </div>
        <div className="flex-[2] min-w-[320px] max-w-lg bg-panel border-l border-border-gold/50">
          {error && !treeNodes.length ? (
            <div className="flex h-full flex-col items-center justify-center gap-4 p-8 text-center">
              <p className="text-red-300 text-sm">{error}</p>
              <a href="/" className="btn-gold text-sm">
                Upload again
              </a>
            </div>
          ) : (
            <AssessmentPanel
              key={panelKey}
              sessionId={sessionId}
              nodeId={selectedNodeId}
              assessmentData={assessmentData}
              step={step}
              error={error}
              onComplete={handleComplete}
            />
          )}
        </div>
      </div>
    </div>
  );
}
