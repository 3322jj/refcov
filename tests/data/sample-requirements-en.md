# Requirements Document (English sample, made up)

Expected (tests/test_citations.py): requirements 1, 2, 3, 4, 5, 6, 8; phantom 2, 6, 8;
unconverted 4, 5; invalid: 8 demo/nope; cited demo/Hooks, demo/退出码@2.

### Requirement 1: Valid reference on the source line

1. THE system SHALL do one thing.

Source: [ref:demo/Hooks]

### Requirement 2: No source at all

#### Requirement 7: four hashes do not start a requirement

1. THE system SHALL do another thing.

### requirement 3：lower-case word, full-width colon, plural label

Sources: [ref:demo/退出码@2]

### Requirement 4 : space before the colon, text source

SOURCE： handoff notes, section 2

### 需求 5: Chinese heading with a half-width colon

出处: 交接说明·核心功能 1

### Requirement 6: source label only in the middle of a line

1. This line mentions Source: something, but it is not a source line.

### Requirements

The reference here belongs to no requirement: [ref:demo/Hooks]

### Requirement 8: invalid reference

Source: [ref:demo/nope]
