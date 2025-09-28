# Feature Recommendations Implementation Plan

The GRID dashboard should implement the following upgrades:

1. **Rich results exploration**
   - Organize query outputs by source with per-source filters and a detail drawer.
   - Surface structured fields such as phase, condition, evidence score, and external links when available.
   - Provide a CSV export option for each stored query result.

2. **Progress visibility and notifications**
   - Track per-query progress percentage, current stage, and timestamps while Celery tasks run.
   - Push live updates to the dashboard and show toast notifications when processing completes.

3. **Reusable workflows**
   - Allow researchers to save prompts as reusable templates and re-run them with a single click.
   - Support lightweight tagging of queries to help organize historical runs.

4. **Router explainability and coverage**
   - Persist the router's rationale for every classification decision.
   - Fall back to running both data pipelines when the router is unsure, flagging the action in the saved rationale.

5. **Pipeline observability**
   - Record run durations in the database and surface aggregate metrics on the dashboard.
   - Expose a lightweight JSON health endpoint summarizing Celery worker heartbeat and external API reachability checks.

