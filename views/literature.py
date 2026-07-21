import streamlit as st
import database as db
import file_manager as fm
import plugin_manager as pm
from ui.forms import render_dynamic_form
from ui.helpers import _json_or_raw,log_errors

TITLE="文献の登録"
ORDER=1
# 画面描画
@log_errors("文献の登録")
def render():
    st.header("文献の登録")
    st.markdown("基本となる論文や内部資料を登録します。")
    from schemas import Literature
    literatures=db.fetch_all_literatures()
    LITERATURE_SCHEMAS=pm.get_literature_schemas()
    lit_options=list(LITERATURE_SCHEMAS.keys()) if LITERATURE_SCHEMAS else ["Paper","Internal_Report"]
    with st.form("literature_form"):
        lit_type=st.selectbox("文献タイプ (必須)",lit_options)
        doi_default="-" if lit_type=="学内論文" else ""
        doi=st.text_input("DOI (必須) *ローカル資料の場合等は '-' を入力",value=doi_default)
        remarks=st.text_area("備考 (必須) *内容や概要を記載")
        schema=LITERATURE_SCHEMAS.get(lit_type,{})
        if lit_type=="学内論文":
            st.write("---")
            st.markdown("**学内論文の入力項目**")
            parameters=render_dynamic_form(schema,key_prefix="lit_internal")
            title,authors,venue,publication_year,volume=None,None,None,0,None
        else:
            st.write("---")
            st.markdown("**以下は任意入力**")
            title=st.text_input("タイトル")
            authors=st.text_input("著者 (カンマ区切り)")
            col_venue,col_year,col_vol=st.columns(3)
            with col_venue:
                venue=st.text_input("発表先")
            with col_year:
                publication_year=st.number_input("発行年",min_value=0,max_value=3000,value=0,step=1)
            with col_vol:
                volume=st.text_input("巻 (Volume)")
            parameters=render_dynamic_form(schema,key_prefix="lit")
        uploaded_pdf=st.file_uploader("文献PDF(任意)のアップロード",type=["pdf"])
        submitted=st.form_submit_button("登録する")
        if submitted:
            if not doi or not remarks or not lit_type:
                st.error("【必須エラー】 文献タイプ、DOI、備考はすべて必須項目です。")
                return
            if lit_type=="学内論文":
                if not isinstance(parameters,dict):
                    st.error("【入力エラー】 学内論文の入力内容が不正です。")
                    return
                if not parameters.get("name") or not parameters.get("degree") or not parameters.get("year"):
                    st.error("【必須エラー】 学位・名前・年は必須です。")
                    return
                doi="-"
            for l in literatures:
                if l["doi"]==doi and doi not in ["","-","None"]:
                    st.error("【重複エラー】 同じDOI of 文献がすでに登録されています！")
                    return
            try:
                lit_title=title if title else None
                lit_authors=authors if authors else None
                lit_venue=venue if venue else None
                lit_year=int(publication_year) if publication_year>0 else None
                lit_volume=volume if volume else None
                if lit_type=="学内論文":
                    thesis_name=str(parameters.get("name","")).strip()
                    thesis_degree=str(parameters.get("degree","")).strip()
                    thesis_year=parameters.get("year")
                    lit_title=thesis_name if thesis_name else None
                    lit_authors=thesis_name if thesis_name else None
                    lit_venue=f"学内{thesis_degree}論文" if thesis_degree else "学内論文"
                    try:
                        lit_year=int(thesis_year) if thesis_year else None
                    except Exception:
                        lit_year=None
                    lit_volume=None
                lit=Literature(
                    literature_type=lit_type,
                    doi=doi,
                    remarks=remarks,
                    title=lit_title,
                    authors=lit_authors,
                    venue=lit_venue,
                    publication_year=lit_year,
                    volume=lit_volume,
                    parameters=parameters
                )
                if uploaded_pdf:
                    pdf_path=fm.save_literature_file(lit.literature_id,uploaded_pdf.name,uploaded_pdf.getvalue())
                    lit.pdf_file_path=pdf_path
                db.insert_literature(lit)
                st.success(f"文献を登録しました！ (ID: {lit.literature_id})")
                if lit.pdf_file_path:
                    st.info(f"PDFを保存しました: `{lit.pdf_file_path}`")
            except Exception as e:
                st.error(f"登録時にエラーが発生しました: {e}")
