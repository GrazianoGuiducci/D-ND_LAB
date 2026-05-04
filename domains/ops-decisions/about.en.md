# Lab D-ND — ops-decisions

## About

This lab studies the D-ND system from the inside. It reads incidents
(failed cycles, deploy errors, orphan processes) and operator decisions
(memories, feedback, commits) to extract structural rules the system
hasn't formalized yet.

Two faces of the same work. The first traces incidents back to the node
where a relational condition was missing — proposes regressive fixes,
not patches. The second digs through the decision deposit — finds
recurring patterns and crystallizes them as candidate rules.

The lab doesn't impose anything. It proposes. The operator decides what
becomes a rule and what goes to the cimitero. Every proposal carries
its metric: "how many times this pattern appears in the corpus" and
"would the proposed fix have prevented recurrence?"

Naive baseline: symptomatic fix + manual episodic crystallization.
This lab tests whether the D-ND modus (inversion to the regressive
node + automatic pattern matching) produces measurable delta.

The lab is in trial. The first cycle runs on the real system corpus:
2 incident reports, 97 operator memories, 1 COWORK channel.
