# Error analysis

## Observed failure patterns

The grouped model raises 114 false alarms among 150 benign flows. R03's Medium
output alone has centroid 43.333, above its calibrated threshold 25, so legitimate
long low-rate exchanges become alerts. Benign median score 38.466 and attack median
37.172 demonstrate strong overlap. A high aggregate F1 does not cure that overlap.
Low-rate and low-volume attacks activate conservative Low rules; small application
attacks may be behaviorally indistinguishable from benign transactions. Grouped
SQL injection recall is 0/3, Bot and Slowhttptest miss 40/150 each, and slowloris
misses 33/150. These cases show the limits of load-oriented aggregate inputs.

Day threshold 75 is selected because none of the tested thresholds performs well
on Thursday validation. Friday attack scores concentrate mostly below it (attack
median 50.573), producing 287,709 false negatives. PortScan has 157,751/157,751
misses, Bot 1,956/1,956, and DDoS 128,002/128,020. Simultaneous Low and High rules
can suppress a concern rule's centroid. Only 18 attacks exceed the day threshold.
This threshold collapse must remain visible in a future demonstration UI.

## Extreme values, duplicates and label ambiguity

Valid extreme measurements saturate shoulder memberships, rather than producing
invalid scores or being removed. No grouped test input is outside its observed
training range; two day test rows are. Out-of-range flags and error examples remain
available. Bounded training-only numerical stress tests also cover huge values.
The grouped test repeats 126 full-observation rows beyond first occurrences; day
test repeats 71,336. Group-weighted metrics quantify sensitivity to duplication.
One conflicting-label group with two day test rows has the same behavioral
evidence but two labels; no deterministic feature-only engine can satisfy both.
Excluding it barely changes the metrics (see metrics.json), so label conflicts do
not explain the model's main failures. The development subset happens to contain
no conflicting full-observation group in its test; the 698 source conflicts still
exist and were not relabeled. Exact equality of five-feature projections adds a
separate ambiguity/overlap risk quantified in projected_input_overlap.json.

## Deterministic representative examples

Five false positives and five false negatives per scenario are chosen by stable
row-ID hash priority with seed 20261103. They are diagnostic examples, not a random
estimate of error prevalence. Full inputs, all memberships, every activated rule,
strengths, consequents, model hashes and explanation keys are in error_examples.json.
No rules were automatically changed from these examples.

### grouped false_positive — source row 1694363

Actual label: BENIGN. Score 43.333333, Medium; alert=True.

Inputs: `{" Flow Packets/s": 0.4292773, " Total Fwd Packets": 14.0, " Packet Length Mean": 73.74074074, " Bwd Packet Length Std": 236.1033897, " Down/Up Ratio": 0.0}`.

Dominant input terms: `{" Flow Packets/s": "sparse", " Total Fwd Packets": "many", " Packet Length Mean": "medium", " Bwd Packet Length Std": "uniform", " Down/Up Ratio": "forward"}`.

Strongest rules: R03 -> Medium (1.0000).

Possible error mechanism: Large low-rate flows merit context but may be legitimate long sessions. Those behavior hypotheses overlap the actual traffic label; the aggregated centroid crosses the selected alert threshold in the wrong direction. This is an explanatory hypothesis, not a verified attack mechanism.

### grouped false_positive — source row 4086

Actual label: BENIGN. Score 52.984396, High; alert=True.

Inputs: `{" Flow Packets/s": 0.217221056, " Total Fwd Packets": 14.0, " Packet Length Mean": 4.423076923, " Bwd Packet Length Std": 0.0, " Down/Up Ratio": 0.0}`.

Dominant input terms: `{" Flow Packets/s": "sparse", " Total Fwd Packets": "many", " Packet Length Mean": "small", " Bwd Packet Length Std": "uniform", " Down/Up Ratio": "forward"}`.

Strongest rules: R03 -> Medium (1.0000), R13 -> High (0.6326).

