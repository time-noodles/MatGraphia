# MatGraphia - 結晶構造プレビュー (crystal_toolkit 3Dインタラクティブ)
# DashサーバーをバックグラウンドスレッドでStreamlit内で起動し
# iframeで3Dモデルを埋め込む
import os
import socket
import tempfile
import warnings
import threading

os.environ["NO_PROXY"]="localhost,127.0.0.1"


def _find_free_port():
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
        s.bind(("",0))
        return s.getsockname()[1]


# モジュールレベルでサーバー状態を管理
_server_lock=threading.Lock()
_active_port=None
_active_cif_hash=None


def _start_dash_server(graph,port):
    """Dashサーバーをデーモンスレッドで起動"""
    import nest_asyncio
    nest_asyncio.apply()
    import dash
    from dash import html
    import crystal_toolkit.components as ctc

    app=dash.Dash(
        __name__,
        suppress_callback_exceptions=True,
    )
    struct_component=ctc.StructureMoleculeComponent(graph,id="mg_struct_preview")
    app.layout=html.Div(
        [struct_component.layout()],
        style={
            "width":"100%","height":"100vh",
            "margin":"0","padding":"0","backgroundColor":"white"
        }
    )
    ctc.register_crystal_toolkit(app,layout=app.layout)

    def run():
        app.run(debug=False,port=port,use_reloader=False)

    t=threading.Thread(target=run,daemon=True)
    t.start()
    return t


def build_structure_preview(cif_bytes:bytes,cif_name:str):
    """
    CIFバイト列からcrystal_toolkitの3Dインタラクティブビューアを起動する。

    Returns:
        (graph_str, payload_dict, error_str)
        payload_dict: {
            "summary": {...},
            "dash_port": int,
            "graph_text": str,
        }
    """
    global _active_port,_active_cif_hash

    try:
        from pymatgen.core import Structure
        from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
        from pymatgen.core.graphs import StructureGraph
        from pymatgen.core.local_env import MinimumDistanceNN
        from pymatgen.io.cif import CifParser
    except Exception as e:
        return None,None,f"pymatgenの読み込みに失敗しました: {e}"

    suffix=os.path.splitext(cif_name or "uploaded.cif")[1] or ".cif"
    tmp_path=None
    try:
        # CIFハッシュで重複起動を防止
        import hashlib
        cif_hash=hashlib.md5(cif_bytes).hexdigest()

        with _server_lock:
            if _active_cif_hash==cif_hash and _active_port is not None:
                # 既にこのCIFのサーバーが起動中 -> ポートが生きているか確認
                try:
                    s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
                    s.settimeout(1)
                    s.connect(("127.0.0.1",_active_port))
                    s.close()
                    # サーバーは生きている -> 解析だけやり直してポートを返す
                except Exception:
                    # サーバーが死んでいる -> 再起動
                    _active_port=None
                    _active_cif_hash=None

        # ==========================================
        # 1. CIF解析
        # ==========================================
        with tempfile.NamedTemporaryFile(delete=False,suffix=suffix) as tf:
            tf.write(cif_bytes)
            tmp_path=tf.name

        struct=None
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                parser=CifParser(tmp_path,occupancy_tolerance=100)
                parsed=parser.parse_structures(primitive=False)
                if parsed:
                    struct=parsed[0]
        except Exception:
            struct=None

        if struct is None:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                struct=Structure.from_file(tmp_path)

        if struct is None or len(struct)==0:
            return None,None,f"有効な構造を抽出できませんでした: {cif_name}"

        # 慣用セルに変換
        try:
            analyzer=SpacegroupAnalyzer(struct)
            conventional_struct=analyzer.get_conventional_standard_structure()
        except Exception:
            conventional_struct=struct

        env=MinimumDistanceNN()
        graph=StructureGraph.from_local_env_strategy(conventional_struct,env)

        # Summary情報
        atom_counts={}
        for s in conventional_struct.sites:
            k=str(s.specie)
            atom_counts[k]=int(atom_counts.get(k,0))+1

        # ==========================================
        # 2. Dashサーバー起動 (必要な場合のみ)
        # ==========================================
        with _server_lock:
            if _active_cif_hash!=cif_hash or _active_port is None:
                port=_find_free_port()
                _start_dash_server(graph,port)
                _active_port=port
                _active_cif_hash=cif_hash
                # サーバー起動待機
                import time
                time.sleep(1.0)

        payload={
            "summary":{
                "formula":conventional_struct.composition.reduced_formula,
                "site_count":len(conventional_struct),
                "volume":round(conventional_struct.lattice.volume,4),
                "a":round(conventional_struct.lattice.a,4),
                "b":round(conventional_struct.lattice.b,4),
                "c":round(conventional_struct.lattice.c,4),
                "alpha":round(conventional_struct.lattice.alpha,3),
                "beta":round(conventional_struct.lattice.beta,3),
                "gamma":round(conventional_struct.lattice.gamma,3),
                "edge_count":graph.graph.number_of_edges(),
                "atom_counts":atom_counts,
            },
            "dash_port":_active_port,
            "graph_text":str(graph),
        }
        return str(graph),payload,None

    except Exception as e:
        return None,None,f"結晶構造プレビュー生成に失敗しました: {e}"
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
