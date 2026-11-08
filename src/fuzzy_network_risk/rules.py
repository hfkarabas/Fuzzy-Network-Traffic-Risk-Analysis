"""Fixed, hand-authored security hypotheses, shared by both evaluation scenarios.

No rule is generated from labels or from the Cartesian product of input terms.
The first nine explicitly document conservative rate/volume coverage behavior.
"""


def rule(identifier, terms, consequent, rationale, operator='all'):
    return {
        'id': identifier,
        'antecedent': {operator: [{'feature': f, 'term': t} for f, t in terms]},
        'consequent': consequent,
        'weight': 1.0,
        'rationale': rationale,
    }


def default_rules():
    return [
        rule(
            'R01',
            [('rate', 'sparse'), ('volume', 'few')],
            'Low',
            'Sparse small flows alone provide little evidence of abnormal load; low-rate scans may evade this.',
        ),
        rule(
            'R02',
            [('rate', 'sparse'), ('volume', 'moderate')],
            'Low',
            'Modest traffic at a low packet rate has weak load evidence.',
        ),
        rule(
            'R03',
            [('rate', 'sparse'), ('volume', 'many')],
            'Medium',
            'Large low-rate flows merit context but may be legitimate long sessions.',
        ),
        rule(
            'R04',
            [('rate', 'moderate'), ('volume', 'few')],
            'Low',
            'Few packets at ordinary intensity can be routine transactions.',
        ),
        rule(
            'R05',
            [('rate', 'moderate'), ('volume', 'moderate')],
            'Low',
            'Ordinary rate and volume form a conservative low-load baseline.',
        ),
        rule(
            'R06',
            [('rate', 'moderate'), ('volume', 'many')],
            'Medium',
            'Large packet volume increases load concern without implying an attack.',
        ),
        rule(
            'R07',
            [('rate', 'intensive'), ('volume', 'few')],
            'Medium',
            'A tiny duration can inflate rate for a few packets; avoid critical risk from rate alone.',
        ),
        rule(
            'R08',
            [('rate', 'intensive'), ('volume', 'moderate')],
            'High',
            'Intensive activity with nontrivial volume supports load concern.',
        ),
        rule(
            'R09',
            [('rate', 'intensive'), ('volume', 'many')],
            'High',
            'High intensity and volume jointly support sustained-load concern.',
        ),
        rule(
            'R10',
            [('rate', 'intensive'), ('size', 'small'), ('balance', 'forward')],
            'Critical',
            'Small intensive forward-dominated traffic can resemble repeated request/control floods.',
        ),
        rule(
            'R11',
            [('rate', 'intensive'), ('size', 'small'), ('variation', 'uniform')],
            'High',
            'Intensive small packets with uniform responses can resemble repetitive traffic.',
        ),
        rule(
            'R12',
            [('rate', 'moderate'), ('size', 'small'), ('balance', 'forward')],
            'High',
            'Small forward-heavy transactions warrant investigation; legitimate one-way traffic overlaps.',
        ),
        rule(
            'R13',
            [('volume', 'many'), ('size', 'small'), ('balance', 'forward')],
            'High',
            'Many small forward packets can indicate repeated requests.',
        ),
        rule(
            'R14',
            [('volume', 'many'), ('size', 'large'), ('variation', 'highly_variable')],
            'High',
            'Large varied responses at high volume can produce resource pressure; benign transfers overlap.',
        ),
        rule(
            'R15',
            [('rate', 'sparse'), ('size', 'large'), ('variation', 'highly_variable')],
            'Medium',
            'Large varied responses at sparse rate are ambiguous rather than inherently safe.',
        ),
        rule(
            'R16',
            [('rate', 'moderate'), ('size', 'large'), ('variation', 'highly_variable')],
            'High',
            'Varied large responses at ordinary intensity may still describe costly transactions.',
        ),
        rule(
            'R17',
            [('rate', 'moderate'), ('size', 'medium'), ('balance', 'balanced')],
            'Low',
            'Balanced medium-size transactions provide a routine-traffic counter-hypothesis.',
        ),
        rule(
            'R18',
            [('rate', 'sparse'), ('size', 'medium'), ('balance', 'balanced')],
            'Low',
            'Sparse balanced transactions provide weak evidence of abnormal resource load.',
        ),
        rule(
            'R19',
            [('volume', 'few'), ('size', 'small'), ('balance', 'forward')],
            'Medium',
            'Small forward-only exchanges merit context, including scanning, but are not definitive.',
        ),
        rule(
            'R20',
            [('rate', 'moderate'), ('variation', 'variable'), ('balance', 'balanced')],
            'Low',
            'Ordinary intensity with varied balanced exchanges supports a benign counter-hypothesis.',
        ),
        rule(
            'R21',
            [('rate', 'intensive'), ('size', 'large'), ('balance', 'backward')],
            'Medium',
            'Fast backward-heavy payload transfer can be an ordinary download.',
        ),
        rule(
            'R22',
            [('volume', 'many'), ('variation', 'uniform'), ('balance', 'backward')],
            'Medium',
            'Large uniform directional transfer is ambiguous without application context.',
        ),
    ]