Possible error mechanism: Large low-rate flows merit context but may be legitimate long sessions.; Many small forward packets can indicate repeated requests. Those behavior hypotheses overlap the actual traffic label; the aggregated centroid crosses the selected alert threshold in the wrong direction. This is an explanatory hypothesis, not a verified attack mechanism.

### grouped false_positive — source row 2483649

Actual label: BENIGN. Score 40.024871, Medium; alert=True.

Inputs: `{" Flow Packets/s": 16736.40167, " Total Fwd Packets": 2.0, " Packet Length Mean": 122.2, " Bwd Packet Length Std": 0.0, " Down/Up Ratio": 1.0}`.

Dominant input terms: `{" Flow Packets/s": "intensive", " Total Fwd Packets": "few", " Packet Length Mean": "medium", " Bwd Packet Length Std": "uniform", " Down/Up Ratio": "balanced"}`.

Strongest rules: R07 -> Medium (0.8839), R04 -> Low (0.1161), R17 -> Low (0.1161).

Possible error mechanism: A tiny duration can inflate rate for a few packets; avoid critical risk from rate alone.; Few packets at ordinary intensity can be routine transactions.; Balanced medium-size transactions provide a routine-traffic counter-hypothesis. Those behavior hypotheses overlap the actual traffic label; the aggregated centroid crosses the selected alert threshold in the wrong direction. This is an explanatory hypothesis, not a verified attack mechanism.

### grouped false_positive — source row 641795

Actual label: BENIGN. Score 43.050981, Medium; alert=True.

Inputs: `{" Flow Packets/s": 60.5877007, " Total Fwd Packets": 2.0, " Packet Length Mean": 2.0, " Bwd Packet Length Std": 0.0, " Down/Up Ratio": 0.0}`.

Dominant input terms: `{" Flow Packets/s": "moderate", " Total Fwd Packets": "few", " Packet Length Mean": "small", " Bwd Packet Length Std": "uniform", " Down/Up Ratio": "forward"}`.

Strongest rules: R19 -> Medium (0.8339), R04 -> Low (0.7677), R12 -> High (0.7677).

Possible error mechanism: Small forward-only exchanges merit context, including scanning, but are not definitive.; Few packets at ordinary intensity can be routine transactions.; Small forward-heavy transactions warrant investigation; legitimate one-way traffic overlaps. Those behavior hypotheses overlap the actual traffic label; the aggregated centroid crosses the selected alert threshold in the wrong direction. This is an explanatory hypothesis, not a verified attack mechanism.

### grouped false_positive — source row 1059663

Actual label: BENIGN. Score 40.597562, Medium; alert=True.

Inputs: `{" Flow Packets/s": 20000.0, " Total Fwd Packets": 2.0, " Packet Length Mean": 84.4, " Bwd Packet Length Std": 0.0, " Down/Up Ratio": 1.0}`.

Dominant input terms: `{" Flow Packets/s": "intensive", " Total Fwd Packets": "few", " Packet Length Mean": "medium", " Bwd Packet Length Std": "uniform", " Down/Up Ratio": "balanced"}`.

Strongest rules: R07 -> Medium (0.9046), R04 -> Low (0.0954), R17 -> Low (0.0954).

Possible error mechanism: A tiny duration can inflate rate for a few packets; avoid critical risk from rate alone.; Few packets at ordinary intensity can be routine transactions.; Balanced medium-size transactions provide a routine-traffic counter-hypothesis. Those behavior hypotheses overlap the actual traffic label; the aggregated centroid crosses the selected alert threshold in the wrong direction. This is an explanatory hypothesis, not a verified attack mechanism.

### grouped false_negative — source row 109402

Actual label: DDoS. Score 16.249797, Low; alert=False.

Inputs: `{" Flow Packets/s": 0.793100973, " Total Fwd Packets": 4.0, " Packet Length Mean": 6.0, " Bwd Packet Length Std": 0.0, " Down/Up Ratio": 0.0}`.

