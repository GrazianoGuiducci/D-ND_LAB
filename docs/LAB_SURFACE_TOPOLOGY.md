# Lab Surface Topology

Status: canonical boundary map for the current D-ND Lab family.

The word `Lab` is overloaded across the ecosystem. These surfaces share
genealogy, model language and sometimes THIA context, but they are not the same
operational object.

## Four Different Objects

### 1. Physics Lab on the main site

The physics Lab surfaced on `d-nd.com` / `d-nd.com/ai-lab` is a public-facing
site experience around the original physics/mathematics research line.

It owns:

- public narrative and orientation for the physics Lab;
- visitor-facing explanation, intake and THIA-assisted discussion;
- site copy, guide paths and public interaction surface.

It does not own:

- installable Lab orchestration;
- domain template generation;
- finance Lab runtime decisions.

### 2. Lab subdomain

`lab.d-nd.com` is the Lab dashboard/subdomain surface. It is related to the
same genealogy, but it is a separate operational surface from the main site.

It owns:

- dashboard views for active domains;
- graph, bicono, agent reports, taxonomy, products and info tabs;
- Lab Dashboard Assistant context and domain-level explanation;
- demo/production visibility for domain Labs.

It does not automatically imply that the main-site THIA/DOMUS widget has been
tested or modified.

### 3. Installable repository and meta-lab seed

`D-ND_LAB` is the installable cognitive Lab engine. It contains the orchestrator,
domain contracts, installer, CLI, dashboard server, shipped domains and the
`meta-lab`.

It owns:

- the generic 16-movement Lab cycle;
- domain installation and restoration;
- meta-lab generation of new domain Labs from domain/intention requests;
- contracts that preserve movement across domains without copying results;
- installer behavior for researchers or external operators.

When we say "a system where an assistant configures the Lab and starts it from
an intent", this belongs here: the repo plus meta-lab plus installer/domain
request flow.

### 4. Finance Lab

The finance Lab is a concrete domain Lab being developed into production/demo
on the Lab subdomain. It is also a reference prototype/template for what the
meta-lab should learn to generate.

It owns:

- finance-specific intent, data-card, nulls, baselines and falsifiers;
- current synthetic promotion boundary and dashboard visibility;
- practical value demonstration without trading-signal claims;
- reference behavior for future meta-lab-generated finance or finance-like
  Labs.

It is not the meta-lab itself. It is both:

- a demo/product surface showing value;
- a gold/reference domain used to harden the installable seed.

## Routing Rule

```text
d-nd.com physics Lab page -> public physics narrative and visitor discussion.
lab.d-nd.com dashboard -> live domain views and Lab Dashboard Assistant.
D-ND_LAB repo -> installable engine, domains, meta-lab and installer.
finance domain -> concrete production/demo domain and reference template.
```

Do not transfer conclusions across these boundaries without naming the target
surface and verifying it there.

## Shared Genealogy

The surfaces share D-ND lineage and may share THIA language or context. Shared
genealogy means they can inform one another; it does not mean that a fix,
credential, assistant behavior, UI state or runtime result on one surface is
valid on the others.

When documenting or reporting, use precise names:

- `main-site physics Lab`;
- `Lab subdomain dashboard`;
- `Lab Dashboard Assistant`;
- `THIA/DOMUS public widget`;
- `D-ND_LAB installable repo`;
- `meta-lab`;
- `finance domain Lab`.
