# TASK05 implemented fuzzy architecture

Production A_frozen remains the unchanged five-input/22-rule Mamdani model. A_refit uses the same architecture with fold-training memberships. B_flat8 is a 15-rule eight-input Mamdani model. C_hierarchy has four computationally separate modules (9 load, 6 timing, 6 connection, 6 structure rules), each with its own clipped/aggregated output and centroid, followed by 7 final Mamdani rules: 34 rules total. D_behavior has 6 flooding-like load, 7 persistent-intermittent behavior and 6 connection rules, followed by 6 final Mamdani rules: 25 total.

Hierarchical inference is physical inputs -> input memberships -> per-module min/max rules -> per-module clipped output union -> module centroids -> module-score memberships -> final min/max rules -> output union -> final centroid. There is no averaging, voting, learned classifier, label lookup or Cartesian enumeration. Modules are computationally independent first-layer mappings, not statistically independent evidence. Timing/structure can encode related behavior.

All membership anchors are training-only p25/p60/p90, with positive subsets for backward-length variation and IAT spread. Rate/count/variation/duration/IAT use log1p. Size is linear. Exported ratio has domain anchors 0/1/2; SYN has a fixed 0/1 domain. Low/high shoulder sets saturate finite extremes; middle sets are triangular. Duplicated quantiles expand deterministically by one physical unit or 1% of the first anchor. Each three-term partition covers its domain. Intermediate memberships use explicit 25/50/75 score anchors on the 0–100 behavioral scale. These semantic index anchors are not label-tuned.

All layers use AND=min, OR=max, implication=min clipping, aggregation=max, 201-point centroid quadrature. Same Low/Medium/High/Critical output sets and 25/50/75 category cuts as the original. Final alert threshold is calibrated separately per model/fold. membership_parameters.csv and all nine experimental fold JSON configs record exact numerical parameters and model IDs.

C requires cross-dimension agreement for strong elevation; D permits one multi-input behavior module to elevate concern, and two to activate Critical. A SYN flag or high packet rate alone cannot establish a definitive attack. Connection modules use the coarse exported ratio; zero does not mean no backward packets. Repeated connection attempts/scanning cannot be reconstructed from these per-flow summaries, so no such definitive module is claimed.

Missing/non-numeric/Boolean/NaN/infinite/negative inputs abstain globally. Missing subsystem output also forces final abstention, even if other modules fire. SYN values outside [0,1] reject rather than saturate a malformed indicator; other extreme finite inputs saturate with range flags. Fractional values inside the SYN domain interpolate its two terms, although actual source observations are binary. Zero is a valid measurement, never a missing-value replacement. Explanation paths preserve layer name, stable rule ID, antecedent, strength, consequent, raw memberships, module score and final score.

Example executable API: AdvancedRiskEngine.load(config).predict_one(eight_input_dict); predict_batch(frame,batch_size=1024) is vectorized. Existing PolicyRiskModel can wrap this engine without changing inference evidence. The experimental CLI is scripts/task05_predict.py. Production API/UI are not imported or replaced by these research engines.

## B_flat8

| Layer | Rule | IF | THEN | Rationale |
|---|---|---|---|---|
| final | E01 | rate IS low AND volume IS low | Low | Sparse few-packet exchange; low-rate attacks can overlap. |
| final | E02 | rate IS low AND volume IS moderate | Low | Low intensity with modest volume is weak load evidence. |
| final | E03 | rate IS low AND volume IS high | Medium | Long low-rate transfers need context. |
| final | E04 | rate IS moderate AND volume IS low | Low | Short ordinary exchanges support a routine-load hypothesis. |
| final | E05 | rate IS moderate AND volume IS moderate | Low | Ordinary intensity and volume carry weak load concern. |
| final | E06 | rate IS moderate AND volume IS high | Medium | Sustained packet volume warrants context. |
| final | E07 | rate IS high AND volume IS low | Low | Tiny duration can inflate few-packet rate. |
| final | E08 | rate IS high AND volume IS moderate | Medium | Intensity corroborated by nontrivial volume. |
| final | E09 | rate IS high AND volume IS high | High | Joint high intensity and volume support load concern. |
| final | E10 | duration IS high AND iat IS high AND variation IS high | High | Long intermittent exchanges with highly varied responses warrant investigation. |
| final | E11 | size IS high AND variation IS high AND duration IS high | High | Large varied responses sustained over a long flow; benign overlap remains. |
| final | E12 | syn IS present AND balance IS low AND volume IS high | High | SYN-bearing high-volume exported forward-heavy traffic. |
| final | E13 | syn IS present AND balance IS low AND volume IS low | Medium | Short handshake-like exchanges are ambiguous, not proof of scanning. |
| final | E14 | rate IS high AND volume IS high AND size IS low | Critical | Repeated small high-rate packets with sustained volume support flooding-like load concern. |
| final | E15 | duration IS low AND volume IS low | Low | A short small exchange supports a routine-transaction hypothesis. |
## C_hierarchy

