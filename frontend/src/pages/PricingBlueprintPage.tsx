import { useMemo, useState } from "react";
import {
  getUsageSnapshot,
  metricLabel,
  PRICING_BLUEPRINT_PLANS,
  resetUsageSnapshot,
  type PricingPlan,
  type UsageMetric,
} from "../lib/pricingBlueprint";

const ORDERED_METRICS: UsageMetric[] = [
  "copy_jobs",
  "image_jobs",
  "inpaint_jobs",
  "video_jobs",
  "t2v_jobs",
];

function usagePercent(used: number, limit: number): number {
  if (limit <= 0) {
    return 100;
  }
  return Math.min(100, Math.round((used / limit) * 100));
}

export function PricingBlueprintPage() {
  const [activePlanId, setActivePlanId] = useState<PricingPlan["id"]>("free");
  const [usageSnapshot, setUsageSnapshot] = useState(getUsageSnapshot());

  const activePlan = useMemo(
    () => PRICING_BLUEPRINT_PLANS.find((plan) => plan.id === activePlanId) ?? PRICING_BLUEPRINT_PLANS[0],
    [activePlanId],
  );

  return (
    <div className="page-grid">
      <section className="panel panel-wide">
        <h2>Pricing Blueprint (No Paywall Active)</h2>
        <p className="status">
          This is planning mode only. No billing, no card capture, no feature lock is enforced right now.
        </p>
        <div className="inline-actions">
          <button type="button" onClick={() => setUsageSnapshot(getUsageSnapshot())}>
            Refresh Usage
          </button>
          <button
            type="button"
            onClick={() => setUsageSnapshot(resetUsageSnapshot())}
          >
            Reset Demo Counters
          </button>
        </div>
        <p className="small-note">Current month: {usageSnapshot.monthKey}</p>
      </section>

      <section className="panel">
        <h2>Plans</h2>
        <div className="plan-grid">
          {PRICING_BLUEPRINT_PLANS.map((plan) => (
            <article
              key={plan.id}
              className={`plan-card ${plan.id === activePlan.id ? "active" : ""}`}
            >
              <p className="plan-name">{plan.label}</p>
              <p className="plan-price">{plan.monthlyPrice} / month</p>
              <p className="small-note">{plan.notes}</p>
              <button
                type="button"
                className={plan.id === activePlan.id ? "secondary" : ""}
                onClick={() => setActivePlanId(plan.id)}
              >
                Use As Preview
              </button>
            </article>
          ))}
        </div>
      </section>

      <section className="panel">
        <h2>Usage vs {activePlan.label}</h2>
        <div className="form-grid">
          {ORDERED_METRICS.map((metric) => {
            const used = usageSnapshot.counters[metric] ?? 0;
            const limit = activePlan.limits[metric];
            const pct = usagePercent(used, limit);
            const over = used > limit;
            return (
              <div key={metric} className="meter-row">
                <div className="meter-top">
                  <strong>{metricLabel(metric)}</strong>
                  <span>
                    {used} / {limit}
                  </span>
                </div>
                <div className="meter-track">
                  <div
                    className={`meter-fill ${over ? "danger" : ""}`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="panel panel-wide">
        <h2>Implementation Blueprint</h2>
        <div className="asset-grid">
          <article className="asset-card">
            <p>
              <strong>Phase A: Tracking</strong>
            </p>
            <p className="small-note">Add backend usage events table and emit events per completed job.</p>
          </article>
          <article className="asset-card">
            <p>
              <strong>Phase B: Entitlements</strong>
            </p>
            <p className="small-note">Attach plan limits to account/workspace and compute monthly usage windows.</p>
          </article>
          <article className="asset-card">
            <p>
              <strong>Phase C: Billing</strong>
            </p>
            <p className="small-note">Integrate Stripe customer/subscription records with webhook sync.</p>
          </article>
          <article className="asset-card">
            <p>
              <strong>Phase D: Enforcement</strong>
            </p>
            <p className="small-note">Soft warnings first, then hard limits with upgrade prompts.</p>
          </article>
        </div>
      </section>
    </div>
  );
}

