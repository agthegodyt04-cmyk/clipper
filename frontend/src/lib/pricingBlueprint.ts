export type UsageMetric = "copy_jobs" | "image_jobs" | "inpaint_jobs" | "video_jobs" | "t2v_jobs";

export interface UsageSnapshot {
  monthKey: string;
  counters: Record<UsageMetric, number>;
}

export interface PricingPlan {
  id: "free" | "creator" | "studio";
  label: string;
  monthlyPrice: string;
  notes: string;
  limits: Record<UsageMetric, number>;
}

const STORAGE_KEY = "clipper_pricing_usage_v1";

const ZERO_COUNTERS: Record<UsageMetric, number> = {
  copy_jobs: 0,
  image_jobs: 0,
  inpaint_jobs: 0,
  video_jobs: 0,
  t2v_jobs: 0,
};

export const PRICING_BLUEPRINT_PLANS: PricingPlan[] = [
  {
    id: "free",
    label: "Free Blueprint",
    monthlyPrice: "$0",
    notes: "Great for testing and hobby campaigns.",
    limits: {
      copy_jobs: 100,
      image_jobs: 40,
      inpaint_jobs: 30,
      video_jobs: 8,
      t2v_jobs: 2,
    },
  },
  {
    id: "creator",
    label: "Creator",
    monthlyPrice: "$19",
    notes: "For solo creators running weekly campaigns.",
    limits: {
      copy_jobs: 400,
      image_jobs: 180,
      inpaint_jobs: 120,
      video_jobs: 40,
      t2v_jobs: 15,
    },
  },
  {
    id: "studio",
    label: "Studio",
    monthlyPrice: "$59",
    notes: "For teams handling multiple brands.",
    limits: {
      copy_jobs: 1500,
      image_jobs: 700,
      inpaint_jobs: 450,
      video_jobs: 180,
      t2v_jobs: 75,
    },
  },
];

function monthKeyNow(): string {
  const now = new Date();
  const month = `${now.getMonth() + 1}`.padStart(2, "0");
  return `${now.getFullYear()}-${month}`;
}

function cloneZeroCounters(): Record<UsageMetric, number> {
  return { ...ZERO_COUNTERS };
}

function defaultSnapshot(): UsageSnapshot {
  return {
    monthKey: monthKeyNow(),
    counters: cloneZeroCounters(),
  };
}

export function getUsageSnapshot(): UsageSnapshot {
  if (typeof window === "undefined") {
    return defaultSnapshot();
  }

  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    const snapshot = defaultSnapshot();
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot));
    return snapshot;
  }

  try {
    const parsed = JSON.parse(raw) as UsageSnapshot;
    if (parsed.monthKey !== monthKeyNow()) {
      const reset = defaultSnapshot();
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(reset));
      return reset;
    }
    const safe: UsageSnapshot = {
      monthKey: parsed.monthKey,
      counters: {
        copy_jobs: Number(parsed.counters?.copy_jobs ?? 0),
        image_jobs: Number(parsed.counters?.image_jobs ?? 0),
        inpaint_jobs: Number(parsed.counters?.inpaint_jobs ?? 0),
        video_jobs: Number(parsed.counters?.video_jobs ?? 0),
        t2v_jobs: Number(parsed.counters?.t2v_jobs ?? 0),
      },
    };
    return safe;
  } catch {
    const snapshot = defaultSnapshot();
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot));
    return snapshot;
  }
}

export function recordUsage(metric: UsageMetric, amount = 1): UsageSnapshot {
  const snapshot = getUsageSnapshot();
  snapshot.counters[metric] = Math.max(0, snapshot.counters[metric] + amount);
  if (typeof window !== "undefined") {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot));
  }
  return snapshot;
}

export function resetUsageSnapshot(): UsageSnapshot {
  const snapshot = defaultSnapshot();
  if (typeof window !== "undefined") {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot));
  }
  return snapshot;
}

export function metricLabel(metric: UsageMetric): string {
  switch (metric) {
    case "copy_jobs":
      return "Copy Jobs";
    case "image_jobs":
      return "Image Jobs";
    case "inpaint_jobs":
      return "Inpaint Jobs";
    case "video_jobs":
      return "Storyboard Video Jobs";
    case "t2v_jobs":
      return "Text-to-Video Jobs";
    default:
      return metric;
  }
}

