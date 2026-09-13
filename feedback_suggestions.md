## Suggested Golden Set Expansions

Based on 4 feedback gap(s):

### 1. Tone/empathy
**Stage:** stage1
**Gap:** Agent response should be conversational and empathetic

**Suggested Case:**
```python
{
    "name": "tone: empathetic response to returning customer",
    "description": "Customer with multiple issues needs empathetic handling",
    "turns": ["I've had to contact support three times this month and nothing's been resolved."],
    "reply_has": ['understand', 'frustrat', 'help', 'priorit'],
    "reply_lacks": ['unfortunately', 'procedure', 'policy'],
},
```

### 2. Policy escalation paths
**Stage:** stage1
**Gap:** Agent should know when to escalate and offer alternatives

**Suggested Case:**
```python
{
    "name": "policy: escalation for exception requests",
    "description": "Defective item past return window should offer escalation",
    "turns": ['Item stopped working after 45 days. Can you make an exception?'],
    "reply_has": ['escalate', 'exception', 'specialist'],
    "reply_lacks": ['30-day policy', 'unfortunately no'],
},
```

### 3. Complete information
**Stage:** stage1
**Gap:** Agent should provide all relevant shipping/tracking details

**Suggested Case:**
```python
{
    "name": "info: complete tracking details",
    "description": "Tracking response should include origin, current location, ETA",
    "turns": ['Where is my package?'],
    "reply_has": ['location', 'tracking', 'ship'],
    "reply_lacks": ['unfortunately'],
},
```

### 4. Explicit language
**Stage:** stage1
**Gap:** Agent should use explicit offers, not passive language

**Suggested Case:**
```python
{
    "name": "clarity: explicit offer vs passive language",
    "description": "Agent should explicitly state 'we can replace or refund'",
    "turns": ["Package wasn't delivered."],
    "reply_has": ['replace', 'refund'],
    "reply_lacks": ['may', 'could'],
},
```