Dominant input terms: `{" Flow Packets/s": "sparse", " Total Fwd Packets": "moderate", " Packet Length Mean": "small", " Bwd Packet Length Std": "uniform", " Down/Up Ratio": "forward"}`.

Strongest rules: R02 -> Low (0.9591), R05 -> Low (0.0409), R12 -> High (0.0409).

Possible error mechanism: Modest traffic at a low packet rate has weak load evidence.; Ordinary rate and volume form a conservative low-load baseline.; Small forward-heavy transactions warrant investigation; legitimate one-way traffic overlaps. Those behavior hypotheses overlap the actual traffic label; the aggregated centroid crosses the selected alert threshold in the wrong direction. This is an explanatory hypothesis, not a verified attack mechanism.

### grouped false_negative — source row 171557

Actual label: DDoS. Score 18.382579, Low; alert=False.

Inputs: `{" Flow Packets/s": 0.883350283, " Total Fwd Packets": 4.0, " Packet Length Mean": 6.0, " Bwd Packet Length Std": 0.0, " Down/Up Ratio": 0.0}`.

Dominant input terms: `{" Flow Packets/s": "sparse", " Total Fwd Packets": "moderate", " Packet Length Mean": "small", " Bwd Packet Length Std": "uniform", " Down/Up Ratio": "forward"}`.

Strongest rules: R02 -> Low (0.9285), R05 -> Low (0.0715), R12 -> High (0.0715).

Possible error mechanism: Modest traffic at a low packet rate has weak load evidence.; Ordinary rate and volume form a conservative low-load baseline.; Small forward-heavy transactions warrant investigation; legitimate one-way traffic overlaps. Those behavior hypotheses overlap the actual traffic label; the aggregated centroid crosses the selected alert threshold in the wrong direction. This is an explanatory hypothesis, not a verified attack mechanism.

### grouped false_negative — source row 172994

Actual label: DDoS. Score 23.823684, Low; alert=False.

Inputs: `{" Flow Packets/s": 16.10504786, " Total Fwd Packets": 3.0, " Packet Length Mean": 1162.7, " Bwd Packet Length Std": 1757.789948, " Down/Up Ratio": 2.0}`.

Dominant input terms: `{" Flow Packets/s": "moderate", " Total Fwd Packets": "moderate", " Packet Length Mean": "large", " Bwd Packet Length Std": "variable", " Down/Up Ratio": "backward"}`.

Strongest rules: R05 -> Low (0.5632), R04 -> Low (0.4368), R07 -> Medium (0.0833).

Possible error mechanism: Ordinary rate and volume form a conservative low-load baseline.; Few packets at ordinary intensity can be routine transactions.; A tiny duration can inflate rate for a few packets; avoid critical risk from rate alone. Those behavior hypotheses overlap the actual traffic label; the aggregated centroid crosses the selected alert threshold in the wrong direction. This is an explanatory hypothesis, not a verified attack mechanism.

### grouped false_negative — source row 162277

Actual label: DDoS. Score 13.165000, Low; alert=False.

Inputs: `{" Flow Packets/s": 0.507628321, " Total Fwd Packets": 4.0, " Packet Length Mean": 6.0, " Bwd Packet Length Std": 0.0, " Down/Up Ratio": 0.0}`.

Dominant input terms: `{" Flow Packets/s": "sparse", " Total Fwd Packets": "moderate", " Packet Length Mean": "small", " Bwd Packet Length Std": "uniform", " Down/Up Ratio": "forward"}`.

Strongest rules: R02 -> Low (1.0000).

Possible error mechanism: Modest traffic at a low packet rate has weak load evidence. Those behavior hypotheses overlap the actual traffic label; the aggregated centroid crosses the selected alert threshold in the wrong direction. This is an explanatory hypothesis, not a verified attack mechanism.

### grouped false_negative — source row 2292216

