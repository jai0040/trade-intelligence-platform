# Upstream Source Reference & Isolation Policy

## Upstream Repository

- **Repository:** `https://github.com/Jakeschincariol/day-trader-skill`
- **Original Author / Copyright:** `Copyright (c) 2026 Jake Schincariol`
- **Upstream License:** MIT License (full verbatim notice preserved in `THIRD_PARTY_NOTICES`)
- **Vendored Location in This Repo:** `trading-engine/skills/`
- **Local Source Snapshot Path:** `C:\Users\ADMIN\.claude\skills\trader-*` (originally installed `2026-11-01`, vendored unmodified on `2026-11-18`)
- **Upstream Commit SHA:** *Pending exact SHA pin* — the local Claude installation did not include `.git` metadata. Record the exact upstream commit SHA in this file during the next authorized online verification against `github.com/Jakeschincariol/day-trader-skill`. In the interim, exact file-level provenance is locked by the SHA-256 manifest below.

---

## Strict Upstream Isolation & Change Management Policy

1. **No Automatic Upstream Pulls:** Production and development branches must **never** pull, download, or auto-update code from the upstream repository.
2. **Independent Maintained Implementation:** This private repository (`trade-intelligence-platform`) is the sole authoritative source for all production builds.
3. **Preservation of Original Scripts:** The 11 upstream skill folders in `trading-engine/skills/` serve as our audited baseline. Platform extensions (multi-market adapters, database persistence, licensed data providers, `Decimal` upgrades, signals-only guardrails) are implemented in `trading-engine/skill_wrappers/`, `trading-engine/adapters/`, `trading-engine/signal_engine/`, and `trading-engine/risk_engine/` rather than destructive rewrites of upstream files.
4. **Approved Upstream Cherry-Picks Only:** Any future upstream bug fix or improvement must be:
   - Reviewed manually for security, license, and signals-only compliance.
   - Tested in an isolated feature branch against the full automated test suite.
   - Logged in the Upstream Sync Log below with upstream commit SHA, review date, and test evidence before merging.

---

## Vendored Baseline SHA-256 Manifest (`2026-11-18`)

All 27 files copied byte-for-byte unmodified from `C:\Users\ADMIN\.claude\skills\`:

```text
31705e9b5055232ee99a96797bbffd280bdb4bf19489c5608f6fcd7e592dda29  trading-engine/skills/trader-alerts/alerts.example.json
4b22d5ef4e26e03d6f8c356a1e2e2dd4aee682a3b05abb5f456a9e1370d4a127  trading-engine/skills/trader-alerts/alerts.py
6a594cc59dcd787f6cffb710eb71debaa752de391a5a98c1719f172d79e87d9f  trading-engine/skills/trader-alerts/SKILL.md
5f495a8d7c5f5686525e6a7eb62ae7c4151a1d5077daf18cad421e6d7b779704  trading-engine/skills/trader-analyst/facts.py
fe9070c8e12bcff0e4badaa728daedc869a0042ee55cc031c9b839254c2165a5  trading-engine/skills/trader-analyst/metrics.example.json
eda8265757d3f48f2563ffd51c7e7c88acc2b30166f74a061d1a7096120fa7e0  trading-engine/skills/trader-analyst/SKILL.md
cffbae3fc51831aae136b7d8a8378fa6299d3b7ccaafaa6b0a7fec59e22d4680  trading-engine/skills/trader-broker/claude_desktop_config.example.json
c2b0dcf2b66f2aa73c9909e1e07ae07975ac44d4783cac5230cebdf11d73f604  trading-engine/skills/trader-broker/SKILL.md
a06ff7b1511ff397156478874efb3e5e90cad59d20397eaade6f99e8d8b6d317  trading-engine/skills/trader-broker/ticket.py
80db18b77f52ec88069b8ca0f6f72b96be6349650dae92a238888a8f005e6b9e  trading-engine/skills/trader-budget/config.example.json
547b65b60d097086884e2454750fa4830ee7464eae7ea5126b631cf0dff30b37  trading-engine/skills/trader-budget/size.py
4082ad10e6d6c8422a6d2fda24fe408369545bf9399318aa4313358fd9cb928f  trading-engine/skills/trader-budget/SKILL.md
975bae28ba360c22c2fc4fe3de9279f41cbe86d080b0feb03f330f90f24e5880  trading-engine/skills/trader-budget/targets.example.json
40bfffb5b7a77494767f70a2fa14a37ed59af5ef75352e2bd1ab7aa45d16550a  trading-engine/skills/trader-entry/entry.py
94a5bb104502410a40133092e36e707c81015a3086f05a71d224bfb380e8b54b  trading-engine/skills/trader-entry/SKILL.md
3e4083e754cdef0b53ce4c84953d695c834a419cc8a0f95b13d80abbbd46c4ec  trading-engine/skills/trader-exit/exit.py
ccc9cf491d8895ff0b1a90ae516472e21955437e0f6382701fdec4ca2d252ba3  trading-engine/skills/trader-exit/SKILL.md
e377784802b00159ace6a5f9caa5deaf48cb2d96312158532ce5818726783405  trading-engine/skills/trader-news/news.py
1cc6d7fb1bf60452b2c346321cc9d0e96544834d7087c03e273082fb00b4ae50  trading-engine/skills/trader-news/SKILL.md
6d10c786d9d5a1c7480b03e664f7a0126d302be58155af2779ec637c0c954c88  trading-engine/skills/trader-pelosi/ptr.py
1e905231908d720253fa4120502359de67ecd12a64b53c48c1dba1c76543f740  trading-engine/skills/trader-pelosi/SKILL.md
e29c6c2b00b8408ac5c4c7306af1432e1ba59b5287c920a21ac48fda4b15695e  trading-engine/skills/trader-risk/check.py
b6c2340ab0bf2815453cf3dd55ac603c7e80867154262b85ccd6e8466a3c7c7b  trading-engine/skills/trader-risk/SKILL.md
86aacc71321712bd68b39190127c9164a14f727449c868f60a5ced10edd1d839  trading-engine/skills/trader-scanner/scan.py
55f2e20c2f2fa0e6dd7d777f7fb0032cd2e140b410caae781224714d09b3222d  trading-engine/skills/trader-scanner/SKILL.md
b5d0f5641d74923774d72081dc32f9bacaec829255128761d8e56ab278ac7243  trading-engine/skills/trader-timemachine/SKILL.md
3db5e7da25e421815f48caaa8bc52632a26120e5b124181a9a9358f6fd4a12f1  trading-engine/skills/trader-timemachine/timemachine.py
```

---

## Upstream Sync Log

| Date (UTC) | Action | Upstream Ref / Commit | Summary | Reviewed & Tested By |
| --- | --- | --- | --- | --- |
| 2026-11-18 | Initial Vendoring | Local v2.0 snapshot (SHA-256 locked above) | Copied all 11 skills unmodified into `trading-engine/skills/` | Phase 2 Baseline |
