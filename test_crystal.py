"""
crystal_toolkit の描画方法を調査するテストスクリプト
実行: conda run -n py312 python test_crystal.py
"""
import os
import sys

os.environ["NO_PROXY"] = "localhost,127.0.0.1"

print("=== Step 1: crystal_toolkit インポート前 ===")
from pymatgen.core.graphs import StructureGraph
print(f"import前 _repr_html_: {hasattr(StructureGraph, '_repr_html_')}")

print("\n=== Step 2: crystal_toolkit インポート後 ===")
import crystal_toolkit
print(f"import後 _repr_html_: {hasattr(StructureGraph, '_repr_html_')}")

# crystal_toolkit の内部モジュールを調査
print("\n=== Step 3: crystal_toolkit のモジュール一覧 ===")
import pkgutil
for mod in pkgutil.iter_modules(crystal_toolkit.__path__):
    print(f"  {mod.name}")

print("\n=== Step 4: 構造読み込みと StructureGraph 生成 ===")
from pymatgen.core import Structure
from pymatgen.analysis.local_env import MinimumDistanceNN

# テスト用の簡単な構造（CIFファイルが不要）
struct = Structure(
    [[3.54, 0, 0], [0, 3.54, 0], [0, 0, 3.54]],
    ["Cu"],
    [[0, 0, 0]]
)
env = MinimumDistanceNN()
graph = StructureGraph.from_local_env_strategy(struct, env)
print(f"StructureGraph 生成完了: {graph}")
print(f"_repr_html_: {hasattr(graph, '_repr_html_')}")

# StructureGraph の全メソッドを確認
print("\n=== Step 5: graph オブジェクトのメソッド ===")
for name in dir(graph):
    if not name.startswith("__"):
        print(f"  {name}")

# crystal_toolkit 内の get_scene 等を探す
print("\n=== Step 6: crystal_toolkit.renderables の調査 ===")
try:
    from crystal_toolkit import renderables
    print(f"renderables: {dir(renderables)}")
except Exception as e:
    print(f"renderables インポート失敗: {e}")

print("\n=== Step 7: crystal_toolkit components の調査 ===")
try:
    from crystal_toolkit import components
    print(f"components: {dir(components)}")

    from crystal_toolkit.components.structure_graph import StructureGraphComponent
    print(f"StructureGraphComponent: {StructureGraphComponent}")

    comp = StructureGraphComponent(graph)
    print(f"Component 生成完了: {comp}")

    layout = comp.layout()
    print(f"layout type: {type(layout)}")
except Exception as e:
    print(f"components 調査失敗: {e}")

print("\n=== Step 8: get_scene / get_scene_dict の探索 ===")
# crystal_toolkit 配下で scene に関する関数を探す
try:
    import crystal_toolkit.renderables.structure_graph as sg_mod
    print(f"structure_graph モジュール: {dir(sg_mod)}")
    # get_scene を試す
    scene = graph.get_scene()
    print(f"get_scene() 成功: {type(scene)}")

    scene_dict = scene.as_dict()
    print(f"scene as_dict keys: {list(scene_dict.keys())}")

    # HTML として出力してファイルに保存
    import json
    with open("test_scene.json", "w") as f:
        json.dump(scene_dict, f, indent=2, default=str)
    print("scene を test_scene.json に保存しました")
except Exception as e:
    print(f"get_scene 失敗: {e}")

print("\n=== Step 9: 独自 HTML 生成試行 ===")
try:
    # crystal_toolkit が持つ HTML レンダラーを直接呼ぶ
    from crystal_toolkit.core.scene import Scene
    print(f"Scene クラス: {Scene}")
    html = graph.get_scene()._repr_html_()
    print(f"Scene._repr_html_() 成功: {html[:200]}")
    with open("test_output.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("HTML を test_output.html に保存しました")
except Exception as e:
    print(f"Scene HTML 生成失敗: {e}")

print("\n=== 完了 ===")
