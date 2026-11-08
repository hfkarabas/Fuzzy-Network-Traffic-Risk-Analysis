"""English presentation catalog, separate from inference parameters."""

FEATURES = [
    {
        'key': 'rate',
        'column': ' Flow Packets/s',
        'title': 'Packet rate',
        'unit': 'packets/s',
        'symbol': 'pps',
        'description': 'Packets per second across the flow.',
        'hint': 'A high value can indicate intensive traffic or a very short flow. A low value indicates sparse '
        'communication; neither alone establishes safety or attack.',
    },
    {
        'key': 'volume',
        'column': ' Total Fwd Packets',
        'title': 'Forward packet count',
        'unit': 'packets',
        'symbol': 'pkt',
        'description': "Total packets observed in the flow's initial direction.",
        'hint': 'High volume can be normal for a long transfer. Few packets can be a short transaction or scan; '
        'the count alone does not prove attack.',
    },
    {
        'key': 'size',
        'column': ' Packet Length Mean',
        'title': 'Mean packet length',
        'unit': 'bytes',
        'symbol': 'B',
        'description': 'Mean packet length within the flow.',
        'hint': 'Small packets can be control/request traffic; large packets can be data transfer. '
        'Both occur in legitimate traffic.',
    },
    {
        'key': 'variation',
        'column': ' Bwd Packet Length Std',
        'title': 'Backward length variability',
        'unit': 'bytes',
        'symbol': 'σ B',
        'description': 'Standard deviation of backward packet lengths.',
        'hint': 'A high value indicates varying lengths. Zero can mean equal lengths, too few backward packets '
        'or no backward packets; it is not proof of attack.',
    },
    {
        'key': 'balance',
        'column': ' Down/Up Ratio',
        'title': 'Direction balance',
        'unit': 'ratio',
        'symbol': '↓/↑',
        'description': 'Integer backward/forward packet ratio exported by the dataset.',
        'hint': '0 indicates forward dominance, 1 approximate balance, and larger values backward dominance. '
        'Integer quantization loses information; 0 does not imply no responses.',
    },
]
TERMS = {
    'sparse': 'Sparse',
    'moderate': 'Moderate',
    'intensive': 'Intensive',
    'few': 'Few',
    'many': 'Many',
    'small': 'Small',
    'medium': 'Medium',
    'large': 'Large',
    'uniform': 'Uniform',
    'variable': 'Variable',
    'highly_variable': 'Highly variable',
    'forward': 'Forward-dominated',
    'balanced': 'Balanced',
    'backward': 'Backward-dominated',
}
LEVELS = {'Low': 'Low', 'Medium': 'Medium', 'High': 'High', 'Critical': 'Critical'}
POLICIES = {
    'Sensitive': {'title': 'Sensitive', 'description': 'More alerts; a greater chance of false alarms.'},
    'Balanced': {
        'title': 'Balanced',
        'description': 'An intermediate operating point between alert frequency and missed attacks.',
    },
    'Conservative': {'title': 'Conservative', 'description': 'Fewer alerts; a greater chance of missed attacks.'},
}


def condition_text(expression):
    """Readable antecedent, e.g. 'Packet rate is intensive AND Mean packet length is small'."""
    if 'feature' in expression:
        feature = next(f for f in FEATURES if f['key'] == expression['feature'])
        return f'{feature["title"]} is {TERMS[expression["term"]].lower()}'
    operator = ' AND ' if 'all' in expression else ' OR '
    return operator.join(condition_text(child) for child in expression.get('all', expression.get('any', [])))


def rule_text(expression, consequent):
    return f'IF {condition_text(expression)} THEN risk is {LEVELS[consequent].lower()}.'