| Layer | Rule | IF | THEN | Rationale |
|---|---|---|---|---|
| intensity | L01 | rate IS low AND volume IS low | Low | Sparse few-packet exchange; low-rate attacks can overlap. |
| intensity | L02 | rate IS low AND volume IS moderate | Low | Low intensity with modest volume is weak load evidence. |
| intensity | L03 | rate IS low AND volume IS high | Medium | Long low-rate transfers need context. |
| intensity | L04 | rate IS moderate AND volume IS low | Low | Short ordinary exchanges support a routine-load hypothesis. |
| intensity | L05 | rate IS moderate AND volume IS moderate | Low | Ordinary intensity and volume carry weak load concern. |
| intensity | L06 | rate IS moderate AND volume IS high | Medium | Sustained packet volume warrants context. |
| intensity | L07 | rate IS high AND volume IS low | Low | Tiny duration can inflate few-packet rate. |
| intensity | L08 | rate IS high AND volume IS moderate | Medium | Intensity corroborated by nontrivial volume. |
| intensity | L09 | rate IS high AND volume IS high | High | Joint high intensity and volume support load concern. |
| timing | T01 | duration IS low | Low | Short lifetime provides little long-gap persistence evidence. |
| timing | T02 | iat IS low | Low | Stable/small inter-arrival spread is weak intermittent-timing evidence. |
| timing | T03 | duration IS moderate AND iat IS moderate | Medium | Moderate persistence and variable spacing are ambiguous. |
| timing | T04 | duration IS high AND iat IS moderate | Medium | Long lifetime with moderate gaps may be an idle legitimate session. |
| timing | T05 | duration IS moderate AND iat IS high | Medium | Large gaps without long persistence require context. |
| timing | T06 | duration IS high AND iat IS high | High | Long-lived intermittent activity is a timing concern, not attack attribution. |
| connection | N01 | syn IS absent | Low | Absence of exported SYN evidence is not proof of a safe connection. |
| connection | N02 | balance IS moderate | Low | Exported directional balance counters a forward-heavy hypothesis. |
| connection | N03 | balance IS high | Low | Backward-heavy traffic does not support this forward-heavy connection hypothesis. |
| connection | N04 | syn IS present AND balance IS low AND volume IS low | Medium | A short SYN-bearing forward-heavy exchange is ambiguous. |
| connection | N05 | syn IS present AND balance IS low AND volume IS moderate | Medium | Nontrivial forward-heavy SYN-bearing exchange merits context. |
| connection | N06 | syn IS present AND balance IS low AND volume IS high | High | SYN evidence corroborated by high volume and exported forward imbalance. No repeated-attempt claim. |
| structure | P01 | size IS low | Low | Small packets alone are not an abnormal response-size pattern. |
| structure | P02 | variation IS low | Low | Low response spread can be routine or reflect too few backward packets. |
| structure | P03 | size IS moderate AND variation IS moderate | Medium | Moderate response size and spread are ambiguous. |
| structure | P04 | size IS high AND variation IS moderate | Medium | Large responses may simply be payload transfer. |
| structure | P05 | size IS moderate AND variation IS high | Medium | High spread with moderate mean size warrants context. |
| structure | P06 | size IS high AND variation IS high | High | Joint large size and high response variability; benign transfers overlap. |
| final | F01 | intensity IS low AND timing IS low AND connection IS low AND structure IS low | Low | All module outputs weakly support their respective concern patterns. |
| final | F02 | intensity IS moderate OR timing IS moderate OR connection IS moderate OR structure IS moderate | Medium | Any moderate module is ambiguous behavioral evidence. |
| final | F03 | intensity IS high OR timing IS high OR connection IS high OR structure IS high | Medium | One elevated dimension needs cross-dimension corroboration. |
| final | F04 | intensity IS high AND connection IS high | Critical | Joint load and connection concerns provide corroboration. |
| final | F05 | timing IS high AND structure IS high | High | Joint long-gap timing and varied-response structure provide corroboration. |
| final | F06 | intensity IS high AND timing IS high | High | Joint sustained load and intermittent timing merit investigation. |
| final | F07 | connection IS high AND structure IS high | High | Connection and response structure concerns corroborate each other. |
## D_behavior

