SCHEMA = {
    "type": "Deintercalation",
    "fields": [
        {
            "name": "temperature",
            "type": "float",
            "label": "温度 (C)",
            "default": 25.0
        },
        {
            "name": "time",
            "type": "float",
            "label": "時間 (h)",
            "default": 24.0
        },
        {
            "name": "solvent",
            "type": "str",
            "label": "溶媒",
            "default": ""
        },
        {
            "name": "oxidizing_agent",
            "type": "str",
            "label": "酸化剤",
            "default": ""
        },
        {
            "name": "rotation",
            "type": "select",
            "label": "回転アリ・ナシ (任意)",
            "options": ["未指定", "アリ", "ナシ"],
            "default": "未指定"
        },
        {
            "name": "sample_form",
            "type": "select",
            "label": "粉末 or valk (任意)",
            "options": ["未指定", "粉末", "valk"],
            "default": "未指定"
        }
    ]
}