Actual label: DoS Hulk. Score 22.376407, Low; alert=False.

Inputs: `{" Flow Packets/s": 0.132159686, " Total Fwd Packets": 5.0, " Packet Length Mean": 856.4285714, " Bwd Packet Length Std": 1547.981999, " Down/Up Ratio": 1.0}`.

Dominant input terms: `{" Flow Packets/s": "sparse", " Total Fwd Packets": "moderate", " Packet Length Mean": "large", " Bwd Packet Length Std": "variable", " Down/Up Ratio": "balanced"}`.

Strongest rules: R02 -> Low (0.7688), R03 -> Medium (0.2312).

Possible error mechanism: Modest traffic at a low packet rate has weak load evidence.; Large low-rate flows merit context but may be legitimate long sessions. Those behavior hypotheses overlap the actual traffic label; the aggregated centroid crosses the selected alert threshold in the wrong direction. This is an explanatory hypothesis, not a verified attack mechanism.

### day false_negative — source row 435511

Actual label: PortScan. Score 52.190098, High; alert=False.

Inputs: `{" Flow Packets/s": 38461.53846, " Total Fwd Packets": 1.0, " Packet Length Mean": 2.0, " Bwd Packet Length Std": 0.0, " Down/Up Ratio": 1.0}`.

Dominant input terms: `{" Flow Packets/s": "intensive", " Total Fwd Packets": "few", " Packet Length Mean": "small", " Bwd Packet Length Std": "uniform", " Down/Up Ratio": "balanced"}`.

Strongest rules: R07 -> Medium (0.9229), R11 -> High (0.9229), R04 -> Low (0.0771).

Possible error mechanism: A tiny duration can inflate rate for a few packets; avoid critical risk from rate alone.; Intensive small packets with uniform responses can resemble repetitive traffic.; Few packets at ordinary intensity can be routine transactions. Those behavior hypotheses overlap the actual traffic label; the aggregated centroid crosses the selected alert threshold in the wrong direction. This is an explanatory hypothesis, not a verified attack mechanism.

### day false_negative — source row 190974

Actual label: DDoS. Score 26.743179, Medium; alert=False.

Inputs: `{" Flow Packets/s": 0.741125714, " Total Fwd Packets": 4.0, " Packet Length Mean": 6.0, " Bwd Packet Length Std": 0.0, " Down/Up Ratio": 0.0}`.

Dominant input terms: `{" Flow Packets/s": "sparse", " Total Fwd Packets": "moderate", " Packet Length Mean": "small", " Bwd Packet Length Std": "uniform", " Down/Up Ratio": "forward"}`.

Strongest rules: R02 -> Low (0.8219), R03 -> Medium (0.1781), R13 -> High (0.1781).

Possible error mechanism: Modest traffic at a low packet rate has weak load evidence.; Large low-rate flows merit context but may be legitimate long sessions.; Many small forward packets can indicate repeated requests. Those behavior hypotheses overlap the actual traffic label; the aggregated centroid crosses the selected alert threshold in the wrong direction. This is an explanatory hypothesis, not a verified attack mechanism.

### day false_negative — source row 399543

Actual label: PortScan. Score 52.959948, High; alert=False.

Inputs: `{" Flow Packets/s": 46511.62791, " Total Fwd Packets": 1.0, " Packet Length Mean": 2.0, " Bwd Packet Length Std": 0.0, " Down/Up Ratio": 1.0}`.

Dominant input terms: `{" Flow Packets/s": "intensive", " Total Fwd Packets": "few", " Packet Length Mean": "small", " Bwd Packet Length Std": "uniform", " Down/Up Ratio": "balanced"}`.

Strongest rules: R07 -> Medium (0.9551), R11 -> High (0.9551), R04 -> Low (0.0449).

