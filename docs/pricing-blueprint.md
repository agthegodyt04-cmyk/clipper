# Pricing Blueprint (No Billing Active)

This project currently exposes a **blueprint-only** pricing experience in the frontend.

## What Exists

1. A pricing preview page in the UI (`/pricing`)
2. Plan definitions (`free`, `creator`, `studio`) with monthly limits
3. Local monthly usage counters in browser storage
4. Usage bars that compare current usage vs selected plan limits
5. No checkout, no subscriptions, no feature lock enforcement

## Local Usage Events Tracked

1. `copy_jobs`
2. `image_jobs`
3. `inpaint_jobs`
4. `video_jobs`
5. `t2v_jobs`

## Suggested Production Backend Phases

1. Tracking phase:
   - Add `usage_events` table
   - Write one event per completed generation job
2. Entitlements phase:
   - Add `workspaces`, `plans`, `workspace_plan_subscriptions`
   - Resolve limits from effective plan at request time
3. Billing phase:
   - Integrate Stripe products/prices/subscriptions
   - Sync via webhook handlers
4. Enforcement phase:
   - Soft limit warnings
   - Hard limit blocks for overages
   - Upgrade prompts

## Suggested Future API Shape

1. `GET /api/v1/billing/preview`:
   - Returns current plan, monthly usage, and limit thresholds
2. `POST /api/v1/billing/checkout-session`:
   - Creates checkout session for plan changes
3. `POST /api/v1/billing/webhooks/stripe`:
   - Handles subscription lifecycle events

