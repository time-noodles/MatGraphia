SCHEMA = {
    "type": "Ar-Annealing",
    "fields": [
        {"name": "gas_flow", "type": "str", "label": "Gas Flow Rate (Ar流量)", "default": "100 sccm"},
        {"name": "quartz_diameter", "type": "float", "label": "Quartz Tube Diameter (石英管の直径 mm)", "default": 10.0},
        {"name": "quartz_length", "type": "float", "label": "Quartz Tube Length (石英管の長さ cm)", "default": 10.0}
    ],
    "tables": [
        {
            "name": "preparation_table",
            "label": "Preparation (準備・仕込み内容)",
            "columns": [
                {"name": "Item (項目)", "type": "str"},
                {"name": "Detail (詳細)", "type": "str"}
            ],
            "init_data": [
                {"Item (項目)": "サンプル", "Detail (詳細)": "100mg"}
            ]
        },
        {
            "name": "temperature_profile",
            "label": "Annealing Profile (アニールプロファイル)",
            "is_heating_profile": True,
            "columns": [
                {"name": "Temperature (C)", "type": "int"},
                {"name": "Duration (h)", "type": "float"},
                {"name": "Target End", "type": "bool"}
            ],
            "init_data": [
                {"Temperature (C)": 500, "Duration (h)": 12.0, "Target End": True}
            ]
        }
    ]
}
