import streamlit as st
import pandas as pd

st.title("帳簿データアップロード画面")

uploaded_file = st.file_uploader("CSVまたはExcelファイルを選択してください", type=["csv", "xlsx"])

if uploaded_file is not None:
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    st.write("### アップロードされたデータのプレビュー（先頭10件）")
    st.dataframe(df.head(10))
    st.success("ファイルの読み込みに成功しました！")