| Layer | Rule | IF | THEN | Rationale |
|---|---|---|---|---|
| flood | B01 | rate IS low | Low | Sparse rate weakens a high-rate flooding hypothesis. |
| flood | B02 | volume IS low | Low | Few-packet bursts are not sustained floods. |
| flood | B03 | rate IS moderate AND volume IS moderate | Low | Ordinary load provides weak flooding evidence. |
| flood | B04 | rate IS moderate AND volume IS high | Medium | Volume without high intensity is ambiguous. |
| flood | B05 | rate IS high AND volume IS moderate | Medium | Intensity corroborated by modest volume. |
| flood | B06 | rate IS high AND volume IS high | High | Sustained high-rate packet load supports flooding-like concern. |
| intermittent | T01 | duration IS low | Low | Short lifetime provides little long-gap persistence evidence. |
| intermittent | T02 | iat IS low | Low | Stable/small inter-arrival spread is weak intermittent-timing evidence. |
| intermittent | T03 | duration IS moderate AND iat IS moderate | Medium | Moderate persistence and variable spacing are ambiguous. |
| intermittent | T04 | duration IS high AND iat IS moderate | Medium | Long lifetime with moderate gaps may be an idle legitimate session. |
| intermittent | T05 | duration IS moderate AND iat IS high | Medium | Large gaps without long persistence require context. |
| intermittent | T06 | duration IS high AND iat IS high | High | Long-lived intermittent activity is a timing concern, not attack attribution. |
| intermittent | T07 | duration IS high AND iat IS high AND variation IS high AND size IS high | Critical | Persistent intermittent exchanges with large varied responses corroborate a resource-occupation-like behavior; ordinary downloads can overlap. |
| connection | N01 | syn IS absent | Low | Absence of exported SYN evidence is not proof of a safe connection. |
| connection | N02 | balance IS moderate | Low | Exported directional balance counters a forward-heavy hypothesis. |
| connection | N03 | balance IS high | Low | Backward-heavy traffic does not support this forward-heavy connection hypothesis. |
| connection | N04 | syn IS present AND balance IS low AND volume IS low | Medium | A short SYN-bearing forward-heavy exchange is ambiguous. |
| connection | N05 | syn IS present AND balance IS low AND volume IS moderate | Medium | Nontrivial forward-heavy SYN-bearing exchange merits context. |
| connection | N06 | syn IS present AND balance IS low AND volume IS high | High | SYN evidence corroborated by high volume and exported forward imbalance. No repeated-attempt claim. |
| final | F01 | flood IS low AND intermittent IS low AND connection IS low | Low | All module outputs weakly support their respective concern patterns. |
| final | F02 | flood IS moderate OR intermittent IS moderate OR connection IS moderate | Medium | Any moderate module is ambiguous behavioral evidence. |
| final | F03 | flood IS high OR intermittent IS high OR connection IS high | High | A corroborated behavior module can warrant elevated investigation. |
| final | F04 | flood IS high AND intermittent IS high | Critical | Two distinct multi-input behavior hypotheses agree; this is not a named attack diagnosis. |
| final | F05 | flood IS high AND connection IS high | Critical | Two distinct multi-input behavior hypotheses agree; this is not a named attack diagnosis. |
| final | F06 | intermittent IS high AND connection IS high | Critical | Two distinct multi-input behavior hypotheses agree; this is not a named attack diagnosis. |
