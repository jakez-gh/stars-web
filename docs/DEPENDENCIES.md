# Stars! Web — Issue Dependency Graph

This diagram shows the dependency flow between GitHub issues.
Arrows mean "must be done before." Colors match issue labels.

GitHub renders Mermaid natively — view this file on github.com to see the graph.

```mermaid
graph TD
    subgraph "M0: Infrastructure & Quality"
        I1["#1 Fix 69 lint problems"]
        I2["#2 Git hooks pre-commit"]
        I3["#3 Merge to master"]
        I1 --> I3
        I2 --> I3
    end

    subgraph "M1: Complete Read-Only Viewer"
        I4["#4 Ship designs type 26"]
        I5["#5 Production queues type 28"]
        I6["#6 Player/race + tech type 6"]
        I7["#7 Waypoints type 20"]
        I8["#8 GUI automation harness"]
    end

    subgraph "M2: Issue Orders via Web UI"
        I9["#9 Set waypoints UI"]
        I10["#10 Production queue editor UI"]
        I7 --> I9
        I5 --> I10
        I4 --> I10
    end

    subgraph "M3: Playable Turn Loop"
        I11["#11 Write .x1 files"]
        I12["#12 Run host + reload"]
        I9 --> I11
        I10 --> I11
        I11 --> I12
    end

    I3 --> I4
    I3 --> I5
    I3 --> I6
    I3 --> I7
    I3 --> I8

    classDef infra fill:#d4c5f9,stroke:#333,color:#000
    classDef read fill:#0075ca,stroke:#333,color:#fff
    classDef orders fill:#e4e669,stroke:#333,color:#000
    classDef turns fill:#fbca04,stroke:#333,color:#000
    classDef auto fill:#1d76db,stroke:#333,color:#fff

    class I1,I2,I3 infra
    class I4,I5,I6,I7 read
    class I8 auto
    class I9,I10 orders
    class I11,I12 turns
```

## Critical Path

The shortest path to a playable game:

**#1 + #2 → #3 → #7 → #9 → #11 → #12**

(lint → hooks → merge → waypoints → set waypoints UI → write .x1 → run host)

Production queues (#5 → #10) can be done in parallel once #3 is merged.

## How to Update

When adding new issues, update this diagram:

1. Add the issue node in the appropriate milestone subgraph
2. Add dependency arrows
3. Assign the correct class for coloring