Possible error mechanism: A tiny duration can inflate rate for a few packets; avoid critical risk from rate alone.; Intensive small packets with uniform responses can resemble repetitive traffic.; Few packets at ordinary intensity can be routine transactions. Those behavior hypotheses overlap the actual traffic label; the aggregated centroid crosses the selected alert threshold in the wrong direction. This is an explanatory hypothesis, not a verified attack mechanism.

### day false_negative — source row 447747

Actual label: PortScan. Score 51.275750, High; alert=False.

Inputs: `{" Flow Packets/s": 30769.23077, " Total Fwd Packets": 1.0, " Packet Length Mean": 2.0, " Bwd Packet Length Std": 0.0, " Down/Up Ratio": 1.0}`.

Dominant input terms: `{" Flow Packets/s": "intensive", " Total Fwd Packets": "few", " Packet Length Mean": "small", " Bwd Packet Length Std": "uniform", " Down/Up Ratio": "balanced"}`.

Strongest rules: R07 -> Medium (0.8851), R11 -> High (0.8851), R04 -> Low (0.1149).

Possible error mechanism: A tiny duration can inflate rate for a few packets; avoid critical risk from rate alone.; Intensive small packets with uniform responses can resemble repetitive traffic.; Few packets at ordinary intensity can be routine transactions. Those behavior hypotheses overlap the actual traffic label; the aggregated centroid crosses the selected alert threshold in the wrong direction. This is an explanatory hypothesis, not a verified attack mechanism.

### day false_negative — source row 67171

Actual label: DDoS. Score 45.031570, Medium; alert=False.

Inputs: `{" Flow Packets/s": 0.151687583, " Total Fwd Packets": 8.0, " Packet Length Mean": 897.6153846, " Bwd Packet Length Std": 5795.50069, " Down/Up Ratio": 0.0}`.

Dominant input terms: `{" Flow Packets/s": "sparse", " Total Fwd Packets": "many", " Packet Length Mean": "large", " Bwd Packet Length Std": "highly_variable", " Down/Up Ratio": "forward"}`.

Strongest rules: R15 -> Medium (1.0000), R03 -> Medium (0.6473), R14 -> High (0.6473).

Possible error mechanism: Large varied responses at sparse rate are ambiguous rather than inherently safe.; Large low-rate flows merit context but may be legitimate long sessions.; Large varied responses at high volume can produce resource pressure; benign transfers overlap. Those behavior hypotheses overlap the actual traffic label; the aggregated centroid crosses the selected alert threshold in the wrong direction. This is an explanatory hypothesis, not a verified attack mechanism.

### day false_positive — source row 648664

Actual label: BENIGN. Score 79.272274, Critical; alert=True.

Inputs: `{" Flow Packets/s": 60000.0, " Total Fwd Packets": 3.0, " Packet Length Mean": 7.75, " Bwd Packet Length Std": 0.0, " Down/Up Ratio": 0.0}`.

Dominant input terms: `{" Flow Packets/s": "intensive", " Total Fwd Packets": "moderate", " Packet Length Mean": "small", " Bwd Packet Length Std": "uniform", " Down/Up Ratio": "forward"}`.

Strongest rules: R08 -> High (0.9983), R10 -> Critical (0.9751), R11 -> High (0.9751).

Possible error mechanism: Intensive activity with nontrivial volume supports load concern.; Small intensive forward-dominated traffic can resemble repeated request/control floods.; Intensive small packets with uniform responses can resemble repetitive traffic. Those behavior hypotheses overlap the actual traffic label; the aggregated centroid crosses the selected alert threshold in the wrong direction. This is an explanatory hypothesis, not a verified attack mechanism.

### day false_positive — source row 461811

Actual label: BENIGN. Score 79.501250, Critical; alert=True.

Inputs: `{" Flow Packets/s": 61224.4898, " Total Fwd Packets": 3.0, " Packet Length Mean": 6.0, " Bwd Packet Length Std": 0.0, " Down/Up Ratio": 0.0}`.

