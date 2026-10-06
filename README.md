# Falconer distance conjecture in all dimensions

This repository isolates the all-dimensional Falconer formalization from
[openai/math](https://github.com/openai/math/tree/adc7f1241b42e322a6451854ab7e4b4c146bf78a).
The copied Lean sources and Comparator challenge are unchanged.

For every integer dimension at least two and every compact subset of Euclidean
space, the theorem states:

$$
\dim_H E > d/2
\quad\Longrightarrow\quad
\left|\{\|x-y\|:x,y\in E\}\right|>0.
$$

The proof entry point is
[`OAI/MeasureTheory/Falconer/Campaign123PlanarFurstenbergProof.lean`](OAI/MeasureTheory/Falconer/Campaign123PlanarFurstenbergProof.lean).
Its theorem is `OAI.Falconer.falconer_distance_conjecture`.
The independently stated target is
[`ComparatorChallenges/FalconerAllDimensions.lean`](ComparatorChallenges/FalconerAllDimensions.lean).

## Verification

Run the [Falconer Comparator workflow](https://github.com/CoolRmal/falconer-all-dimensions/actions/workflows/comparator.yml)
on GitHub, or on Linux with Lean installed:

```sh
bash scripts/setup-comparator.sh
lake exe cache get
sudo systemd-run --wait --pipe --collect \
  --uid="$(id -u)" --gid="$(id -g)" \
  --property=NoNewPrivileges=yes --property=CapabilityBoundingSet= \
  --property=RestrictAddressFamilies=~AF_UNIX \
  --setenv="PATH=$PATH" --setenv="HOME=$HOME" \
  --working-directory="$PWD" \
  /bin/bash "$PWD/scripts/run-comparator-service.sh"
```

The Linux workflow runs [Comparator](https://github.com/leanprover/comparator)
with the upstream JSON configuration. The permitted axioms are `propext`,
`Quot.sound`, and `Classical.choice`; no definition holes are configured.
Comparator compares the theorem statements, checks their dependencies and axioms,
and replays the solution declarations through the Lean kernel.

The presence of source files or a workflow is not evidence of a passing proof.
Check the workflow conclusion and its uploaded verification log for the actual
result. A failed setup or compilation is not a successful Comparator check.

The workflow runs Comparator before compiling any copied solution sources.
It uses a disposable Linux runner, real Landrun, and the additional Unix-socket
restriction recommended by Comparator upstream. It does not substitute the
development-only fake sandbox.

## Provenance

The repository includes the full transitive closure of local imports of the
proof entry point, the upstream challenge/configuration, and the Apache 2.0
license. Mathlib is pinned to the upstream revision and Lean to version 4.34.1.
The provenance manifest records source file hashes so the extraction can be
checked against the upstream commit.
