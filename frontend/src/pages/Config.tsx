import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Page } from "@/components/common";
import { post } from "@/lib/api";

const DEFAULT_WEIGHTS = {
  "model_risk": 0.20,
  "rule_evidence": 0.20,
  "peer_deviation": 0.10,
  "network": 0.10,
  "temporal": 0.10,
  "anomaly": 0.05,
  "evidence_strength": 0.10,
  "exposure": 0.10,
  "member_impact": 0.05,
};

export default function Config() {
  const [weights, setWeights] = useState<Record<string, number>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    // Fetch current weights from queue API response (hacky but it works since queue returns them)
    fetch("/api/queue").then(res => res.json()).then(data => {
      if (data.weights) setWeights(data.weights);
    }).catch(() => setWeights(DEFAULT_WEIGHTS));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      await post("/config/weights", weights);
      alert("Weights updated and case priorities recalculated successfully!");
    } catch (e) {
      alert("Failed to update weights.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Page title="System Configuration" subtitle="Tune investigation prioritization weights dynamically.">
      <Card className="max-w-2xl">
        <CardHeader>
          <CardTitle>Priority Scoring Weights</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {Object.keys(weights).map((key) => (
              <div key={key} className="flex items-center gap-4">
                <label className="w-48 text-sm font-medium capitalize">{key.replace("_", " ")}</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  max="1"
                  value={weights[key]}
                  onChange={(e) => setWeights({ ...weights, [key]: parseFloat(e.target.value) || 0 })}
                  className="h-8 w-24 rounded-md border border-input bg-background px-2 text-sm"
                />
              </div>
            ))}
            
            <div className="pt-4 flex gap-4">
              <Button onClick={handleSave} disabled={saving}>{saving ? "Saving..." : "Save Weights"}</Button>
              <Button variant="outline" onClick={() => setWeights(DEFAULT_WEIGHTS)}>Reset to Default</Button>
            </div>
            
            <p className="text-xs text-muted-foreground mt-4">
              Total weight: {Object.values(weights).reduce((a, b) => a + b, 0).toFixed(2)}. 
              (It is recommended to keep the sum around 1.0)
            </p>
          </div>
        </CardContent>
      </Card>
    </Page>
  );
}
