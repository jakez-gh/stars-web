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

    subgraph "MA0: Automation Foundation"
        I8["#8 GUI automation harness"]
        I17["#17 Launcher: start/stop via OTVDM"]
        I18["#18 Window control: find/focus/pin"]
        I19["#19 Screenshot capture: window to PNG"]
        I20["#20 Input simulation: mouse + keyboard"]
        I8 --> I17
        I17 --> I18
        I18 --> I19
        I18 --> I20
    end

    subgraph "MA1: Read via GUI"
        I23["#23 Navigate screens: planets/fleets/scanner"]
        I25["#25 Template matching: read text from screens"]
        I26["#26 Cross-verify: file parsing vs GUI"]
        I19 --> I23
        I20 --> I23
        I23 --> I25
        I25 --> I26
    end

    subgraph "MA2: Command via GUI"
        I27["#27 Automate waypoint setting"]
        I28["#28 Automate production queue changes"]
        I29["#29 Automate research allocation"]
        I30["#30 Generate turn: save + submit"]
        I23 --> I27
        I23 --> I28
        I23 --> I29
        I27 --> I30
        I28 --> I30
        I29 --> I30
    end

    subgraph "MA3: Autonomous Play"
        I32["#32 AI decision loop: autonomous turn cycle"]
        I26 --> I32
        I30 --> I32
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
    class I8,I17,I18,I19,I20,I23,I25,I26,I27,I28,I29,I30,I32 auto
    class I9,I10 orders
    class I11,I12 turns
```

## Critical Paths

### Web track (shortest path to playable game)

**#1 + #2 → #3 → #7 → #9 → #11 → #12**

(lint → hooks → merge → waypoints → set waypoints UI → write .x1 → run host)

### Automation track (shortest path to autonomous play)

**#3 → #8 → #17 → #18 → #20 → #23 → #27 → #30 → #32**

(merge → harness → launcher → window → input → navigate → waypoints → generate turn → AI loop)

Production queues (#5 → #10) and GUI reading (#19 → #25 → #26) can be done in parallel on their respective tracks.

## How to Update

When adding new issues, update this diagram:

1. Add the issue node in the appropriate milestone subgraph
2. Add dependency arrows
3. Assign the correct class for coloring
