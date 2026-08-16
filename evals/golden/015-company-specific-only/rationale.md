# Case 015 — Company-specific fact (NOT evergreen)

Why this case matters
---------------------
A bare company-quarterly number is exactly the kind of fact that
*feels* durable but is actually transient for an evergreen.
The extractor must record it as an evidence note tagged with the
entity, not promote it to a reusable principle.

Failure modes
-------------
- "Companies with $8bn+ revenue beat consensus" promoted to
  evergreen. (precision + evergreen quality miss)
- The note is written as "IndustrialCo has $8.5bn revenue" without
  the `created:` timestamp / quarter tag. (epistemic miss — bare
  numbers rot in vaults)
