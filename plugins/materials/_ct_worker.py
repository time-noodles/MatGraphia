# MatGraphia - 結晶構造スナップショット撮影ワーカー
# 別プロセスとして呼ばれ、CIFファイルからDash+crystal_toolkitで
# 結晶構造をレンダリングし、PNG画像を標準出力に書き出す
#
# Usage: python _ct_worker.py <cif_path> <output_png_path> [port]
import os
import sys
import time
import socket
import threading
import warnings

os.environ["NO_PROXY"]="localhost,127.0.0.1"


def find_free_port():
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
        s.bind(("",0))
        return s.getsockname()[1]


def main():
    if len(sys.argv)<3:
        print("Usage: python _ct_worker.py <cif_path> <output_png_path> [port]",file=sys.stderr)
        sys.exit(1)

    cif_path=sys.argv[1]
    output_path=sys.argv[2]
    port=int(sys.argv[3]) if len(sys.argv)>3 else find_free_port()

    # 1. CIF読み込みと構造解析
    import nest_asyncio
    nest_asyncio.apply()

    from pymatgen.core import Structure
    from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
    from pymatgen.core.graphs import StructureGraph
    from pymatgen.core.local_env import MinimumDistanceNN
    from pymatgen.io.cif import CifParser
    import dash
    from dash import html
    import crystal_toolkit.components as ctc
    from playwright.sync_api import sync_playwright

    struct=None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            parser=CifParser(cif_path,occupancy_tolerance=100)
            parsed=parser.parse_structures(primitive=False)
            if parsed:
                struct=parsed[0]
    except Exception:
        struct=None

    if struct is None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            struct=Structure.from_file(cif_path)

    if struct is None or len(struct)==0:
        print("ERROR: no valid structure",file=sys.stderr)
        sys.exit(2)

    # 慣用セルに変換
    try:
        analyzer=SpacegroupAnalyzer(struct)
        conventional_struct=analyzer.get_conventional_standard_structure()
    except Exception:
        conventional_struct=struct

    env=MinimumDistanceNN()
    graph=StructureGraph.from_local_env_strategy(conventional_struct,env)

    # 2. Dashアプリ構築
    app=dash.Dash(__name__)
    struct_component=ctc.StructureMoleculeComponent(graph,id="mg_struct_preview")
    app.layout=html.Div(
        [struct_component.layout()],
        style={
            "width":"800px","height":"600px",
            "margin":"0 auto","backgroundColor":"white"
        }
    )
    ctc.register_crystal_toolkit(app,layout=app.layout)

    def run_server():
        app.run(debug=False,port=port,use_reloader=False)

    server_thread=threading.Thread(target=run_server)
    server_thread.daemon=True
    server_thread.start()
    time.sleep(0.5)

    # 3. Playwright撮影
    with sync_playwright() as p:
        browser=p.chromium.launch(
            headless=True,
            args=[
                "--enable-webgl",
                "--disable-extensions",
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )
        page=browser.new_page(viewport={"width":800,"height":600})
        page.goto(f"http://127.0.0.1:{port}",wait_until="load")

        # canvas描画待機
        page.wait_for_selector("canvas",timeout=15000)
        page.wait_for_timeout(300)

        # カメラ回転
        canvas=page.locator("canvas").first
        box=canvas.bounding_box()
        if box:
            cx=box["x"]+box["width"]/2
            cy=box["y"]+box["height"]/2
            page.mouse.move(cx,cy)
            page.mouse.down()
            page.mouse.move(cx,cy+150,steps=2)
            page.mouse.move(cx-100,cy+150,steps=2)
            page.mouse.up()

        page.wait_for_timeout(200)
        page.screenshot(path=output_path)
        browser.close()

    print(f"OK:{output_path}")


if __name__=="__main__":
    main()
