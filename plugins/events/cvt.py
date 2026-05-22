SCHEMA = {
    "type": "CVT",
    "fields": [
        {"name": "transport_agent", "type": "str", "label": "Transport Agent (輸送剤 / 例: I2)", "default": "I2"},
        {"name": "quartz_diameter", "type": "float", "label": "Quartz Tube Diameter (石英管の直径 mm)", "default": 10.0},
        {"name": "quartz_length", "type": "float", "label": "Quartz Tube Length (石英管の長さ cm)", "default": 10.0}
    ],
    "tables": [
        {
            "name": "preparation_table",
            "label": "Preparation / Ingredients (仕込み内容: Stoichiometry 計算可能)",
            "is_advanced_prep": True,
            "columns": [
                {"name": "item", "type": "str"},
                {"name": "Composition ratio", "type": "float"},
                {"name": "mass", "type": "float"}
            ],
            "init_data": [
                {"item": "Fe", "Composition ratio": 1.0, "mass": 0.0},
                {"item": "S", "Composition ratio": 2.0, "mass": 0.0}
            ]
        },
        {
            "name": "temperature_profile",
            "label": "Heating Profile (T1 / T2)",
            "is_heating_profile": True,
            "columns": [
                {"name": "T1 (C)", "type": "int"},
                {"name": "T2 (C)", "type": "int"},
                {"name": "Duration (h)", "type": "float"},
                {"name": "Target End", "type": "bool"}
            ],
            "init_data": [
                {"T1 (C)": 900, "T2 (C)": 800, "Duration (h)": 168.0, "Target End": True}
            ]
        }
    ]
}
