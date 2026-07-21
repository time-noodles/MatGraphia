SCHEMA={
    "type":"Solid-State",
    "fields":[
        {"name":"furnace_info","type":"str","label":"Furnace Info (使用炉情報)","default":"銀炉1"},
        {"name":"quartz_diameter","type":"float","label":"Quartz Tube Diameter (石英管の直径 mm)","default":10.0},
        {"name":"quartz_length","type":"float","label":"Quartz Tube Length (石英管の長さ cm)","default":10.0}
    ],
    "tables":[
        {
            "name":"preparation_table",
            "label":"Preparation / Ingredients (仕込み内容: Stoichiometry 計算可能)",
            "is_advanced_prep":True,
            "columns":[
                {"name":"item","type":"str"},
                {"name":"Composition ratio","type":"float"},
                {"name":"M.W.","type":"float"},
                {"name":"mass","type":"float"}
            ],
            "init_data":[
                {"item":"Bi","Composition ratio":2.0,"M.W.":208.98,"mass":0.0},
                {"item":"Te","Composition ratio":3.0,"M.W.":127.60,"mass":0.0}
            ]
        },
        {
            "name":"temperature_profile",
            "label":"Heating Profile (温度プロファイル)",
            "is_heating_profile":True,
            "columns":[
                {"name":"Heating Temperature (C)","type":"int"},
                {"name":"Duration (h)","type":"float"},
                {"name":"Target End","type":"bool"}
            ],
            "init_data":[
                {"Heating Temperature (C)":1000,"Duration (h)":10.0,"Target End":False},
                {"Heating Temperature (C)":1000,"Duration (h)":40.0,"Target End":True},
                {"Heating Temperature (C)":40,"Duration (h)":10.0,"Target End":False}
            ]
        }
    ]
}
