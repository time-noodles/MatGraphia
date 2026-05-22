SCHEMA = {
    "type": "学内論文",
    "fields": [
        {
            "name": "degree",
            "type": "select",
            "label": "学位 (学士 / 修士 / 博士)",
            "options": ["学士", "修士", "博士"],
            "default": "修士"
        },
        {
            "name": "name",
            "type": "str",
            "label": "名前",
            "default": ""
        },
        {
            "name": "year",
            "type": "int",
            "label": "年",
            "default": 2026
        }
    ]
}