Dominant input terms: `{" Flow Packets/s": "intensive", " Total Fwd Packets": "moderate", " Packet Length Mean": "small", " Bwd Packet Length Std": "uniform", " Down/Up Ratio": "forward"}`.

Strongest rules: R08 -> High (1.0000), R10 -> Critical (1.0000), R11 -> High (1.0000).

Possible error mechanism: Intensive activity with nontrivial volume supports load concern.; Small intensive forward-dominated traffic can resemble repeated request/control floods.; Intensive small packets with uniform responses can resemble repetitive traffic. Those behavior hypotheses overlap the actual traffic label; the aggregated centroid crosses the selected alert threshold in the wrong direction. This is an explanatory hypothesis, not a verified attack mechanism.

### day false_positive — source row 298199

Actual label: BENIGN. Score 79.501250, Critical; alert=True.

Inputs: `{" Flow Packets/s": 72463.76812, " Total Fwd Packets": 4.0, " Packet Length Mean": 0.0, " Bwd Packet Length Std": 0.0, " Down/Up Ratio": 0.0}`.

Dominant input terms: `{" Flow Packets/s": "intensive", " Total Fwd Packets": "moderate", " Packet Length Mean": "small", " Bwd Packet Length Std": "uniform", " Down/Up Ratio": "forward"}`.

Strongest rules: R10 -> Critical (1.0000), R11 -> High (1.0000), R08 -> High (0.8219).

Possible error mechanism: Small intensive forward-dominated traffic can resemble repeated request/control floods.; Intensive small packets with uniform responses can resemble repetitive traffic.; Intensive activity with nontrivial volume supports load concern. Those behavior hypotheses overlap the actual traffic label; the aggregated centroid crosses the selected alert threshold in the wrong direction. This is an explanatory hypothesis, not a verified attack mechanism.

### day false_positive — source row 703015

Actual label: BENIGN. Score 79.501250, Critical; alert=True.

Inputs: `{" Flow Packets/s": 1500000.0, " Total Fwd Packets": 3.0, " Packet Length Mean": 0.0, " Bwd Packet Length Std": 0.0, " Down/Up Ratio": 0.0}`.

Dominant input terms: `{" Flow Packets/s": "intensive", " Total Fwd Packets": "moderate", " Packet Length Mean": "small", " Bwd Packet Length Std": "uniform", " Down/Up Ratio": "forward"}`.

Strongest rules: R08 -> High (1.0000), R10 -> Critical (1.0000), R11 -> High (1.0000).

Possible error mechanism: Intensive activity with nontrivial volume supports load concern.; Small intensive forward-dominated traffic can resemble repeated request/control floods.; Intensive small packets with uniform responses can resemble repetitive traffic. Those behavior hypotheses overlap the actual traffic label; the aggregated centroid crosses the selected alert threshold in the wrong direction. This is an explanatory hypothesis, not a verified attack mechanism.

### day false_positive — source row 657125

Actual label: BENIGN. Score 79.057373, Critical; alert=True.

Inputs: `{" Flow Packets/s": 750000.0, " Total Fwd Packets": 3.0, " Packet Length Mean": 12.25, " Bwd Packet Length Std": 0.0, " Down/Up Ratio": 0.0}`.

Dominant input terms: `{" Flow Packets/s": "intensive", " Total Fwd Packets": "moderate", " Packet Length Mean": "small", " Bwd Packet Length Std": "uniform", " Down/Up Ratio": "forward"}`.

Strongest rules: R08 -> High (1.0000), R10 -> Critical (0.9112), R11 -> High (0.9112).

Possible error mechanism: Intensive activity with nontrivial volume supports load concern.; Small intensive forward-dominated traffic can resemble repeated request/control floods.; Intensive small packets with uniform responses can resemble repetitive traffic. Those behavior hypotheses overlap the actual traffic label; the aggregated centroid crosses the selected alert threshold in the wrong direction. This is an explanatory hypothesis, not a verified attack mechanism.
